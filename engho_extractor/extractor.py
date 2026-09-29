"""Deterministic, fail-closed normalization of a governed ENGHo source set."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import zipfile

from . import __version__
from .contracts import (
    ARTIFACT_TYPE,
    DATASET_FAMILY,
    EXTRACTION_CONTRACT_VERSION,
    REQUIRED_ROLES,
    SOURCE_BY_FILENAME,
    SOURCE_BY_ROLE,
    SURVEY_VINTAGE,
)
from .downloader import sha256

MAX_ARCHIVE_MEMBERS = 16
MAX_MEMBER_BYTES = 2 * 1024 * 1024 * 1024
MAX_EXPANDED_BYTES_PER_ARCHIVE = 2 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 300
MAX_PATH_LENGTH = 240
SUPPORTED_SUFFIXES = {".txt", ".csv"}
DELIMITERS = ("|", ";", "\t", ",")


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _decode(raw: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return encoding, raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("unsupported text encoding")


def _delimiter(header: str) -> str:
    counts = [(header.count(delimiter), delimiter) for delimiter in DELIMITERS]
    count, delimiter = max(counts)
    if count <= 0:
        raise ValueError("table header has no supported delimiter")
    return delimiter


def _safe_data_member(archive: zipfile.ZipFile):
    infos = archive.infolist()
    if len(infos) > MAX_ARCHIVE_MEMBERS:
        raise ValueError(f"archive has more than {MAX_ARCHIVE_MEMBERS} members")
    seen, expanded, supported = set(), 0, []
    for info in sorted(infos, key=lambda item: item.filename.casefold()):
        if info.is_dir():
            continue
        path = PurePosixPath(info.filename)
        mode = (info.external_attr >> 16) & 0o170000
        if mode not in (0, 0o100000):
            raise ValueError(f"archive member is a link or special file: {info.filename}")
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"unsafe archive member: {info.filename}")
        if len(info.filename) > MAX_PATH_LENGTH:
            raise ValueError(f"archive path exceeds {MAX_PATH_LENGTH} characters")
        if path.suffix.casefold() in {".zip", ".rar", ".7z", ".tar", ".gz"}:
            raise ValueError(f"nested archive is not supported: {info.filename}")
        key = path.name.casefold()
        if key in seen:
            raise ValueError(f"duplicate archive filename: {path.name}")
        seen.add(key)
        expanded += info.file_size
        if info.file_size > MAX_MEMBER_BYTES or expanded > MAX_EXPANDED_BYTES_PER_ARCHIVE:
            raise ValueError(f"archive member/expansion exceeds bounded limit: {info.filename}")
        if info.compress_size == 0 and info.file_size:
            raise ValueError(f"invalid compressed size: {info.filename}")
        if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
            raise ValueError(f"compression ratio exceeds {MAX_COMPRESSION_RATIO}: {info.filename}")
        if path.suffix.casefold() not in SUPPORTED_SUFFIXES:
            raise ValueError(f"unsupported archive member: {info.filename}")
        supported.append(info)
    if len(supported) != 1:
        raise ValueError(f"expected exactly one supported table in source ZIP; found {len(supported)}")
    return supported[0]


def _normalize_table(archive_path: Path, role: str, destination: Path) -> dict:
    if not zipfile.is_zipfile(archive_path):
        raise ValueError(f"unsupported or corrupt ZIP for role {role}")
    with zipfile.ZipFile(archive_path) as archive:
        info = _safe_data_member(archive)
        raw = archive.read(info)
    source_encoding, text = _decode(raw)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.splitlines()
    if not lines:
        raise ValueError(f"empty table for role {role}")
    delimiter = _delimiter(lines[0])
    reader = csv.reader(lines, delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration as exc:
        raise ValueError(f"missing header for role {role}") from exc
    if not header or any(name == "" for name in header):
        raise ValueError(f"invalid header for role {role}")
    folded = [name.strip().casefold() for name in header]
    if len(set(folded)) != len(folded):
        raise ValueError(f"duplicate columns for role {role}")
    spec = SOURCE_BY_ROLE[role]
    missing = sorted(set(spec.required_columns) - set(folded))
    if missing:
        raise ValueError(f"{role} missing required identity columns: {missing}")
    row_count = sum(1 for _ in reader)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    schema_hash = hashlib.sha256("\0".join(header).encode("utf-8")).hexdigest()
    return {
        "role": role,
        "source_member": info.filename,
        "normalized_filename": destination.name,
        "file": destination.as_posix(),  # caller rewrites to release-relative path
        "bytes": destination.stat().st_size,
        "sha256": sha256(destination),
        "source_encoding": source_encoding,
        "encoding": "utf-8",
        "delimiter": delimiter,
        "rows": row_count,
        "columns": len(header),
        "column_names": header,
        "schema_hash": schema_hash,
    }


def _load_source_manifest(source_dir: Path) -> tuple[dict, Path]:
    path = source_dir / "source-manifest.json"
    if not path.is_file():
        raise ValueError("source directory missing source-manifest.json")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("dataset_family") != DATASET_FAMILY or manifest.get("survey_vintage") != SURVEY_VINTAGE:
        raise ValueError("source manifest is not governed ENGHo 2017-2018")
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        raise ValueError("source manifest sources must be a list")
    by_role = {item.get("role"): item for item in sources}
    if set(by_role) != set(REQUIRED_ROLES) or len(sources) != len(REQUIRED_ROLES):
        raise ValueError("source manifest must contain exactly the five required roles")
    for role in REQUIRED_ROLES:
        item = by_role[role]
        spec = SOURCE_BY_ROLE[role]
        if item.get("filename") != spec.filename:
            raise ValueError(f"source filename mismatch for role {role}")
        archive = source_dir / spec.filename
        if not archive.is_file():
            raise ValueError(f"missing source ZIP for role {role}")
        if archive.stat().st_size != item.get("bytes") or sha256(archive) != item.get("sha256"):
            raise ValueError(f"source checksum/size mismatch for role {role}")
    return manifest, path


def _release_identity(source_manifest: dict) -> str:
    payload = {
        "artifact_type": ARTIFACT_TYPE,
        "survey_vintage": SURVEY_VINTAGE,
        "extraction_contract_version": EXTRACTION_CONTRACT_VERSION,
        "software_version": __version__,
        "sources": [
            {"role": item["role"], "filename": item["filename"], "sha256": item["sha256"]}
            for item in sorted(source_manifest["sources"], key=lambda x: x["role"])
        ],
    }
    digest = hashlib.sha256(canonical_json(payload)).hexdigest()
    return f"engho-2017-2018-{digest[:12]}"


def publish_release(source_dir: Path, output_root: Path, command: str = "engho-extractor extract") -> Path:
    source_dir = Path(source_dir).expanduser().resolve()
    output_root = Path(output_root).expanduser().resolve()
    source_manifest, source_manifest_path = _load_source_manifest(source_dir)
    release_id = _release_identity(source_manifest)
    final = output_root / release_id
    if final.exists():
        from .validator import validate_release
        validate_release(final)
        return final
    output_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{release_id}.", dir=output_root))
    try:
        inventory = []
        by_role = {item["role"]: item for item in source_manifest["sources"]}
        for role in REQUIRED_ROLES:
            spec = SOURCE_BY_ROLE[role]
            target = staging / "tables" / spec.normalized_filename
            item = _normalize_table(source_dir / spec.filename, role, target)
            item["file"] = target.relative_to(staging).as_posix()
            item["source_filename"] = spec.filename
            item["source_url"] = by_role[role]["url"]
            item["source_archive_sha256"] = by_role[role]["sha256"]
            inventory.append(item)
        manifest = {
            "schema_version": 1,
            "artifact_type": ARTIFACT_TYPE,
            "release_id": release_id,
            "publisher": "INDEC",
            "dataset_family": DATASET_FAMILY,
            "survey_vintage": SURVEY_VINTAGE,
            "extraction_contract_version": EXTRACTION_CONTRACT_VERSION,
            "source_manifest_sha256": sha256(source_manifest_path),
            "sources": source_manifest["sources"],
            "documentation": source_manifest.get("documentation", []),
            "files": inventory,
            "warnings": [],
            "producing_command": command,
            "software_version": __version__,
            "scientific_transformations_performed": False,
        }
        (staging / "output-manifest.json").write_bytes(canonical_json(manifest))
        os.replace(staging, final)
        from .validator import validate_release
        validate_release(final)
        return final
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

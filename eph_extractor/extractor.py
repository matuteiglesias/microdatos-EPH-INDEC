"""Deterministic, side-effect bounded EPH archive extraction."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import struct
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

EXTRACTION_CONTRACT_VERSION = "eph-zip-v2"
MAX_ARCHIVE_MEMBERS = 128
MAX_MEMBER_BYTES = 1024 * 1024 * 1024
MAX_EXPANDED_BYTES = 3 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 250
MAX_PATH_LENGTH = 240


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_members(archive: zipfile.ZipFile):
    infos = archive.infolist()
    if len(infos) > MAX_ARCHIVE_MEMBERS:
        raise ValueError(f"archive has more than {MAX_ARCHIVE_MEMBERS} members")
    seen, expanded = set(), 0
    for info in sorted(infos, key=lambda item: item.filename.casefold()):
        path = PurePosixPath(info.filename)
        if info.is_dir():
            continue
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
        if info.file_size > MAX_MEMBER_BYTES:
            raise ValueError(f"archive member exceeds {MAX_MEMBER_BYTES} bytes: {info.filename}")
        if expanded > MAX_EXPANDED_BYTES:
            raise ValueError(f"archive expands beyond {MAX_EXPANDED_BYTES} bytes")
        if info.file_size and info.compress_size == 0:
            raise ValueError(f"invalid compressed size: {info.filename}")
        if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
            raise ValueError(f"compression ratio exceeds {MAX_COMPRESSION_RATIO}: {info.filename}")
        yield info, path.name


def _category(name: str) -> str:
    lowered = name.casefold()
    if "hogar" in lowered or lowered.startswith("hog_"):
        return "household"
    if "individual" in lowered or "indiv" in lowered or lowered.startswith("ind_"):
        return "individual"
    return "other"


def _normalized(name: str, category: str) -> str:
    stem = Path(name).stem.casefold().replace(" ", "_")
    if category == "household" and not stem.startswith("usu_hogar"):
        stem = "usu_hogar_" + stem
    elif category == "individual" and not stem.startswith("usu_individual"):
        stem = "usu_individual_" + stem
    return stem + ".txt"


def _dbf_rows(path: Path):
    """Read the small, standard dBASE III subset used by EPH DBFs."""
    with path.open("rb") as fh:
        header = fh.read(32)
        if len(header) != 32:
            raise ValueError("truncated DBF header")
        count = struct.unpack("<I", header[4:8])[0]
        header_len, record_len = struct.unpack("<HH", header[8:12])
        fields = []
        while fh.tell() < header_len - 1:
            descriptor = fh.read(32)
            name = descriptor[:11].split(b"\0", 1)[0].decode("ascii")
            fields.append((name, chr(descriptor[11]), descriptor[16], descriptor[17]))
        fh.seek(header_len)
        rows = []
        for _ in range(count):
            record = fh.read(record_len)
            if len(record) != record_len:
                raise ValueError("truncated DBF record")
            if record[:1] == b"*":
                continue
            pos, row = 1, []
            for _, kind, length, _decimals in fields:
                raw = record[pos:pos + length].strip(); pos += length
                value = raw.decode("latin-1")
                row.append(value if kind != "N" else value)
            rows.append(row)
        return [field[0] for field in fields], rows


def _table_details(path: Path):
    raw = path.read_bytes()
    encoding = "utf-8"
    try:
        text = raw.decode(encoding)
    except UnicodeDecodeError:
        encoding, text = "latin-1", raw.decode("latin-1")
    rows = list(csv.reader(text.splitlines(), delimiter=";"))
    return encoding, max(0, len(rows) - 1), len(rows[0]) if rows else 0


def publish_release(archive: Path, output_root: Path, year: int, quarter: str,
                    source_manifest: Path | None = None, command: str = "") -> Path:
    quarter = quarter.upper()
    if quarter not in {"Q1", "Q2", "Q3", "Q4"}:
        raise ValueError("quarter must be Q1, Q2, Q3, or Q4")
    archive, output_root = archive.resolve(), output_root.resolve()
    identity = hashlib.sha256(
        (sha256(archive) + "\0" + EXTRACTION_CONTRACT_VERSION + "\0" +
         __import__("eph_extractor").__version__).encode("ascii")
    ).hexdigest()
    release_id = f"eph-{year}-{quarter.lower()}-{identity[:12]}"
    final = output_root / release_id
    if final.exists():
        return final
    output_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{release_id}.", dir=output_root))
    inventory, warnings = [], []
    try:
        if not zipfile.is_zipfile(archive):
            raise ValueError("unsupported or corrupt archive (only ZIP is supported)")
        unpack = staging / ".unpack"; unpack.mkdir()
        with zipfile.ZipFile(archive) as zf:
            members = list(_safe_members(zf))
            for info, basename in members:
                target = unpack / basename
                copied = 0
                with zf.open(info) as src, target.open("wb") as dst:
                    while chunk := src.read(1024 * 1024):
                        copied += len(chunk)
                        if copied > info.file_size or copied > MAX_MEMBER_BYTES:
                            raise ValueError(f"expanded size changed while reading: {info.filename}")
                        dst.write(chunk)
        used_names = set()
        for source in sorted(unpack.iterdir(), key=lambda p: p.name.casefold()):
            category = _category(source.name)
            if source.suffix.casefold() not in {".txt", ".csv", ".dbf"}:
                warnings.append(f"unsupported file: {source.name}"); continue
            name = _normalized(source.name, category)
            if name.casefold() in used_names:
                raise ValueError(f"duplicate normalized output: {name}")
            used_names.add(name.casefold())
            destination = staging / category / name
            destination.parent.mkdir(exist_ok=True)
            if source.suffix.casefold() == ".dbf":
                columns, rows = _dbf_rows(source)
                with destination.open("w", encoding="utf-8", newline="") as fh:
                    writer = csv.writer(fh, delimiter=";", lineterminator="\n")
                    writer.writerow(columns); writer.writerows(rows)
            else:
                raw = source.read_bytes()
                try: text = raw.decode("utf-8")
                except UnicodeDecodeError: text = raw.decode("latin-1")
                destination.write_text(text.replace("\r\n", "\n"), encoding="utf-8")
            encoding, row_count, column_count = _table_details(destination)
            schema_hash = hashlib.sha256(
                "\0".join(columns if source.suffix.casefold() == ".dbf" else
                           next(csv.reader(destination.read_text(encoding="utf-8").splitlines(), delimiter=";"), [])).encode("utf-8")
            ).hexdigest()
            inventory.append({"role": category, "period": f"{year}-{quarter}",
                "schema_hash": schema_hash, "original_name": source.name,
                "normalized_name": name, "file": destination.relative_to(staging).as_posix(),
                "bytes": destination.stat().st_size, "sha256": sha256(destination),
                "delimiter": ";", "encoding": encoding, "rows": row_count, "columns": column_count})
        if not inventory:
            raise ValueError("archive contains no supported tables")
        source_identity = sha256(source_manifest) if source_manifest else sha256(archive)
        manifest = {"schema_version": 1, "release_id": release_id,
            "extraction_contract_version": EXTRACTION_CONTRACT_VERSION,
            "source_archive_sha256": sha256(archive), "requested_year": year, "requested_quarter": quarter,
            "source_manifest_sha256": source_identity, "files": inventory,
            "warnings": warnings, "producing_command": command,
            "software_version": __import__("eph_extractor").__version__}
        (staging / "output-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        shutil.rmtree(unpack)
        os.replace(staging, final)
        return final
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

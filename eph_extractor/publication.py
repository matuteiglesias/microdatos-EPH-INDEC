"""Deterministic packaging for durable EPH candidate transport."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath

from .extractor import sha256

SCHEMA = "ecosystem-release-discovery/v1"
PRODUCER = "matuteiglesias/microdatos-EPH-INDEC"
ARTIFACT_TYPE = "publicdata.eph-microdata@1"


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _safe_relative(path: Path, base: Path) -> str:
    relative = path.resolve().relative_to(base.resolve()).as_posix()
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError("unsafe_publication_path")
    return relative


def _write_member(zf: zipfile.ZipFile, arcname: str, data: bytes) -> None:
    info = zipfile.ZipInfo(arcname, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    zf.writestr(info, data)


def package_candidate(release_dir: Path, source_dir: Path, output_dir: Path) -> dict:
    release_dir = release_dir.resolve()
    source_dir = source_dir.resolve()
    output_dir = output_dir.resolve()

    output_manifest_path = release_dir / "output-manifest.json"
    source_manifest_path = source_dir / "source-manifest.json"
    if not output_manifest_path.is_file():
        raise ValueError("missing_output_manifest")
    if not source_manifest_path.is_file():
        raise ValueError("missing_source_manifest")

    output_manifest = json.loads(output_manifest_path.read_text(encoding="utf-8"))
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))

    release_id = output_manifest.get("release_id")
    if not release_id or release_dir.name != release_id:
        raise ValueError("release_id_directory_mismatch")
    if source_manifest.get("schema_version") != 2:
        raise ValueError("stable_source_manifest_v2_required")
    if output_manifest.get("source_manifest_sha256") != sha256(source_manifest_path):
        raise ValueError("source_manifest_checksum_mismatch")

    source_name = source_manifest.get("original_filename")
    if not source_name or Path(source_name).name != source_name:
        raise ValueError("invalid_source_filename")
    source_archive = source_dir / source_name
    if not source_archive.is_file():
        raise ValueError("missing_source_archive")
    source_sha = sha256(source_archive)
    if source_manifest.get("sha256") != source_sha:
        raise ValueError("source_archive_checksum_mismatch")
    if output_manifest.get("source_archive_sha256") != source_sha:
        raise ValueError("output_source_checksum_mismatch")

    year = output_manifest.get("requested_year")
    quarter = output_manifest.get("requested_quarter")
    if source_manifest.get("requested_year") != year or source_manifest.get("requested_quarter") != quarter:
        raise ValueError("source_period_mismatch")

    for item in output_manifest.get("files", []):
        declared = release_dir / item["file"]
        if not declared.is_file() or sha256(declared) != item.get("sha256"):
            raise ValueError(f"release_file_checksum_mismatch:{item.get('file')}")

    output_dir.mkdir(parents=True, exist_ok=True)
    asset_name = f"{release_id}.zip"
    asset_path = output_dir / asset_name
    with zipfile.ZipFile(asset_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted((p for p in release_dir.rglob("*") if p.is_file()), key=lambda p: p.as_posix()):
            rel = _safe_relative(path, release_dir)
            _write_member(zf, f"{release_id}/{rel}", path.read_bytes())
        _write_member(zf, f"{release_id}/_source/source-manifest.json", source_manifest_path.read_bytes())
        _write_member(zf, f"{release_id}/_source/{source_name}", source_archive.read_bytes())

    tag = f"candidate-{release_id}"
    discovery = {
        "schema": SCHEMA,
        "producer": PRODUCER,
        "artifact_type": ARTIFACT_TYPE,
        "release_id": release_id,
        "status": "candidate",
        "period": {"year": year, "quarter": quarter},
        "extraction_contract_version": output_manifest.get("extraction_contract_version"),
        "source": {
            "publisher": source_manifest.get("publisher"),
            "dataset_family": source_manifest.get("dataset_family"),
            "original_filename": source_name,
            "source_archive_sha256": source_sha,
            "source_manifest_sha256": sha256(source_manifest_path),
        },
        "github_release": {
            "tag": tag,
            "asset_name": asset_name,
            "asset_sha256": sha256(asset_path),
            "manifest_sha256": sha256(output_manifest_path),
        },
    }
    discovery_path = output_dir / "discovery.json"
    discovery_path.write_bytes(canonical_json(discovery))
    return {"asset": str(asset_path), "discovery": str(discovery_path), **discovery}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Package one exact EPH release for durable candidate transport")
    parser.add_argument("release_dir", type=Path)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("build/publication"))
    args = parser.parse_args(argv)
    result = package_candidate(args.release_dir, args.source_dir, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

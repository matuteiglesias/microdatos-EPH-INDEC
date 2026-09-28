"""Structural validation and real-data commissioning receipt for ENGHo releases."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

from .contracts import (
    ARTIFACT_TYPE,
    EXTRACTION_CONTRACT_VERSION,
    PUBLISHED_ROW_TARGETS,
    REQUIRED_ROLES,
    SOURCE_BY_ROLE,
    SURVEY_VINTAGE,
)
from .downloader import sha256


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def validate_release(release: Path) -> dict:
    release = Path(release).expanduser().resolve()
    manifest_path = release / "output-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("release missing output-manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("artifact_type") != ARTIFACT_TYPE:
        raise ValueError("wrong ENGHo artifact type")
    if manifest.get("survey_vintage") != SURVEY_VINTAGE:
        raise ValueError("wrong ENGHo survey vintage")
    if manifest.get("extraction_contract_version") != EXTRACTION_CONTRACT_VERSION:
        raise ValueError("wrong extraction contract version")
    if manifest.get("scientific_transformations_performed") is not False:
        raise ValueError("custody release must not perform scientific transformations")
    files = manifest.get("files")
    if not isinstance(files, list):
        raise ValueError("manifest files must be a list")
    by_role = {item.get("role"): item for item in files}
    if set(by_role) != set(REQUIRED_ROLES) or len(files) != len(REQUIRED_ROLES):
        raise ValueError("release must contain exactly the five required table roles")
    for role in REQUIRED_ROLES:
        item = by_role[role]
        path = (release / item["file"]).resolve()
        if release not in path.parents or not path.is_file():
            raise ValueError(f"unsafe/missing normalized table for role {role}")
        if path.stat().st_size != item.get("bytes") or sha256(path) != item.get("sha256"):
            raise ValueError(f"normalized table checksum/size mismatch for role {role}")
        if item.get("normalized_filename") != SOURCE_BY_ROLE[role].normalized_filename:
            raise ValueError(f"normalized filename mismatch for role {role}")
        folded = {str(name).strip().casefold() for name in item.get("column_names", [])}
        missing = sorted(set(SOURCE_BY_ROLE[role].required_columns) - folded)
        if missing:
            raise ValueError(f"normalized {role} inventory lacks required identity columns: {missing}")
        if int(item.get("rows", -1)) < 0 or int(item.get("columns", 0)) <= 0:
            raise ValueError(f"invalid row/column inventory for role {role}")
    return {
        "status": "pass",
        "release_id": manifest["release_id"],
        "artifact_type": ARTIFACT_TYPE,
        "roles": list(REQUIRED_ROLES),
        "manifest_sha256": sha256(manifest_path),
    }


def commission_release(release: Path, output: Path | None = None) -> dict:
    validation = validate_release(release)
    release = Path(release).expanduser().resolve()
    manifest = json.loads((release / "output-manifest.json").read_text(encoding="utf-8"))
    by_role = {item["role"]: item for item in manifest["files"]}
    checks = []
    for role in REQUIRED_ROLES:
        observed = int(by_role[role]["rows"])
        expected = PUBLISHED_ROW_TARGETS[role]
        checks.append({
            "role": role,
            "observed_rows": observed,
            "published_rows": expected,
            "matches_published_dimension": observed == expected,
            "schema_hash": by_role[role]["schema_hash"],
            "columns": by_role[role]["columns"],
            "required_identity_columns": list(SOURCE_BY_ROLE[role].required_columns),
        })
    status = "pass" if all(item["matches_published_dimension"] for item in checks) else "blocked"
    receipt = {
        "schema_version": 1,
        "receipt_type": "publicdata.indec-engho-microdata-commissioning/v1",
        "status": status,
        "release_id": validation["release_id"],
        "release_manifest_sha256": validation["manifest_sha256"],
        "survey_vintage": SURVEY_VINTAGE,
        "producer_git_commit": _git_commit(),
        "extraction_contract_version": manifest.get("extraction_contract_version"),
        "software_version": manifest.get("software_version"),
        "sources": manifest.get("sources", []),
        "file_inventory": [
            {
                "role": item["role"],
                "file": item["file"],
                "normalized_filename": item["normalized_filename"],
                "rows": item["rows"],
                "columns": item["columns"],
                "schema_hash": item["schema_hash"],
                "delimiter": item["delimiter"],
                "source_encoding": item["source_encoding"],
                "encoding": item["encoding"],
            }
            for item in manifest["files"]
        ],
        "published_dimension_source": "INDEC ENGHo 2017-2018 user manual, table 1",
        "checks": checks,
        "warnings": [] if status == "pass" else ["one_or_more_published_dimensions_do_not_match"],
    }
    if output is not None:
        output = Path(output).expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        (output / "commissioning-receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        lines = [
            "# ENGHo 2017/18 commissioning receipt",
            "",
            f"Status: **{status.upper()}**",
            f"Release: `{validation['release_id']}`",
            f"Manifest SHA-256: `{validation['manifest_sha256']}`",
            "",
            "| role | observed | published | match | schema |",
            "|---|---:|---:|:---:|---|",
        ]
        for item in checks:
            lines.append(
                f"| {item['role']} | {item['observed_rows']} | {item['published_rows']} | "
                f"{'yes' if item['matches_published_dimension'] else 'no'} | `{item['schema_hash'][:12]}` |"
            )
        lines += [
            "",
            "This receipt verifies source-custody dimensions and identity schemas only. It does not select a reference population or compute expenditure shares, Engel coefficients, CBA/CBT, welfare, or poverty.",
            "",
        ]
        (output / "commissioning-receipt.md").write_text("\n".join(lines), encoding="utf-8")
    return receipt

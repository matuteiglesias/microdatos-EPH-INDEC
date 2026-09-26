"""Governed sequential acquisition/materialization for a contiguous EPH quarter envelope."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Callable

from .downloader import retrieve
from .extractor import publish_release, sha256

PERIOD_RE = re.compile(r"^(20\\d{2})-Q([1-4])$")
BATCH_SCHEMA = "publicdata.eph-microdata-batch/v1"


def _period_tuple(period: str) -> tuple[int, int]:
    match = PERIOD_RE.fullmatch(period)
    if match is None:
        raise ValueError(f"invalid EPH period: {period!r}")
    return int(match.group(1)), int(match.group(2))


def period_envelope(start: str, end: str) -> tuple[str, ...]:
    start_year, start_q = _period_tuple(start)
    end_year, end_q = _period_tuple(end)
    first = start_year * 4 + start_q
    last = end_year * 4 + end_q
    if last < first:
        raise ValueError("end period precedes start period")
    periods = []
    for ordinal in range(first, last + 1):
        year, q0 = divmod(ordinal - 1, 4)
        periods.append(f"{year}-Q{q0 + 1}")
    return tuple(periods)


def _hash_json(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_batch(
    *,
    start: str,
    end: str,
    output: Path,
    retrieve_fn: Callable = retrieve,
    publish_fn: Callable = publish_release,
) -> Path:
    periods = period_envelope(start, end)
    root = Path(output).expanduser().resolve()
    releases_root = root / "releases"
    sources_root = root / "sources"
    if root.exists() and (root / "batch_manifest.json").exists():
        existing = json.loads((root / "batch_manifest.json").read_text(encoding="utf-8"))
        if existing.get("periods") == list(periods):
            return root / "batch_manifest.json"
        raise ValueError("existing batch manifest has a different period envelope")
    root.mkdir(parents=True, exist_ok=True)

    entries = []
    for period in periods:
        year, quarter_num = _period_tuple(period)
        quarter = f"Q{quarter_num}"
        source_dir = sources_root / period
        release_dir = None
        try:
            archive, source_manifest = retrieve_fn(year, quarter, source_dir)
            release_dir = publish_fn(
                archive,
                releases_root,
                year,
                quarter,
                source_manifest,
                "eph-extractor batch",
            )
            output_manifest = release_dir / "output-manifest.json"
            if not output_manifest.is_file():
                raise ValueError(f"{period}: release missing output-manifest.json")
            manifest = json.loads(output_manifest.read_text(encoding="utf-8"))
            if (
                manifest.get("requested_year") != year
                or manifest.get("requested_quarter") != quarter
            ):
                raise ValueError(f"{period}: release period mismatch")
            roles = sorted(
                item.get("role")
                for item in manifest.get("files", [])
                if item.get("role") in {"household", "individual"}
            )
            if roles != ["household", "individual"]:
                raise ValueError(f"{period}: expected household and individual tables")
            entries.append(
                {
                    "period": period,
                    "release_id": manifest["release_id"],
                    "source_manifest_sha256": sha256(source_manifest),
                    "source_archive_sha256": manifest["source_archive_sha256"],
                    "release_manifest_sha256": _hash_json(output_manifest),
                    "household_rows": sum(
                        int(item["rows"])
                        for item in manifest["files"]
                        if item["role"] == "household"
                    ),
                    "person_rows": sum(
                        int(item["rows"])
                        for item in manifest["files"]
                        if item["role"] == "individual"
                    ),
                }
            )
        except Exception:
            if release_dir is None:
                shutil.rmtree(source_dir, ignore_errors=True)
            raise

    payload = {
        "schema_version": BATCH_SCHEMA,
        "periods": list(periods),
        "period_count": len(periods),
        "entries": entries,
        "qa": {
            "all_periods_materialized": len(entries) == len(periods),
            "unique_release_ids": len({row["release_id"] for row in entries}) == len(entries),
            "nonempty_household_tables": all(row["household_rows"] > 0 for row in entries),
            "nonempty_person_tables": all(row["person_rows"] > 0 for row in entries),
        },
    }
    manifest_path = root / "batch_manifest.json"
    manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2022-Q1")
    parser.add_argument("--end", default="2025-Q4")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    print(run_batch(start=args.start, end=args.end, output=args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

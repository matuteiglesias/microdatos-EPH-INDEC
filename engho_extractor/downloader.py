"""Bounded retrieval of the five explicit official ENGHo 2017/18 public-use ZIPs."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from . import __version__
from .contracts import (
    DATASET_FAMILY,
    DOCUMENTATION,
    OFFICIAL_BASE_URL,
    SOURCE_LANDING_PAGE,
    SOURCES,
    SURVEY_VINTAGE,
)

USER_AGENT = "engho-extractor/1"
MAX_SOURCE_BYTES = 512 * 1024 * 1024
MAX_TOTAL_SOURCE_BYTES = 2 * 1024 * 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, destination: Path) -> tuple[int, dict]:
    response = urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=120)
    headers = dict(response.headers.items())
    length = headers.get("Content-Length")
    if length is not None and int(length) > MAX_SOURCE_BYTES:
        response.close()
        raise RuntimeError(f"source exceeds {MAX_SOURCE_BYTES} bytes: {url}")
    downloaded = 0
    try:
        with destination.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                downloaded += len(chunk)
                if downloaded > MAX_SOURCE_BYTES:
                    raise RuntimeError(f"source exceeds {MAX_SOURCE_BYTES} bytes: {url}")
                output.write(chunk)
    finally:
        response.close()
    return downloaded, headers


def retrieve_sources(destination: Path, base_url: str | None = None) -> tuple[Path, Path]:
    """Retrieve the fixed official source set atomically.

    The durable source manifest deliberately excludes retrieval timestamps and HTTP
    response details so identical source bytes yield identical durable provenance.
    Volatile transport evidence is written separately to ``retrieval-run.json``.
    """
    base = (base_url or OFFICIAL_BASE_URL).rstrip("/")
    destination = Path(destination).expanduser().resolve()
    if destination.exists():
        raise FileExistsError(f"destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
    entries, run_entries = [], []
    total = 0
    try:
        for spec in SOURCES:
            url = f"{base}/{spec.filename}"
            target = staging / spec.filename
            size, headers = _download(url, target)
            total += size
            if total > MAX_TOTAL_SOURCE_BYTES:
                raise RuntimeError(f"ENGHo source set exceeds {MAX_TOTAL_SOURCE_BYTES} bytes")
            entries.append({
                "role": spec.role,
                "url": url,
                "filename": spec.filename,
                "bytes": size,
                "sha256": sha256(target),
            })
            run_entries.append({
                "role": spec.role,
                "url": url,
                "transport": {
                    "scheme": urlparse(url).scheme,
                    "content_type": headers.get("Content-Type"),
                    "etag": headers.get("ETag"),
                    "last_modified": headers.get("Last-Modified"),
                },
            })
        manifest = {
            "schema_version": 1,
            "artifact_type": "publicdata.indec-engho-source-set/v1",
            "publisher": "INDEC",
            "dataset_family": DATASET_FAMILY,
            "survey_vintage": SURVEY_VINTAGE,
            "source_landing_page": SOURCE_LANDING_PAGE,
            "documentation": list(DOCUMENTATION),
            "selection_rule": "fixed_explicit_official_2017_18_source_set",
            "sources": entries,
            "tool_version": __version__,
        }
        manifest_path = staging / "source-manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        run = {
            "schema_version": 1,
            "source_manifest_sha256": sha256(manifest_path),
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "sources": run_entries,
        }
        (staging / "retrieval-run.json").write_text(
            json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(staging, destination)
        return destination, destination / "source-manifest.json"
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

"""Fail-closed, bounded EPH discovery and retrieval with source provenance."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .config import load_config
from .extractor import sha256

USER_AGENT = "eph-extractor/1"
MAX_SOURCE_BYTES = 512 * 1024 * 1024
FORMAT_PREFERENCE = ("text", "dbf", "generic")


def candidate_specs(year: int, quarter: str) -> list[tuple[str, str]]:
    """Return bounded official filename variants annotated by transport class.

    Different transport formats for the same quarter are not competing datasets.
    Selection prefers text, then DBF, then the generic archive, while still
    failing closed when more than one filename in the preferred available class
    is simultaneously valid.
    """
    q, yy = quarter[-1], str(year)[-2:]
    specs: list[tuple[str, str]] = [(f"EPH_usu_{q}_Trim_{year}_txt.zip", "text")]
    if year == 2016:
        ordinal = {"1": "1er", "2": "2do", "3": "3er", "4": "4to"}[q]
        specs.append((f"EPH_usu_{ordinal}Trim_{year}_txt.zip", "text"))
    if year == 2017:
        specs.append((f"EPH_usu_{'1er' if q == '1' else q}_Trim_{year}_txt.zip", "text"))
    specs.extend(
        [
            (f"t{q}{yy}_dbf.zip", "dbf"),
            (f"EPH_usu_{q}_Trim_{year}.zip", "generic"),
        ]
    )
    return list(dict.fromkeys(specs))


def candidate_names(year: int, quarter: str) -> list[str]:
    """Compatibility helper returning every bounded filename considered."""
    return [name for name, _ in candidate_specs(year, quarter)]


def _probe(url: str) -> tuple[dict, object | None]:
    record = {"url": url, "status": "rejected", "reason": None}
    try:
        response = urlopen(Request(url, method="HEAD", headers={"User-Agent": USER_AGENT}), timeout=60)
        status = getattr(response, "status", 200)
        length = response.headers.get("Content-Length")
        response.close()
        if status != 200:
            record["reason"] = f"HTTP {status}"
        elif length is not None and int(length) > MAX_SOURCE_BYTES:
            record["reason"] = f"Content-Length exceeds {MAX_SOURCE_BYTES} bytes"
        else:
            record.update(status="available", reason="HTTP HEAD 200", content_length=int(length) if length else None)
    except HTTPError as exc:
        record["reason"] = f"HTTP {exc.code}"
        exc.close()
    except URLError as exc:
        record["reason"] = f"transport error: {exc.reason}"
    return record


def _validate_filename(name: str, year: int, quarter: str) -> None:
    q = quarter[-1]
    modern = re.fullmatch(rf"EPH_usu_(?:{q}|{q}(?:er|do|to))_?Trim_{year}(?:_txt)?\.zip", name, re.I)
    legacy = re.fullmatch(rf"t{q}{str(year)[-2:]}_dbf\.zip", name, re.I)
    if not (modern or legacy):
        raise RuntimeError(f"selected filename does not identify {year}-{quarter}: {name}")


def _select_candidate(considered: list[dict], year: int, quarter: str) -> dict:
    for format_class in FORMAT_PREFERENCE:
        available = [
            item
            for item in considered
            if item["format_class"] == format_class and item["status"] == "available"
        ]
        if not available:
            continue
        if len(available) != 1:
            summary = ", ".join(f"{x['filename']}: {x['reason']}" for x in available)
            raise RuntimeError(
                f"expected exactly one available {format_class} archive for {year}-{quarter}; "
                f"found {len(available)} ({summary})"
            )
        return available[0]
    summary = ", ".join(f"{x['filename']}: {x['reason']}" for x in considered)
    raise RuntimeError(
        f"no available official archive for {year}-{quarter} in governed format preference "
        f"{FORMAT_PREFERENCE} ({summary})"
    )


def retrieve(year: int, quarter: str, destination: Path, base_url: str | None = None):
    quarter = quarter.upper()
    if quarter not in {"Q1", "Q2", "Q3", "Q4"}:
        raise ValueError("quarter must be Q1, Q2, Q3, or Q4")
    base_url = (base_url or load_config()["ftp_url"]).rstrip("/") + "/"
    destination = destination.resolve()
    considered = []
    for name, format_class in candidate_specs(year, quarter):
        record = _probe(base_url + name)
        record["filename"] = name
        record["format_class"] = format_class
        considered.append(record)
    selected = _select_candidate(considered, year, quarter)
    name, url = selected["filename"], selected["url"]
    _validate_filename(name, year, quarter)
    destination.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".download-", dir=destination)
    os.close(fd)
    temp = Path(temporary)
    response = None
    try:
        response = urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=120)
        headers = dict(response.headers.items())
        downloaded = 0
        with temp.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                downloaded += len(chunk)
                if downloaded > MAX_SOURCE_BYTES:
                    raise RuntimeError(f"source exceeds {MAX_SOURCE_BYTES} bytes")
                output.write(chunk)
        archive = destination / name
        os.replace(temp, archive)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    finally:
        if response is not None:
            response.close()
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        commit = None

    # source-manifest.json is deliberately stable for identical source bytes and
    # extractor semantics. Volatile observation details belong to retrieval-run.json
    # so a fresh runner cannot produce different durable bytes under the same release ID.
    source_manifest = {
        "schema_version": 2,
        "publisher": "INDEC",
        "dataset_family": "EPH",
        "requested_year": year,
        "requested_quarter": quarter,
        "resolved_source_url": url,
        "original_filename": name,
        "bytes": archive.stat().st_size,
        "sha256": sha256(archive),
        "retrieval_status": "success",
        "candidate_selection": {
            "rule": "preferred_format_class_then_exactly_one",
            "format_preference": list(FORMAT_PREFERENCE),
            "selected": url,
            "selected_format_class": selected["format_class"],
        },
        "tool_version": __import__("eph_extractor").__version__,
    }
    source_path = destination / "source-manifest.json"
    source_path.write_text(json.dumps(source_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    retrieval_run = {
        "schema_version": 1,
        "source_manifest_sha256": sha256(source_path),
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "transport": {
            "scheme": urlparse(url).scheme,
            "content_type": headers.get("Content-Type"),
            "etag": headers.get("ETag"),
            "last_modified": headers.get("Last-Modified"),
        },
        "candidate_selection": {
            "considered": considered,
        },
        "git_commit": commit,
    }
    (destination / "retrieval-run.json").write_text(
        json.dumps(retrieval_run, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return archive, source_path

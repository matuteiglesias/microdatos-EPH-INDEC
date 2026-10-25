#!/usr/bin/env python3
"""Governed metadata-only receipt: verified EPH candidate transport != approval."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

CONTRACT = "evidence:producer-run-receipt@1"
PRODUCER = "producer.github.eph-release-probe"
REPO = "matuteiglesias/microdatos-EPH-INDEC"
ARTIFACT = "publicdata.eph-microdata@1"
STAGES = ("checks", "target", "probe", "package", "publish")
HEX = re.compile(r"[0-9a-f]{64}\Z")
RELEASE = re.compile(r"eph-[0-9]{4}-q[1-4]-[0-9a-f]{12}\Z")
STATES = {"success", "failed", "skipped", "unknown", "not_applicable"}


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def read(path):
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except (ValueError, OSError):
        return None


def utc(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone-required")
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def step(value):
    return {"success": "success", "failure": "failed", "cancelled": "failed", "skipped": "skipped"}.get(value, "unknown")


def goodhash(value):
    return isinstance(value, str) and HEX.fullmatch(value) is not None


def verify(probe, publication, year, quarter, selection, manual_year, manual_quarter):
    """Inspect producer files and final GitHub download attestation; never serialize raw data."""
    found = {}
    checks = {k: False for k in ("target", "source", "package", "transport")}
    expected_year = int(year) if re.fullmatch(r"\d{4}", year) else None
    override = bool(manual_year or manual_quarter)
    checks["target"] = (expected_year is not None and quarter in ("Q1", "Q2", "Q3", "Q4")
                        and selection == ("manual_override" if override else "lag_130d")
                        and (not override or (manual_year == year and manual_quarter.upper() == quarter)))
    if not checks["target"]:
        # An early failed/aborted resolution is absence, not a false artifact verdict.
        missing_target = expected_year is None or quarter not in ("Q1", "Q2", "Q3", "Q4")
        return ("missing" if missing_target else "invalid"), checks, found
    discovery = read(publication / "discovery.json")
    source = read(probe / ".source/source-manifest.json")
    release_id = discovery.get("release_id") if discovery else None
    valid_id = (isinstance(release_id, str) and RELEASE.fullmatch(release_id)
                and release_id.startswith(f"eph-{year}-{quarter.lower()}-"))
    output_path = probe / release_id / "output-manifest.json" if valid_id else None
    output = read(output_path) if output_path else None
    if valid_id:
        found["release_id"] = release_id
    if source and output:
        filename = source.get("original_filename")
        archive = (probe / ".source" / filename if isinstance(filename, str)
                   and filename == Path(filename).name and filename not in (".", "..") else None)
        archive_sha = sha(archive) if archive and archive.is_file() else None
        source_sha = sha(probe / ".source/source-manifest.json")
        checks["source"] = all((
            source.get("schema_version") == 2,
            source.get("publisher") == "INDEC",
            source.get("dataset_family") == "EPH",
            source.get("retrieval_status") == "success",
            source.get("requested_year") == expected_year,
            source.get("requested_quarter") == quarter,
            goodhash(source.get("sha256")),
            archive_sha is not None and source.get("sha256") == archive_sha,
            output.get("source_archive_sha256") == archive_sha,
            output.get("source_manifest_sha256") == source_sha,
            output.get("requested_year") == expected_year,
            output.get("requested_quarter") == quarter,
            output.get("release_id") == release_id,
        ))
        if checks["source"]:
            found.update(source_archive_sha256=archive_sha, source_manifest_sha256=source_sha,
                         output_manifest_sha256=sha(output_path))
    if checks["source"] and discovery:
        github = discovery.get("github_release")
        src = discovery.get("source")
        asset_name = github.get("asset_name") if isinstance(github, dict) else None
        asset = publication / asset_name if isinstance(asset_name, str) and asset_name == Path(asset_name).name else None
        asset_sha = sha(asset) if asset and asset.is_file() else None
        checks["package"] = all((
            discovery.get("schema") == "ecosystem-release-discovery/v1",
            discovery.get("producer") == REPO, discovery.get("artifact_type") == ARTIFACT,
            discovery.get("status") == "candidate",
            discovery.get("period") == {"year": expected_year, "quarter": quarter},
            isinstance(src, dict) and src.get("publisher") == "INDEC",
            isinstance(src, dict) and src.get("dataset_family") == "EPH",
            isinstance(src, dict) and src.get("original_filename") == source.get("original_filename"),
            isinstance(src, dict) and src.get("source_archive_sha256") == found["source_archive_sha256"],
            isinstance(src, dict) and src.get("source_manifest_sha256") == found["source_manifest_sha256"],
            isinstance(github, dict) and github.get("tag") == f"candidate-{release_id}",
            isinstance(github, dict) and asset_name == f"{release_id}.zip",
            isinstance(github, dict) and github.get("manifest_sha256") == found["output_manifest_sha256"],
            isinstance(github, dict) and github.get("asset_sha256") == asset_sha,
            goodhash(asset_sha),
        ))
        if checks["package"]:
            found.update(asset_sha256=asset_sha, discovery_sha256=sha(publication / "discovery.json"),
                         tag=github["tag"])
    transport = read(publication / "transport-verified.json")
    checks["transport"] = bool(checks["package"] and transport and all((
        transport.get("schema") == "eph-candidate-transport-verification/v1",
        transport.get("status") == "verified",
        transport.get("verification") == "github_download_cmp",
        transport.get("prerelease") is True,
        transport.get("release_id") == release_id,
        transport.get("tag") == found.get("tag"),
        transport.get("asset_sha256") == found.get("asset_sha256"),
        transport.get("discovery_sha256") == found.get("discovery_sha256"),
    )))
    if checks["transport"]:
        return "valid", checks, found
    if (source and output and not checks["source"]) or (discovery and not checks["package"]) or transport:
        return "invalid", checks, found
    return ("partial" if source or output or discovery else "missing"), checks, found


def validate_receipt(receipt):
    if receipt["contract"] != CONTRACT or receipt["producer_id"] != PRODUCER:
        raise ValueError("invalid contract")
    if set(receipt["stages"]) != set(STAGES) or not set(receipt["stages"].values()) <= STATES:
        raise ValueError("invalid stages")
    if len(receipt["outputs"]) != 1 or receipt["outputs"][0]["type"] != ARTIFACT or receipt["outputs"][0]["durability"] != "candidate_release":
        raise ValueError("invalid output")
    if set(receipt["result"]) != {"scheduler_state", "execution_state", "artifact_state", "terminal_state", "authority_state"}:
        raise ValueError("invalid axes")
    if receipt["trigger"] not in {"schedule", "manual", "event"}:
        raise ValueError("invalid trigger")
    allowed_health = {"healthy", "degraded", "failed", "unknown", "not_applicable"}
    if any(receipt["result"][k] not in allowed_health for k in
           ("scheduler_state", "execution_state", "terminal_state")):
        raise ValueError("invalid health state")
    if receipt["result"]["artifact_state"] not in allowed_health | {"stale"}:
        raise ValueError("invalid artifact health")
    if receipt["result"]["authority_state"] not in {"candidate", "unknown"}:
        raise ValueError("invalid candidate authority")
    if receipt["outputs"][0]["state"] not in {"valid", "invalid", "partial", "missing", "unknown"}:
        raise ValueError("invalid output state")
    if utc(receipt["started_at"]) > utc(receipt["finished_at"]):
        raise ValueError("inconsistent run boundaries")
    raw = json.dumps(receipt, sort_keys=True).lower()
    for forbidden in ("/home/", "/users/", "\\users\\", '"command"', '"environment"', '"token"', '"secret"', "api_key", "password", "source_payload", "raw_rows", "p47t"):
        if forbidden in raw:
            raise ValueError("unsafe receipt")


def make_receipt(args):
    run, attempt = str(args.scheduler_run_id), str(args.run_attempt)
    if not re.fullmatch(r"\d+", run) or not re.fullmatch(r"[1-9]\d*", attempt):
        raise ValueError("invalid run identity")
    trigger = {"schedule": "schedule", "workflow_dispatch": "manual"}.get(args.event_name, "event")
    out, checks, found = verify(args.probe_dir, args.publication_dir, args.year, args.quarter,
                                args.selection, args.manual_year, args.manual_quarter)
    stages = {k: step(getattr(args, "step_" + k)) for k in STAGES}
    for stage_name, check_name in (("target", "target"), ("probe", "source"),
                                   ("package", "package"), ("publish", "transport")):
        if stages[stage_name] == "success" and not checks[check_name]:
            stages[stage_name] = "failed" if out == "invalid" else "unknown"
    if out == "valid" and stages["publish"] != "success":
        out = "invalid"
    artifact = {"valid": "healthy", "invalid": "failed", "partial": "degraded", "missing": "unknown"}[out]
    execution = {"success": "healthy", "failure": "failed", "cancelled": "degraded"}.get(args.job_status, "unknown")
    terminal = ("failed" if "failed" in (execution, artifact) else
                "healthy" if execution == artifact == "healthy" else
                "degraded" if "degraded" in (execution, artifact) else "unknown")
    refs = [f"https://github.com/{REPO}/actions/runs/{run}/attempts/{attempt}"]
    for name in ("source_archive_sha256", "source_manifest_sha256", "output_manifest_sha256", "asset_sha256"):
        if goodhash(found.get(name)):
            refs.append(f"eph:{name}:sha256:{found[name]}")
    release_url = f"https://github.com/{REPO}/releases/tag/{found['tag']}" if out == "valid" else None
    if release_url:
        refs.append(release_url)
    inputs = []
    if re.fullmatch(r"\d{4}", args.year) and args.quarter in {"Q1", "Q2", "Q3", "Q4"}:
        inputs.append({"ref": f"eph-period:{args.year}-{args.quarter}", "version": args.selection})
    warnings = [f"{key}: {value}" for key, value in stages.items() if value != "success"]
    if out != "valid":
        warnings.append(f"candidate evidence: {out}")
    if execution != "healthy":
        warnings.append(f"workflow execution: {execution}")
    receipt = {
        "contract": CONTRACT, "run_id": f"github-actions:{REPO}:{run}:{attempt}",
        "producer_id": PRODUCER, "scheduler_run_id": run, "trigger": trigger,
        "started_at": utc(args.started_at), "finished_at": utc(args.finished_at),
        "inputs": inputs, "stages": stages,
        "outputs": [{"type": ARTIFACT, "state": out, "durability": "candidate_release", "ref": release_url}],
        "result": {"scheduler_state": "healthy" if trigger in ("schedule", "manual") else "unknown",
                   "execution_state": execution, "artifact_state": artifact,
                   "terminal_state": terminal, "authority_state": "candidate" if out == "valid" else "unknown"},
        "warnings": warnings, "evidence_refs": refs,
    }
    validate_receipt(receipt)
    return receipt


def main():
    p = argparse.ArgumentParser()
    for name in ("scheduler-run-id", "run-attempt", "event-name", "job-status", "started-at",
                 "finished-at", "year", "quarter", "selection", "step-checks", "step-target",
                 "step-probe", "step-package", "step-publish"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--manual-year", default="")
    p.add_argument("--manual-quarter", default="")
    p.add_argument("--probe-dir", required=True, type=Path)
    p.add_argument("--publication-dir", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    receipt = make_receipt(a)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": receipt["run_id"], "output_state": receipt["outputs"][0]["state"],
                      "artifact_state": receipt["result"]["artifact_state"]}, sort_keys=True))


if __name__ == "__main__":
    main()

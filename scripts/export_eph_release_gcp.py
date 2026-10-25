#!/usr/bin/env python3
"""Keyless, allowlisted Cloud Logging projection of an EPH semantic receipt."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from emit_eph_release_receipt import ARTIFACT, CONTRACT, PRODUCER, REPO, STAGES, validate_receipt

PROJECT = "estate-observability-510700"
LOG_ID = "estate-producer-run"
ENDPOINT = "https://logging.googleapis.com/v2/entries:write"
SCOPE = "https://www.googleapis.com/auth/logging.write"
HEX = r"[a-f0-9]{64}"
REF = re.compile(r"^eph:(?:source_archive_sha256|source_manifest_sha256|output_manifest_sha256|asset_sha256):sha256:"+HEX+r"$")
RUN = re.compile(r"^[0-9]+$")
ATTEMPT = re.compile(r"^[1-9][0-9]*$")
RESULT_KEYS = {"scheduler_state", "execution_state", "artifact_state", "terminal_state", "authority_state"}


class ExportError(ValueError):
    pass


def require(condition, msg):
    if not condition:
        raise ExportError(msg)


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate_for_export(receipt, run_id, attempt):
    try:
        validate_receipt(receipt)
    except (ValueError, KeyError, TypeError) as e:
        raise ExportError("invalid receipt") from e
    require(RUN.fullmatch(run_id) is not None and ATTEMPT.fullmatch(attempt) is not None, "invalid run identity")
    require(set(receipt) == {"contract", "producer_id", "run_id", "scheduler_run_id", "trigger",
                            "started_at", "finished_at", "inputs", "stages", "outputs", "result",
                            "evidence_refs", "warnings"}, "unsafe receipt keys")
    require(receipt["run_id"] == f"github-actions:{REPO}:{run_id}:{attempt}"
            and receipt["scheduler_run_id"] == run_id, "mismatched run attempt")
    require(receipt["trigger"] in ("schedule", "manual"), "untrusted event")
    require(set(receipt["stages"]) == set(STAGES), "invalid stage set")
    require(set(receipt["result"]) == RESULT_KEYS, "invalid result")
    require(len(receipt["inputs"]) <= 1, "invalid input count")
    for item in receipt["inputs"]:
        require(set(item) == {"ref", "version"}, "invalid input fields")
        require(re.fullmatch(r"eph-period:\d{4}-Q[1-4]", item["ref"]) is not None, "invalid period")
        require(item["version"] in ("manual_override", "lag_130d"), "invalid selection")
    output = receipt["outputs"][0]
    require(set(output) == {"type", "state", "durability", "ref"} and output["type"] == ARTIFACT,
            "invalid output shape")
    require(output["state"] in ("valid", "invalid", "partial", "missing"), "invalid output state")
    if output["state"] == "valid":
        require(isinstance(output["ref"], str) and re.fullmatch(
            rf"https://github\.com/{REPO}/releases/tag/candidate-eph-\d{{4}}-q[1-4]-[0-9a-f]{{12}}", output["ref"]) is not None,
            "invalid release reference")
        require(receipt["result"]["authority_state"] == "candidate", "invalid candidate authority")
    else:
        require(output["ref"] is None and receipt["result"]["authority_state"] == "unknown",
                "unverified output claimed authority")
    refs = receipt["evidence_refs"]
    require(isinstance(refs, list) and 1 <= len(refs) <= 6 and
            refs[0] == f"https://github.com/{REPO}/actions/runs/{run_id}/attempts/{attempt}",
            "invalid evidence anchors")
    require(all(REF.fullmatch(x) or x == output["ref"] for x in refs[1:]), "unsafe evidence reference")
    warnings = receipt["warnings"]
    require(isinstance(warnings, list) and len(warnings) <= 8, "invalid warning count")
    require(all(isinstance(w, str) and re.fullmatch(
        r"(?:checks|target|probe|package|publish): (?:failed|unknown|skipped|not_applicable)|"
        r"candidate evidence: (?:invalid|partial|missing)|"
        r"workflow execution: (?:failed|degraded|unknown)", w) for w in warnings),
        "unexpected warning payload")
    raw = canonical_json(receipt).lower()
    for fragment in ("/home/", "/users/", "\\users\\", '"command"', '"cwd"', '"environment"',
                     '"token"', '"secret"', "api_key", "password", "source_payload", "raw_rows"):
        require(fragment not in raw, "unsafe private receipt content")


def build_entry(receipt, run_id, attempt):
    validate_for_export(receipt, run_id, attempt)
    receipt_sha = hashlib.sha256(canonical_json(receipt).encode("utf-8")).hexdigest()
    identity = {"producer_id": receipt["producer_id"], "run_id": receipt["run_id"],
                "receipt_sha256": receipt_sha}
    insert_id = hashlib.sha256(canonical_json(identity).encode("utf-8")).hexdigest()
    states = {receipt["result"][k] for k in ("execution_state", "artifact_state", "terminal_state")}
    severity = "ERROR" if "failed" in states else "WARNING" if states & {"degraded", "unknown"} else "INFO"
    return {
        "logName": f"projects/{PROJECT}/logs/{LOG_ID}",
        "resource": {"type": "global", "labels": {"project_id": PROJECT}},
        "timestamp": receipt["finished_at"], "severity": severity, "insertId": insert_id,
        "labels": {"producer_id": PRODUCER, "receipt_sha256": receipt_sha, "source_contract": CONTRACT},
        "jsonPayload": {
            "contract": CONTRACT, "receipt": receipt, "receipt_sha256": receipt_sha,
            "logical_receipt_id": f"{PRODUCER}:{receipt['run_id']}",
            "producer": {"producer_id": PRODUCER, "owner": "repo.microdatos-EPH-INDEC",
                         "scheduler_kind": "github_actions", "observation_mode": "semantic_receipt",
                         "authority_state": receipt["result"]["authority_state"]},
        },
    }


def write(session, entry, dry_run):
    body = {"logName": entry["logName"], "resource": entry["resource"],
            "entries": [entry], "partialSuccess": False}
    res = session.post(ENDPOINT, params={"dryRun": "true"} if dry_run else None,
                       json=body, timeout=30)
    if not res.ok:
        raise ExportError(f"Cloud Logging entries.write HTTP {res.status_code}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--scheduler-run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        entry = build_entry(receipt, args.scheduler_run_id, args.run_attempt)
        if args.write:
            try:
                import google.auth
                from google.auth.transport.requests import AuthorizedSession
                creds, _ = google.auth.default(scopes=[SCOPE])
                session = AuthorizedSession(creds)
            except Exception as exc:
                raise ExportError("keyless credentials unavailable") from exc
            write(session, entry, dry_run=True)
            write(session, entry, dry_run=False)
        print(json.dumps({"producer_id": PRODUCER, "insert_id": entry["insertId"],
                          "mode": "exported" if args.write else "validated"}, sort_keys=True))
        return 0
    except (ExportError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"EPH receipt export failed: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

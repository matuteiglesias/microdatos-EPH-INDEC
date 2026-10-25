import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from emit_eph_release_receipt import make_receipt, sha, validate_receipt
from export_eph_release_gcp import build_entry, validate_for_export, ExportError
from eph_extractor.publication import package_candidate
from eph_extractor.extractor import publish_release
from test_publication import PublicationTests


class ReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        PublicationTests.setUpClass()
        cls.fixtures = PublicationTests.fixtures

    @classmethod
    def tearDownClass(cls):
        PublicationTests.tearDownClass()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.probe = self.root / "probe"
        self.pub = self.root / "publication"
        self.probe.mkdir()
        self.pub.mkdir()
        self.args = argparse.Namespace(
            scheduler_run_id="39285486370", run_attempt="1", event_name="schedule",
            job_status="success", started_at="2026-10-19T09:17:00Z",
            finished_at="2026-10-19T09:19:00Z", year="2024", quarter="Q3",
            selection="lag_130d", manual_year="", manual_quarter="",
            probe_dir=self.probe, publication_dir=self.pub,
            step_checks="success", step_target="success", step_probe="success",
            step_package="success", step_publish="success",
        )

    def prepare_candidate(self, year=2024, quarter="Q3"):
        source_root = self.root / "build"
        source_root.mkdir()
        release, source_dir = PublicationTests.make_candidate(self, source_root)
        if (year, quarter) != (2024, "Q3"):
            manifest_file = source_dir / "source-manifest.json"
            manifest = json.loads(manifest_file.read_text())
            old_archive = source_dir / manifest["original_filename"]
            new_archive = source_dir / f"EPH_usu_{quarter[1]}_Trim_{year}_txt.zip"
            old_archive.rename(new_archive)
            manifest.update(original_filename=new_archive.name, requested_year=year,
                            requested_quarter=quarter)
            manifest_file.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            release = publish_release(new_archive, source_root / "releases-new",
                                      year, quarter, manifest_file, "eph-extractor release")
            self.args.year, self.args.quarter = str(year), quarter
        (self.probe / ".source").mkdir()
        for f in source_dir.iterdir():
            (self.probe / ".source" / f.name).write_bytes(f.read_bytes())
        dest = self.probe / release.name
        dest.mkdir()
        for f in release.rglob("*"):
            if f.is_file():
                out = dest / f.relative_to(release)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(f.read_bytes())
        package_candidate(dest, self.probe / ".source", self.pub)
        doc = json.loads((self.pub / "discovery.json").read_text())
        self.attest(doc)

    def attest(self, discovery):
        (self.pub / "transport-verified.json").write_text(json.dumps({
            "schema": "eph-candidate-transport-verification/v1", "status": "verified",
            "verification": "github_download_cmp", "prerelease": True,
            "release_id": discovery["release_id"], "tag": discovery["github_release"]["tag"],
            "asset_sha256": sha(self.pub / discovery["github_release"]["asset_name"]),
            "discovery_sha256": sha(self.pub / "discovery.json"),
        }) + "\n")

    def test_real_like_2026_q1_official_period(self):
        self.prepare_candidate(2026, "Q1")
        receipt = make_receipt(self.args)
        self.assertEqual(receipt["outputs"][0]["state"], "valid")
        self.assertEqual(receipt["inputs"][0]["ref"], "eph-period:2026-Q1")

    def test_valid_candidate_and_replay(self):
        self.prepare_candidate()
        first = make_receipt(self.args)
        self.assertEqual(first["outputs"][0]["state"], "valid")
        self.assertEqual(first["result"]["artifact_state"], "healthy")
        self.assertEqual(first["result"]["authority_state"], "candidate")
        self.assertEqual(first, make_receipt(self.args))
        a = build_entry(first, self.args.scheduler_run_id, self.args.run_attempt)
        self.assertEqual(a["insertId"], build_entry(make_receipt(self.args), "39285486370", "1")["insertId"])
        self.assertEqual(a["logName"], "projects/estate-observability-510700/logs/estate-producer-run")
        self.assertNotIn("/home/", json.dumps(a))

    def test_manual_override_correct_and_mismatch(self):
        self.prepare_candidate()
        self.args.event_name = "workflow_dispatch"
        self.args.selection = "manual_override"
        self.args.manual_year, self.args.manual_quarter = "2024", "Q3"
        self.assertEqual(make_receipt(self.args)["outputs"][0]["state"], "valid")
        self.args.manual_quarter = "Q2"
        self.assertEqual(make_receipt(self.args)["result"]["artifact_state"], "failed")

    def test_archive_drift(self):
        self.prepare_candidate()
        name = json.loads((self.probe / ".source/source-manifest.json").read_text())["original_filename"]
        with (self.probe / ".source" / name).open("ab") as out:
            out.write(b"drift")
        receipt = make_receipt(self.args)
        self.assertEqual(receipt["outputs"][0]["state"], "invalid")
        self.assertEqual(receipt["stages"]["probe"], "failed")

    def test_source_manifest_drift(self):
        self.prepare_candidate()
        with (self.probe / ".source/source-manifest.json").open("ab") as out:
            out.write(b"\n")
        self.assertEqual(make_receipt(self.args)["outputs"][0]["state"], "invalid")

    def test_existing_published_bytes_verification(self):
        self.prepare_candidate()
        original = make_receipt(self.args)
        self.attest(json.loads((self.pub / "discovery.json").read_text()))
        self.assertEqual(original, make_receipt(self.args))

    def test_release_asset_missing_or_mismatch(self):
        self.prepare_candidate()
        doc = json.loads((self.pub / "discovery.json").read_text())
        asset = self.pub / doc["github_release"]["asset_name"]
        asset.unlink()
        self.assertEqual(make_receipt(self.args)["outputs"][0]["state"], "invalid")

    def test_failed_remote_transport(self):
        self.prepare_candidate()
        (self.pub / "transport-verified.json").unlink()
        self.args.step_publish = "failure"
        self.args.job_status = "failure"
        receipt = make_receipt(self.args)
        self.assertNotEqual(receipt["outputs"][0]["state"], "valid")
        self.assertEqual(receipt["result"]["execution_state"], "failed")
        self.assertIsNone(receipt["outputs"][0]["ref"])

    def test_packaging_missing_after_verified_retrieval(self):
        self.prepare_candidate()
        (self.pub / "discovery.json").unlink()
        (self.pub / "transport-verified.json").unlink()
        self.args.step_package = "failure"
        self.args.step_publish = "skipped"
        self.args.job_status = "failure"
        receipt = make_receipt(self.args)
        self.assertEqual(receipt["outputs"][0]["state"], "partial")
        self.assertEqual(receipt["stages"]["probe"], "success")
        self.assertEqual(receipt["stages"]["package"], "failed")
        self.assertEqual(receipt["result"]["artifact_state"], "degraded")

    def test_missing_unknown_source_and_early_failure(self):
        self.args.year, self.args.quarter, self.args.selection = "", "", ""
        self.args.step_checks = "failure"
        self.args.step_target = "skipped"
        self.args.step_probe = "skipped"
        self.args.step_package = "skipped"
        self.args.step_publish = "skipped"
        self.args.job_status = "failure"
        receipt = make_receipt(self.args)
        self.assertNotEqual(receipt["outputs"][0]["state"], "valid")
        self.assertEqual(receipt["result"]["execution_state"], "failed")

    def test_privacy_and_export_allowlist(self):
        self.prepare_candidate()
        receipt = make_receipt(self.args)
        receipt["warnings"].append("/home/user/secret")
        with self.assertRaises((ExportError, ValueError)):
            validate_for_export(receipt, "39285486370", "1")
        receipt = make_receipt(self.args)
        receipt["raw_microdata_rows"] = ["private"]
        with self.assertRaises((ExportError, ValueError)):
            validate_for_export(receipt, "39285486370", "1")
        receipt = make_receipt(self.args)
        with self.assertRaises(ExportError):
            validate_for_export(receipt, "39285486370", "2")

    def test_changed_candidate_transport_not_upgradeable(self):
        self.prepare_candidate()
        att = json.loads((self.pub / "transport-verified.json").read_text())
        att["asset_sha256"] = "a" * 64
        (self.pub / "transport-verified.json").write_text(json.dumps(att))
        receipt = make_receipt(self.args)
        self.assertEqual(receipt["outputs"][0]["state"], "invalid")
        self.assertEqual(receipt["result"]["authority_state"], "unknown")


if __name__ == "__main__":
    unittest.main()

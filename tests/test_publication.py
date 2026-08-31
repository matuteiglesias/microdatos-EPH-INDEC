import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from fixture_factory import create_fixtures

from eph_extractor.extractor import publish_release, sha256
from eph_extractor.publication import package_candidate


class PublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_temp = tempfile.TemporaryDirectory()
        cls.fixtures = create_fixtures(Path(cls.fixture_temp.name))

    @classmethod
    def tearDownClass(cls):
        cls.fixture_temp.cleanup()

    def make_candidate(self, root: Path):
        source = root / "source"
        source.mkdir()
        archive = source / "EPH_usu_3_Trim_2024_txt.zip"
        archive.write_bytes((self.fixtures / "modern_nested.zip").read_bytes())
        source_manifest = {
            "schema_version": 2,
            "publisher": "INDEC",
            "dataset_family": "EPH",
            "requested_year": 2024,
            "requested_quarter": "Q3",
            "resolved_source_url": "https://example.invalid/EPH_usu_3_Trim_2024_txt.zip",
            "original_filename": archive.name,
            "bytes": archive.stat().st_size,
            "sha256": sha256(archive),
            "retrieval_status": "success",
            "candidate_selection": {
                "rule": "preferred_format_class_then_exactly_one",
                "format_preference": ["text", "dbf", "generic"],
                "selected": "https://example.invalid/EPH_usu_3_Trim_2024_txt.zip",
                "selected_format_class": "text",
            },
            "tool_version": "1.0.0",
        }
        source_manifest_path = source / "source-manifest.json"
        source_manifest_path.write_text(json.dumps(source_manifest, indent=2, sort_keys=True) + "\n")
        releases = root / "releases"
        release = publish_release(archive, releases, 2024, "Q3", source_manifest_path, "eph-extractor release")
        return release, source

    def test_package_is_deterministic_and_self_describing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release, source = self.make_candidate(root)
            first = package_candidate(release, source, root / "publication-a")
            second = package_candidate(release, source, root / "publication-b")
            self.assertEqual(sha256(Path(first["asset"])), sha256(Path(second["asset"])))
            self.assertEqual(Path(first["discovery"]).read_bytes(), Path(second["discovery"]).read_bytes())
            discovery = json.loads(Path(first["discovery"]).read_text())
            self.assertEqual(discovery["artifact_type"], "publicdata.eph-microdata@1")
            self.assertEqual(discovery["status"], "candidate")
            self.assertEqual(discovery["period"], {"year": 2024, "quarter": "Q3"})
            self.assertEqual(discovery["github_release"]["asset_sha256"], sha256(Path(first["asset"])))
            with zipfile.ZipFile(first["asset"]) as zf:
                names = sorted(zf.namelist())
                prefix = release.name + "/"
                self.assertIn(prefix + "output-manifest.json", names)
                self.assertIn(prefix + "_source/source-manifest.json", names)
                self.assertIn(prefix + "_source/EPH_usu_3_Trim_2024_txt.zip", names)
                self.assertTrue(any(name.startswith(prefix + "household/") for name in names))
                self.assertTrue(any(name.startswith(prefix + "individual/") for name in names))

    def test_rejects_source_manifest_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release, source = self.make_candidate(root)
            manifest_path = source / "source-manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["resolved_source_url"] = "https://example.invalid/changed.zip"
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            with self.assertRaisesRegex(ValueError, "source_manifest_checksum_mismatch"):
                package_candidate(release, source, root / "publication")

    def test_rejects_source_archive_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release, source = self.make_candidate(root)
            archive = source / "EPH_usu_3_Trim_2024_txt.zip"
            archive.write_bytes(archive.read_bytes() + b"drift")
            with self.assertRaisesRegex(ValueError, "source_archive_checksum_mismatch"):
                package_candidate(release, source, root / "publication")


if __name__ == "__main__":
    unittest.main()

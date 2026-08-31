import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

from fixture_factory import create_fixtures

from eph_extractor.downloader import candidate_names, candidate_specs, retrieve
from eph_extractor.extractor import publish_release

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


class ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_temp = tempfile.TemporaryDirectory()
        cls.fixtures = create_fixtures(Path(cls.fixture_temp.name))

    @classmethod
    def tearDownClass(cls):
        cls.fixture_temp.cleanup()

    def _serve(self, served):
        handler = lambda *args, **kwargs: QuietHandler(*args, directory=served, **kwargs)
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def test_modern_nested_dbf_latin1_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = publish_release(self.fixtures / "modern_nested.zip", root, 2024, "Q3")
            self.assertEqual(first, publish_release(self.fixtures / "modern_nested.zip", root, 2024, "q3"))
            manifest = json.loads((first / "output-manifest.json").read_text())
            self.assertEqual([item["role"] for item in manifest["files"]], ["household", "individual"])
            self.assertEqual(manifest["files"][0]["period"], "2024-Q3")
            self.assertTrue(manifest["files"][0]["schema_hash"])
            self.assertEqual(manifest["files"][0]["rows"], 2)
            self.assertIn("José", (first / "household" / "usu_hogar_t324.txt").read_text())
            self.assertFalse(any(path.name.startswith(".") for path in root.iterdir()))

    def test_irregular_name_candidates(self):
        self.assertIn("EPH_usu_2doTrim_2016_txt.zip", candidate_names(2016, "Q2"))
        with tempfile.TemporaryDirectory() as tmp:
            release = publish_release(self.fixtures / "irregular_2016.zip", Path(tmp), 2016, "Q2")
            self.assertTrue((release / "individual" / "usu_individual_ind_t216.txt").exists())

    def test_failure_is_atomic(self):
        for fixture in ("corrupt.zip", "duplicate.zip"):
            with self.subTest(fixture=fixture), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError):
                    publish_release(self.fixtures / fixture, Path(tmp), 2024, "Q3")
                self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_rejects_nested_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "nested.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("payload.zip", b"nested")
            out = Path(tmp) / "out"
            with self.assertRaisesRegex(ValueError, "nested archive"):
                publish_release(archive, out, 2026, "Q1")
            self.assertEqual(list(out.iterdir()), [])

    def test_multiple_official_formats_prefer_text_candidate(self):
        with tempfile.TemporaryDirectory() as served, tempfile.TemporaryDirectory() as downloaded:
            for name in candidate_names(2026, "Q1"):
                (Path(served) / name).write_bytes((self.fixtures / "modern_nested.zip").read_bytes())
            server, thread = self._serve(served)
            try:
                base_url = f"http://127.0.0.1:{server.server_port}/"
                archive, manifest_path = retrieve(2026, "Q1", Path(downloaded), base_url)
            finally:
                server.shutdown(); thread.join(); server.server_close()
            self.assertEqual(archive.name, "EPH_usu_1_Trim_2026_txt.zip")
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["candidate_selection"]["rule"], "preferred_format_class_then_exactly_one")
            self.assertEqual(manifest["candidate_selection"]["selected_format_class"], "text")
            self.assertEqual(manifest["candidate_selection"]["format_preference"], ["text", "dbf", "generic"])
            self.assertEqual(len(manifest["candidate_selection"]["considered"]), 3)

    def test_same_preference_class_remains_fail_closed(self):
        with tempfile.TemporaryDirectory() as served, tempfile.TemporaryDirectory() as downloaded:
            text_names = [name for name, kind in candidate_specs(2016, "Q2") if kind == "text"]
            self.assertEqual(len(text_names), 2)
            for name in text_names:
                (Path(served) / name).write_bytes((self.fixtures / "modern_nested.zip").read_bytes())
            server, thread = self._serve(served)
            try:
                with self.assertRaisesRegex(RuntimeError, "exactly one available text archive.*found 2"):
                    retrieve(2016, "Q2", Path(downloaded), f"http://127.0.0.1:{server.server_port}/")
            finally:
                server.shutdown(); thread.join(); server.server_close()
            self.assertEqual(list(Path(downloaded).iterdir()), [])

    def test_dbf_is_bounded_fallback_when_text_absent(self):
        with tempfile.TemporaryDirectory() as served, tempfile.TemporaryDirectory() as downloaded:
            dbf_name = next(name for name, kind in candidate_specs(2026, "Q1") if kind == "dbf")
            generic_name = next(name for name, kind in candidate_specs(2026, "Q1") if kind == "generic")
            for name in (dbf_name, generic_name):
                (Path(served) / name).write_bytes((self.fixtures / "modern_nested.zip").read_bytes())
            server, thread = self._serve(served)
            try:
                archive, manifest_path = retrieve(
                    2026,
                    "Q1",
                    Path(downloaded),
                    f"http://127.0.0.1:{server.server_port}/",
                )
            finally:
                server.shutdown(); thread.join(); server.server_close()
            self.assertEqual(archive.name, dbf_name)
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["candidate_selection"]["selected_format_class"], "dbf")


if __name__ == "__main__":
    unittest.main()

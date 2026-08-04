import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

from fixture_factory import create_fixtures

from eph_extractor.downloader import candidate_names, retrieve
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

    def test_discovers_and_downloads_exactly_one_2026_q1_candidate(self):
        with tempfile.TemporaryDirectory() as served, tempfile.TemporaryDirectory() as downloaded:
            source_name = "EPH_usu_1_Trim_2026_txt.zip"
            (Path(served) / source_name).write_bytes((self.fixtures / "modern_nested.zip").read_bytes())
            handler = lambda *args, **kwargs: QuietHandler(*args, directory=served, **kwargs)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}/"
                archive, manifest_path = retrieve(2026, "Q1", Path(downloaded), base_url)
            finally:
                server.shutdown()
                thread.join()
                server.server_close()
            self.assertEqual(archive.name, source_name)
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["resolved_source_url"], base_url + source_name)
            self.assertEqual(manifest["candidate_selection"]["rule"], "exactly_one_HEAD_200")
            self.assertEqual(len(manifest["candidate_selection"]["considered"]), 3)

    def test_discovery_fails_closed_on_ambiguous_candidates(self):
        with tempfile.TemporaryDirectory() as served, tempfile.TemporaryDirectory() as downloaded:
            for name in candidate_names(2026, "Q1")[:2]:
                (Path(served) / name).write_bytes((self.fixtures / "modern_nested.zip").read_bytes())
            handler = lambda *args, **kwargs: QuietHandler(*args, directory=served, **kwargs)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with self.assertRaisesRegex(RuntimeError, "found 2"):
                    retrieve(2026, "Q1", Path(downloaded), f"http://127.0.0.1:{server.server_port}/")
            finally:
                server.shutdown()
                thread.join()
                server.server_close()
            self.assertEqual(list(Path(downloaded).iterdir()), [])


if __name__ == "__main__":
    unittest.main()

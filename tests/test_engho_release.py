import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import tempfile
import threading
import unittest
from pathlib import Path

from engho_fixture_factory import create_bad_archive, create_engho_sources
from engho_extractor.contracts import REQUIRED_ROLES
from engho_extractor.downloader import retrieve_sources
from engho_extractor.extractor import publish_release
from engho_extractor.validator import commission_release, validate_release


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


class EnghoReleaseTests(unittest.TestCase):
    def _serve(self, directory):
        handler = lambda *args, **kwargs: QuietHandler(*args, directory=directory, **kwargs)
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def test_deterministic_release_identity_inventory_and_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = create_engho_sources(root / "source")
            releases = root / "releases"
            first = publish_release(source, releases)
            second = publish_release(source, releases)
            self.assertEqual(first, second)
            result = validate_release(first)
            self.assertEqual(result["status"], "pass")
            manifest = json.loads((first / "output-manifest.json").read_text())
            self.assertEqual(manifest["artifact_type"], "publicdata.indec-engho-microdata/v1")
            self.assertFalse(manifest["scientific_transformations_performed"])
            self.assertEqual({x["role"] for x in manifest["files"]}, set(REQUIRED_ROLES))
            households = next(x for x in manifest["files"] if x["role"] == "households")
            self.assertIn("id", [x.casefold() for x in households["column_names"]])
            self.assertEqual(households["normalized_filename"], "households.txt")
            self.assertTrue(households["schema_hash"])

    def test_cross_table_identity_columns_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release = publish_release(create_engho_sources(root / "source"), root / "releases")
            manifest = json.loads((release / "output-manifest.json").read_text())
            by_role = {x["role"]: x for x in manifest["files"]}
            self.assertEqual(by_role["households"]["column_names"][:1], ["id"])
            self.assertEqual(by_role["persons"]["column_names"][:2], ["id", "miembro"])
            self.assertEqual(by_role["articles"]["column_names"][:1], ["articulo"])
            self.assertEqual(by_role["replicate_weights"]["column_names"][:1], ["id"])
            self.assertEqual(
                by_role["expenditures"]["column_names"][:7],
                ["id", "miembro", "articulo", "forma_pago", "tipo_negocio", "modo_adq", "lugar_adq"],
            )

    def test_failures_publish_nothing(self):
        for kind in ("traversal", "duplicate", "unsupported", "corrupt"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = create_bad_archive(root / "source", kind)
                out = root / "releases"
                with self.assertRaises(ValueError):
                    publish_release(source, out)
                self.assertEqual(list(out.iterdir()), [])

    def test_source_checksum_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = create_engho_sources(root / "source")
            path = source / "engho2018_hogares.zip"
            path.write_bytes(path.read_bytes() + b"drift")
            with self.assertRaisesRegex(ValueError, "checksum/size mismatch"):
                publish_release(source, root / "releases")

    def test_source_manifest_is_stable_across_retrieval_runs(self):
        with tempfile.TemporaryDirectory() as served, tempfile.TemporaryDirectory() as tmp:
            create_engho_sources(Path(served))
            server, thread = self._serve(served)
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                _, first = retrieve_sources(Path(tmp) / "first", base)
                _, second = retrieve_sources(Path(tmp) / "second", base)
            finally:
                server.shutdown(); thread.join(); server.server_close()
            self.assertEqual(first.read_bytes(), second.read_bytes())
            first_run = json.loads((Path(tmp) / "first" / "retrieval-run.json").read_text())
            second_run = json.loads((Path(tmp) / "second" / "retrieval-run.json").read_text())
            self.assertEqual(first_run["source_manifest_sha256"], second_run["source_manifest_sha256"])
            self.assertTrue(first_run["retrieved_at_utc"])
            self.assertTrue(second_run["retrieved_at_utc"])

    def test_retrieve_is_atomic_when_one_source_is_missing(self):
        with tempfile.TemporaryDirectory() as served, tempfile.TemporaryDirectory() as tmp:
            create_engho_sources(Path(served))
            (Path(served) / "engho2018_replicas.zip").unlink()
            server, thread = self._serve(served)
            destination = Path(tmp) / "source"
            try:
                with self.assertRaises(Exception):
                    retrieve_sources(destination, f"http://127.0.0.1:{server.server_port}")
            finally:
                server.shutdown(); thread.join(); server.server_close()
            self.assertFalse(destination.exists())

    def test_commissioning_expectations_are_diagnostics_not_parser_constants(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release = publish_release(create_engho_sources(root / "source"), root / "releases")
            receipt = commission_release(release, root / "commissioning")
            self.assertEqual(receipt["status"], "blocked")
            self.assertTrue((root / "commissioning" / "commissioning-receipt.json").exists())
            self.assertTrue(all("published_rows" in item for item in receipt["checks"]))
            # The structurally valid synthetic release still passes generic validation.
            self.assertEqual(validate_release(release)["status"], "pass")


if __name__ == "__main__":
    unittest.main()

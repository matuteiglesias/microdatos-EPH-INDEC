import json
import tempfile
import unittest
from pathlib import Path

from eph_extractor.batch import period_envelope, run_batch
from eph_extractor.extractor import sha256


class BatchTests(unittest.TestCase):
    def test_period_envelope_is_contiguous_and_inclusive(self):
        self.assertEqual(
            period_envelope("2022-Q3", "2023-Q2"),
            ("2022-Q3", "2022-Q4", "2023-Q1", "2023-Q2"),
        )
        with self.assertRaisesRegex(ValueError, "precedes"):
            period_envelope("2023-Q1", "2022-Q4")
        with self.assertRaisesRegex(ValueError, "invalid EPH period"):
            period_envelope("2022-S1", "2022-Q4")

    def test_batch_materializes_all_periods_and_writes_custody_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def fake_retrieve(year, quarter, destination):
                destination.mkdir(parents=True, exist_ok=True)
                archive = destination / f"EPH_usu_{quarter[-1]}_Trim_{year}_txt.zip"
                archive.write_bytes(f"{year}-{quarter}".encode())
                source = destination / "source-manifest.json"
                source.write_text(
                    json.dumps(
                        {
                            "schema_version": 2,
                            "requested_year": year,
                            "requested_quarter": quarter,
                            "sha256": sha256(archive),
                        },
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return archive, source

            def fake_publish(archive, output_root, year, quarter, source_manifest, command):
                release = output_root / f"eph-{year}-{quarter.lower()}-fixture"
                release.mkdir(parents=True, exist_ok=True)
                (release / "household").mkdir()
                (release / "individual").mkdir()
                (release / "household" / "households.txt").write_text("x\n1\n", encoding="utf-8")
                (release / "individual" / "persons.txt").write_text("x\n1\n2\n", encoding="utf-8")
                manifest = {
                    "release_id": release.name,
                    "requested_year": year,
                    "requested_quarter": quarter,
                    "source_archive_sha256": sha256(archive),
                    "source_manifest_sha256": sha256(source_manifest),
                    "files": [
                        {"role": "household", "rows": 1},
                        {"role": "individual", "rows": 2},
                    ],
                    "producing_command": command,
                }
                (release / "output-manifest.json").write_text(
                    json.dumps(manifest, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                return release

            manifest_path = run_batch(
                start="2022-Q1",
                end="2023-Q4",
                output=root / "batch",
                retrieve_fn=fake_retrieve,
                publish_fn=fake_publish,
            )
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["period_count"], 8)
            self.assertEqual(payload["periods"][0], "2022-Q1")
            self.assertEqual(payload["periods"][-1], "2023-Q4")
            self.assertTrue(payload["qa"]["all_periods_materialized"])
            self.assertTrue(payload["qa"]["unique_release_ids"])
            self.assertTrue(payload["qa"]["nonempty_household_tables"])
            self.assertTrue(payload["qa"]["nonempty_person_tables"])
            self.assertTrue(all(row["household_rows"] == 1 for row in payload["entries"]))
            self.assertTrue(all(row["person_rows"] == 2 for row in payload["entries"]))


if __name__ == "__main__":
    unittest.main()

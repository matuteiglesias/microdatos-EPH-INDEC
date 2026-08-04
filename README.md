# microdatos-EPH-INDEC

A bounded CLI that retrieves one official INDEC EPH quarter and atomically publishes deterministic tables with source and output provenance.

## Install and verify

```bash
make install
make check       # offline unit and CLI checks
make smoke       # generates bounded synthetic ZIP/DBF files in /tmp only
```

Python 3.9+ is supported; the core CLI has no third-party runtime dependency. ZIP and standard dBASE III tables are supported. RAR archives are not supported in release v1.

## Canonical commands

```bash
# Explicit opt-in network probe; output is outside the checkout by default.
make probe YEAR=2024 QUARTER=Q3 OUT_DIR=/tmp/eph-probe

# Deterministic offline publication from an already acquired ZIP.
eph-extractor extract --archive source.zip --year 2024 --quarter Q3 --out /tmp/releases

# Retrieval without publication.
eph-extractor fetch --year 2024 --quarter Q3 --out /tmp/eph-source
```

`release` retrieves exactly one quarter, writes `source-manifest.json`, validates and converts supported members in a temporary directory, writes `output-manifest.json`, then atomically renames the complete release into place. Repeating the same archive is idempotent. Archive paths cannot escape the staging root, duplicate basenames fail, and failures publish nothing.

Discovery checks every known filename for the requested period and proceeds only
when exactly one candidate is available. The source manifest records all candidates,
rejection reasons, the selected URL, and the fail-closed selection rule. Retrieval is
bounded to 512 MiB. Extraction rejects links, special files, nested archives, paths
over 240 characters, more than 128 members, individual expanded files over 1 GiB,
total expansion over 3 GiB, and compression ratios over 250:1.

Outputs use an immutable `eph-YEAR-qN-SOURCEHASH` directory containing `household/`, `individual/`, and `other/` inventories as applicable. Consumers locate data from the output manifest rather than a sibling repository path. See [the characterization](docs/EPH_ACQUISITION_CHARACTERIZATION.md), [storage policy](docs/DATA_STORAGE.md), and [probe record](docs/EPH_ACQUISITION_PROBE.md).

# microdatos-EPH-INDEC

Governed acquisition and deterministic republication of official INDEC household-survey microdata. The established `eph_extractor` path remains the authority for quarterly EPH custody; a parallel `engho_extractor` path now covers the fixed ENGHo 2017/18 public-use source set without importing poverty or basket science.

## Install and verify

```bash
make install
make check       # offline unit and CLI checks for both extractors
make smoke       # bounded synthetic EPH + ENGHo publication
```

Python 3.9+ is supported and both current extractors use only the standard library at runtime.

## EPH path — unchanged semantics

```bash
make probe YEAR=2024 QUARTER=Q3 OUT_DIR=/tmp/eph-probe

eph-extractor extract --archive source.zip --year 2024 --quarter Q3 --out /tmp/releases
eph-extractor fetch --year 2024 --quarter Q3 --out /tmp/eph-source
```

The EPH release contract remains `publicdata.eph-microdata@1`. Outputs use immutable `eph-YEAR-qN-SOURCEHASH` directories and preserve the existing source/output provenance contract.

## ENGHo 2017/18 path

The ENGHo capability consumes the five explicit official INDEC public-use ZIPs:

- `engho2018_hogares.zip`
- `engho2018_personas.zip`
- `engho2018_gastos.zip`
- `engho2018_articulos.zip`
- `engho2018_replicas.zip`

The canonical artifact is `publicdata.indec-engho-microdata/v1`.

```bash
# Networked end-to-end acquisition outside the checkout.
make engho-probe ENGHO_OUT_DIR=/tmp/engho-2017-18

# Or split custody into acquisition and deterministic publication.
engho-extractor fetch --out /tmp/engho-source
engho-extractor extract --source-dir /tmp/engho-source --out /tmp/engho-releases

# Structural validation never requires published production row counts.
engho-extractor validate --release /tmp/engho-releases/engho-2017-2018-...

# Real-data commissioning compares the release inventory with INDEC's published dimensions.
engho-extractor commission \
  --release /tmp/engho-releases/engho-2017-2018-... \
  --out /tmp/engho-commissioning
```

The ENGHo source set is fixed by contract rather than discovered heuristically. Retrieval records exact URLs, filenames, byte sizes and SHA-256 values in a stable source manifest; volatile HTTP/timestamp evidence lives in a separate retrieval-run record. Publication verifies every source checksum, safely opens each ZIP, requires exactly one supported text table for each role, normalizes only text encoding/line endings, preserves the source columns and delimiter, and atomically promotes a release only after all five roles succeed.

### Scientific boundary

**ENGHo republication preserves source fields and identity; scientific selection of reference populations and construction of Engel/poverty measures are downstream responsibilities.**

This repository does not select p29–p48, classify restaurants as food/non-food, construct expenditure shares or Engel coefficients, build CBA/CBT, apply EPH weights analytically, estimate welfare, or calculate poverty.

### Real M1 commissioning

The real governed ENGHo run produced immutable release:

```text
engho-2017-2018-ff05578d65ae
```

with households 21,547; persons 68,725; expenditures 901,804; articles 1,224; and replicate weights 21,547. Deterministic re-extraction reproduced the same release ID and table payloads.

The only adjudicated warning is that the persons table has 50 more rows than the published manual commissioning target (68,725 vs 68,675). Source rows are unique and preserved; the custody layer does not delete observations to force a published count.

See [`docs/ENGHO_M1_COMMISSIONING_2026-09-28.md`](docs/ENGHO_M1_COMMISSIONING_2026-09-28.md) for the durable compact receipt.

See [`docs/ENGHO_2017_18_ACQUISITION.md`](docs/ENGHO_2017_18_ACQUISITION.md), [`docs/DATA_STORAGE.md`](docs/DATA_STORAGE.md), and the existing EPH acquisition characterization for detailed boundaries.

# ENGHo 2017/18 acquisition and republication

## Purpose

The `engho_extractor` package is the governed custody surface for the fixed official INDEC ENGHo 2017/18 public-use microdata family.

It runs beside `eph_extractor`. ENGHo is not forced through EPH quarter abstractions and the existing EPH artifact remains `publicdata.eph-microdata@1`.

The ENGHo artifact is:

```text
publicdata.indec-engho-microdata/v1
```

## Fixed source family

The contract requires exactly the official public-use source roles:

- households;
- persons;
- expenditures;
- articles/classification;
- replicate weights.

The current source contract pins the corresponding INDEC ZIP filenames and required identifying columns. Source discovery is not heuristic.

## Publication semantics

Acquisition records source URL, filename, size and SHA-256. Extraction verifies the pinned source bytes, safely opens the archives, identifies one supported table per role, and normalizes only transport-level text details such as encoding and line endings.

Scientific field values and cross-table identities are preserved.

A release is published atomically only after every required role succeeds. Failure leaves no partial promoted release.

Release identity is derived deterministically from exact source identity plus the extraction contract.

## Commands

```bash
make engho-probe ENGHO_OUT_DIR=/tmp/engho-2017-18

engho-extractor fetch --out /tmp/engho-source

engho-extractor extract \
  --source-dir /tmp/engho-source \
  --out /tmp/engho-releases

engho-extractor validate \
  --release /tmp/engho-releases/engho-2017-2018-...

engho-extractor commission \
  --release /tmp/engho-releases/engho-2017-2018-... \
  --out /tmp/engho-commissioning
```

Hosted CI uses synthetic ENGHo-shaped fixtures. Published row counts are commissioning expectations for a real source run, not generic parser assumptions.

## Real commissioning

The first governed real run is retained at:

```text
docs/ENGHO_M1_COMMISSIONING_2026-09-28.md
docs/ENGHO_M1_COMMISSIONING_2026-09-28.json
```

It produced release `engho-2017-2018-ff05578d65ae` and passed with an explicit 50-person-row manual-count warning. The extractor preserved the source rows rather than filtering to a published count.

## Scientific boundary

This repository owns public-data custody only.

It does not select a reference population, aggregate expenditure, decide whether restaurants/tobacco/alcohol are food, calculate an Engel coefficient, construct CBA/CBT, or calculate poverty.

That separation is intentional: downstream science must consume this immutable source artifact without rewriting source identity.

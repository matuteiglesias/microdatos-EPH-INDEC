# INDEC household-survey data storage policy

Git contains source code, documentation, reviewed small manifests/receipts, and text-only synthetic fixture generators. Raw or normalized respondent-level EPH/ENGHo microdata are not committed.

Binary ZIP/DBF fixtures are generated in temporary directories during checks and are never committed. Full ZIP/RAR/DBF/CSV/TXT/Parquet microdata, releases, models, and temporary staging belong in ignored local or managed external storage.

## EPH

Use an output root outside the checkout, for example `/tmp/eph-probe`. One EPH release is an immutable `eph-YEAR-qN-HASH/` directory plus `output-manifest.json`; the acquisition source area contains the archive and stable source manifest. Failed extraction removes dot-prefixed staging and never promotes a release.

## ENGHo 2017/18

Use an output root outside the checkout, for example `/home/matias/data/engho-2017-18` or `/tmp/engho-2017-18`.

A normal end-to-end layout is:

```text
engho-2017-18/
  source/
    engHo ZIPs
    source-manifest.json
    retrieval-run.json
  releases/
    engho-2017-2018-HASH/
      tables/
        households.txt
        persons.txt
        expenditures.txt
        articles.txt
        replicate_weights.txt
      output-manifest.json
  commissioning/
    commissioning-receipt.json
    commissioning-receipt.md
```

The source and normalized tables stay outside git. A compact reviewed commissioning receipt may be committed later because it contains identities, counts and schema hashes rather than respondent records.

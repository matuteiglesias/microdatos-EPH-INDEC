# EPH data storage policy

Git contains source, documentation, reviewed manifests that do not expose sensitive transport metadata, and the text-only synthetic fixture generator. Binary ZIP and DBF fixtures are generated in temporary directories during checks and are never committed. A generated fixture should stay below 100 KiB; the complete generated fixture set should stay below 1 MiB. Full ZIP/RAR/DBF/CSV/Parquet microdata, releases, models, and temporary staging belong in ignored local or managed external storage.

Use an output root outside the checkout (for example `/tmp/eph-probe`). A release is one immutable `eph-YEAR-qN-HASH/` directory plus `output-manifest.json`; its `.source/` sibling contains the archive and source manifest. Manifests can be copied and committed after review without copying microdata. To remove an incomplete run, delete the selected output root. Failed extraction automatically removes its dot-prefixed staging directory and never promotes a release.

# EPH acquisition characterization

## Baseline recorded before repair

The repository contained the `eph_extractor` package but no packaging metadata or installed console entry point. `README.md` advertised `eph-extractor fetch`, `fetch-range`, and `extract`; the Click module defined those names, but could not import in a clean environment because it unconditionally imported pandas, libpysal, simpledbf, requests, Click, jsonschema, and PyYAML. `extract` also referenced `Path` before its late import and swallowed conversion errors.

The old downloader tried modern names, special 2016–2017 names, DBF ZIP/RAR names, and loose uppercase DBFs. It used an unreliable Content-Length threshold, unsafe `extractall`, destructive moves/deletes, and wrote directly into its requested directory. DBF conversion tried libpysal and a Latin-1 simpledbf fallback. Writes included the download root, `hogar/`, `individual/`, `other/`, `dbf_backup/`, and `processed.json`; extraction removed archives, moved input TXT/DBF files, and deleted empty directories. No source/output provenance or transactional publication existed. `verify` existed but was undocumented; no release command existed.

Supported Python was claimed as 3.7+, but was unproven. The repaired package supports Python 3.9+ and needs only Python's standard library. ZIP and the common dBASE III field subset are supported; RAR and unusual DBF field types are explicitly unsupported.

## Smallest safe plan implemented

Keep the public `eph-extractor` name and single-quarter `fetch` concept, replace mutation-prone extraction with a local archive boundary, add `release` as the explicit fetch-and-publish operation, retain observed modern/2016/2017 candidate names, and make publication atomic. `fetch-range` was not retained because an unbounded historical downloader conflicts with this release's bounded scope.

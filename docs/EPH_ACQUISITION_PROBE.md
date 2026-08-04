# Bounded live acquisition probe

Probe selection: **2024 Q3**. The command is explicit and writes outside the repository:

```console
make probe YEAR=2024 QUARTER=Q3 OUT_DIR=/tmp/eph-probe
```

Result on 2026-08-04: **not retrieved**. All candidate requests were blocked by the execution environment's HTTPS proxy (`CONNECT tunnel failed, response 403`), so no source could be unambiguously resolved. The CLI exited non-zero and left neither a promoted release nor partial output under `/tmp/eph-probe`. Consequently there are no source/output checksums or manifest paths to report. Re-run the command in a network environment that permits `www.indec.gob.ar`; do not treat this environmental failure, or a future success, as evidence for other historical quarters.

No scheduler, commit, push, credentials, secret enumeration, or cross-repository dispatch was performed or added.

## Current-source challenge

On 2026-08-04 the explicit current-source challenge was changed to **2026 Q1**,
whose expected official candidate is
`https://www.indec.gob.ar/ftp/cuadros/menusuperior/eph/EPH_usu_1_Trim_2026_txt.zip`:

```console
make probe YEAR=2026 QUARTER=Q1 OUT_DIR=/tmp/eph-probe-2026q1
```

The discovery contract does not special-case that URL: it derives it from the
requested period, probes every known filename, and downloads only if exactly one is
available. An offline HTTP integration test proves this discovery, selection,
download, and manifest path. The real command was also executed, but this runner's
HTTPS proxy rejected the CONNECT request with HTTP 403 before INDEC could be
reached. No archive, manifest, or release was published. This remains a blocked
online-status check rather than a claim of successful live acquisition.

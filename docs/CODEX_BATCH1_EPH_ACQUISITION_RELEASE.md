# Codex work packet — Batch 1: EPH acquisition release v1

## Mission

Convert this repository's legitimate EPH acquisition capability into a small, trustworthy release producer that can be installed cleanly, exercised without network access, and used for one bounded live quarter with complete provenance.

The target state is **not** a revived unattended updater. The target state is a reliable local component that emits a versioned EPH source release for downstream preprocessing.

## Why this matters

This repository is the authority for acquiring and converting upstream EPH microdata. It must make source retrieval, archive handling, DBF conversion, output identity, and failure behavior trustworthy before any scheduler or downstream automation is reconsidered.

The next portfolio stage expects this repository to produce a stable input for `income-modeling-eph`, which now owns the annual EPH preprocessing artifacts.

## Read first

Before changing code:

1. Read every applicable `AGENTS.md` file.
2. Read `README.md`, `SYSTEM.yaml`, `eph_extractor/settings.yaml`, packaging files, CLI modules, tests, `.gitignore`, and `.github/workflows/README.md` if present.
3. Inspect the quarantined legacy workflows only as historical evidence. Do not re-enable them.
4. Inventory the real package layout and compare it with the public commands documented in the README.

Treat README claims as hypotheses until demonstrated in a clean environment.

## Authority and boundaries

This repository owns:

- discovery and retrieval of official EPH source files;
- archive extraction and raw-format conversion;
- normalized output naming;
- source and output provenance;
- a versioned EPH microdata release contract.

It does not own:

- household/person analytical merging;
- socioeconomic feature engineering;
- price deflation;
- geographic ranks;
- income targets or models;
- poverty estimates;
- cross-repository dispatch.

## Required deliverables

### 1. Characterization report

Create `docs/EPH_ACQUISITION_CHARACTERIZATION.md` containing:

- the actual package and CLI entry points;
- supported Python versions and system dependencies;
- the current behavior of `fetch`, `fetch-range`, and `extract`, or an explicit finding that a documented command is absent;
- archive, filename, encoding, and DBF variants currently handled;
- all write locations and destructive cleanup behavior;
- current gaps between README promises and executable behavior;
- the smallest safe change plan.

Do not repair behavior before recording the current state.

### 2. Reproducible installation and canonical commands

Establish a truthful package installation and a single canonical command surface. Prefer the existing `eph-extractor` name when it can be supported without compatibility damage.

Provide commands equivalent to:

```bash
make install
make check
make smoke
make probe YEAR=2024 QUARTER=Q3 OUT_DIR=/tmp/eph-probe
```

The exact implementation may differ, but:

- `make check` must be offline and deterministic;
- `make smoke` must run only bounded local fixtures;
- the live probe must be explicit, opt-in, and write outside tracked repository data by default.

Update `SYSTEM.yaml` only after commands are proven.

### 3. Small deterministic fixtures

Add synthetic or redistributable fixtures that cover the real failure classes found in the code, including where applicable:

- normal modern ZIP naming;
- irregular 2016–2017-style naming;
- nested archive paths;
- case differences;
- one tiny DBF conversion;
- Latin-1 or other supported encoding behavior;
- duplicate or unexpected files;
- corrupt or unsupported archive failure.

Fixtures must contain no real confidential information and must remain small enough for ordinary Git use.

### 4. Deterministic extraction tests

Tests must assert:

- selected source identity;
- normalized output filenames;
- stable table columns and row ordering where the source format permits it;
- encoding behavior;
- archive and temporary-file cleanup policy;
- idempotent reruns;
- no partially published output after failure;
- no writes outside the requested output root.

Use a temporary staging directory and promote outputs only after all validations pass.

### 5. Source manifest

For every retrieval, emit a machine-readable source manifest containing at least:

- manifest schema version;
- publisher and dataset family;
- requested year and quarter;
- resolved source URL;
- retrieval timestamp in UTC;
- HTTP or transport metadata that is safely available;
- original filename;
- byte size;
- SHA-256 checksum;
- retrieval status;
- tool version and Git commit when available.

Do not infer publication dates from filenames unless clearly marked as an inference.

### 6. Output manifest

After successful extraction, emit a machine-readable output manifest containing:

- source-manifest identity or checksum;
- output release ID;
- household, individual, and other file inventory;
- file hashes and sizes;
- detected delimiter and encoding;
- row and column counts where readable;
- normalized names;
- warnings and unsupported files;
- producing command and software version.

Define the release so downstream code can consume it without relying on a sibling-repository path.

### 7. Data-storage and large-file policy

Document:

- what belongs in Git;
- what belongs in local or external storage;
- ignored archive, DBF, CSV, Parquet, model, and temporary paths;
- maximum fixture expectations;
- how manifests may be committed without committing full microdata;
- how a user safely removes an incomplete local run.

Do not rewrite Git history or delete existing tracked data without explicit human approval.

### 8. One bounded live probe

After all offline checks pass, run one explicitly selected quarter only.

The probe must:

- use the canonical CLI;
- write to a disposable external directory;
- produce both manifests;
- report source and output checksums;
- avoid commits, pushes, dispatches, and scheduler changes;
- leave no promoted output if retrieval or extraction fails.

Record the result in `docs/EPH_ACQUISITION_PROBE.md`. Do not describe one successful quarter as proof that all historical quarters work.

## Ordered execution

1. Characterize the existing implementation and packaging.
2. Add characterization tests around behavior worth preserving.
3. Repair the smallest packaging and CLI gaps.
4. Add local fixtures and deterministic tests.
5. Implement source and output manifests.
6. Implement staging and atomic promotion.
7. Add canonical Make targets and offline CI.
8. Run the bounded live probe.
9. Reconcile README and `SYSTEM.yaml` with demonstrated behavior.

Prefer several reviewable commits. Keep implementation PRs small enough to explain independently.

## Human checkpoints

Stop and request review before:

- changing the public CLI incompatibly;
- changing normalized output semantics;
- deleting or relocating tracked datasets;
- selecting a new external storage system;
- re-enabling scheduled automation;
- introducing automatic commits or GitHub tokens;
- interpreting an upstream format change that affects data meaning.

## Non-goals

- No automatic data commits.
- No cross-repository dispatch.
- No secret enumeration.
- No broad downloader framework for unrelated INDEC products.
- No preprocessing, feature engineering, modeling, or poverty calculations.
- No claim that the repository is updated within 24 hours until production evidence supports it.
- No large live-data fixtures.

## Stop conditions

Stop rather than guess when:

- the official source cannot be unambiguously resolved;
- two candidate archives imply different datasets;
- a format change may alter variable meaning;
- fixture behavior cannot be tied to observed legacy behavior;
- successful execution would require credentials or repository mutation not explicitly authorized.

## Acceptance criteria

The packet is complete only when:

```text
clean installation succeeds
canonical help and version commands succeed
offline fixture checks pass deterministically
one bounded quarter can be retrieved and extracted manually
source and output manifests include URLs, timestamps, sizes, and checksums
failure cannot publish partial output
no workflow, commit, push, or downstream dispatch occurs
README and SYSTEM declarations match the proven command surface
```

## Completion report

The final Codex response and PR description must state:

- files and behavior changed;
- exact commands run and their outcomes;
- the live quarter probed;
- release and manifest paths;
- remaining unsupported source variants;
- any methodological or source ambiguity requiring Matías's decision;
- confirmation that no automatic commit, scheduler, secret, or cross-repository operation was added.

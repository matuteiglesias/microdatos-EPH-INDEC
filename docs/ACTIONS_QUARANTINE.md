# GitHub Actions quarantine

The repository's three legacy workflows were removed from `.github/workflows/` on 2026-08-04.

## Why

The observed workflow set was not a coherent or safe production path:

- `actualizador.yml` was disabled for inactivity, used obsolete action versions and Python 3.8, referenced an updater command that is not evidenced as a current repository interface, and attempted a cross-repository dispatch using the repository-scoped `GITHUB_TOKEN`;
- `notify.yml` watched `main` although the default branch is `master`, contained a misspelled token reference, and dispatched to `encuestador-de-hogares`, which is currently consumer-gated rather than active;
- `secrets.yml` enumerated configured secret names and had no legitimate operational responsibility.

Git history preserves the removed files. They should not be restored as production workflows.

## Current Actions policy

Lifecycle: **quarantined data job**.

No GitHub Actions workflow should be added until a local/Codex packet establishes:

1. the current acquisition entry point;
2. an offline fixture or parser smoke check;
3. the upstream release cadence;
4. source URL, checksum, timestamp, row-count and code-SHA manifest fields;
5. a bounded candidate-output location;
6. review before publication;
7. an explicit downstream consumer, if any.

A future refresh should be `workflow_dispatch` first. It must not push canonical data directly to `master`, and cross-repository mutation must use a dedicated GitHub App with narrowly declared permissions.

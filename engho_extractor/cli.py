"""Canonical CLI for governed ENGHo 2017/18 acquisition and republication."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil

from . import __version__
from .downloader import retrieve_sources
from .extractor import publish_release
from .validator import commission_release, validate_release


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="engho-extractor")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="retrieve the fixed official ENGHo 2017/18 source set")
    fetch.add_argument("--out", type=Path, required=True)

    extract = sub.add_parser("extract", help="publish an immutable release from an acquired source directory")
    extract.add_argument("--source-dir", type=Path, required=True)
    extract.add_argument("--out", type=Path, required=True)

    release = sub.add_parser("release", help="retrieve sources and publish an immutable release")
    release.add_argument("--out", type=Path, required=True)

    validate = sub.add_parser("validate", help="validate an immutable ENGHo release")
    validate.add_argument("--release", type=Path, required=True)

    commission = sub.add_parser("commission", help="compare a real release with published INDEC dimensions")
    commission.add_argument("--release", type=Path, required=True)
    commission.add_argument("--out", type=Path, required=True)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == "fetch":
        source, manifest = retrieve_sources(args.out)
        print(source)
        print(manifest)
        return
    if args.command == "extract":
        print(publish_release(args.source_dir, args.out))
        return
    if args.command == "release":
        root = args.out.expanduser().resolve()
        source = root / "source"
        releases = root / "releases"
        root.mkdir(parents=True, exist_ok=True)
        try:
            retrieve_sources(source)
            print(publish_release(source, releases, "engho-extractor release"))
        except Exception:
            if source.exists() and not (source / "source-manifest.json").exists():
                shutil.rmtree(source, ignore_errors=True)
            raise
        return
    if args.command == "validate":
        print(validate_release(args.release))
        return
    receipt = commission_release(args.release, args.out)
    print(args.out / "commissioning-receipt.json")
    if receipt["status"] != "pass":
        raise SystemExit(2)


if __name__ == "__main__":
    main()

"""Canonical command line interface."""
import argparse
import shutil
from pathlib import Path
from . import __version__
from .downloader import retrieve
from .extractor import publish_release

def parser():
    p = argparse.ArgumentParser(prog="eph-extractor")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch", help="retrieve one official quarter and write source provenance")
    extract = sub.add_parser("extract", help="atomically create a release from a local ZIP")
    release = sub.add_parser("release", help="retrieve and atomically publish one quarter")
    for command in (fetch, release):
        command.add_argument("--year", type=int, required=True); command.add_argument("--quarter", required=True)
        command.add_argument("--out", type=Path, required=True)
    extract.add_argument("--archive", type=Path, required=True); extract.add_argument("--year", type=int, required=True)
    extract.add_argument("--quarter", required=True); extract.add_argument("--out", type=Path, required=True)
    extract.add_argument("--source-manifest", type=Path)
    return p

def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == "fetch":
        archive, manifest = retrieve(args.year, args.quarter, args.out)
        print(archive); print(manifest); return
    if args.command == "extract":
        result = publish_release(args.archive, args.out, args.year, args.quarter, args.source_manifest,
                                 "eph-extractor extract")
    else:
        raw = args.out.resolve() / ".source"
        try:
            archive, manifest = retrieve(args.year, args.quarter, raw)
            result = publish_release(archive, args.out, args.year, args.quarter, manifest,
                                     "eph-extractor release")
        except Exception:
            shutil.rmtree(raw, ignore_errors=True)
            try: args.out.rmdir()
            except OSError: pass
            raise
    print(result)

if __name__ == "__main__": main()

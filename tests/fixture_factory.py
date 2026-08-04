"""Generate bounded synthetic EPH fixtures without storing binary files in Git."""
from __future__ import annotations

import struct
from pathlib import Path
import zipfile


def _write_dbf(path: Path) -> None:
    fields = [("NOMBRE", "C", 12, 0), ("VALOR", "N", 4, 0)]
    rows = [("José", "2"), ("Ana", "1")]
    header_length = 32 + 32 * len(fields) + 1
    record_length = 1 + sum(field[2] for field in fields)
    header = bytearray(32)
    header[0] = 3
    header[4:8] = struct.pack("<I", len(rows))
    header[8:12] = struct.pack("<HH", header_length, record_length)
    output = bytearray(header)
    for name, kind, size, decimals in fields:
        descriptor = bytearray(32)
        descriptor[:len(name)] = name.encode("ascii")
        descriptor[11] = ord(kind)
        descriptor[16] = size
        descriptor[17] = decimals
        output += descriptor
    output += b"\r"
    for name, value in rows:
        output += b" " + name.encode("latin-1").ljust(12) + value.encode("ascii").rjust(4)
    path.write_bytes(output + b"\x1a")


def create_fixtures(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    dbf = root / "tiny_latin1.dbf"
    _write_dbf(dbf)
    with zipfile.ZipFile(root / "modern_nested.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(dbf, "nested/USU_HOGAR_T324.DBF")
        archive.writestr(
            "nested/usu_individual_t324.txt",
            "ID;NOMBRE\r\n2;José\r\n1;Ana\r\n".encode("latin-1"),
        )
        archive.writestr("README.pdf", b"synthetic unsupported payload")
    with zipfile.ZipFile(root / "irregular_2016.zip", "w") as archive:
        archive.writestr("EPH_usu_2doTrim_2016/Ind_t216.TXT", "ID;VALUE\n1;ok\n")
    with zipfile.ZipFile(root / "duplicate.zip", "w") as archive:
        archive.writestr("a/Foo.txt", "x\n")
        archive.writestr("b/foo.TXT", "y\n")
    (root / "corrupt.zip").write_text("not a zip", encoding="ascii")
    return root


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    print(create_fixtures(parser.parse_args().output))

"""Generate bounded synthetic ENGHo-shaped source ZIPs for offline tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

FILES = {
    "engho2018_hogares.zip": ("engho2018_hogares.txt", "id|pondera|ingpch\n1|10|100\n2|20|200\n"),
    "engho2018_personas.zip": ("engho2018_personas.txt", "id|miembro|ingreso\n1|1|80\n1|2|20\n2|1|200\n"),
    "engho2018_gastos.zip": (
        "engho2018_gastos.txt",
        "id|miembro|articulo|forma_pago|tipo_negocio|modo_adq|lugar_adq|monto\n"
        "1|1|101|1|1|1|1|20\n1|2|201|1|2|1|1|30\n2|1|101|1|1|1|1|50\n",
    ),
    "engho2018_articulos.zip": ("engho2018_articulos.txt", "articulo|division|descripcion\n101|01|food\n201|11|restaurant\n"),
    "engho2018_replicas.zip": ("engho2018_replicas.txt", "id|rep_1|rep_2\n1|9|11\n2|18|22\n"),
}
ROLE = {
    "engho2018_hogares.zip": "households",
    "engho2018_personas.zip": "persons",
    "engho2018_gastos.zip": "expenditures",
    "engho2018_articulos.zip": "articles",
    "engho2018_replicas.zip": "replicate_weights",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_engho_sources(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    entries = []
    for filename, (member, content) in FILES.items():
        path = root / filename
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(member, content)
        entries.append({
            "role": ROLE[filename],
            "url": f"https://example.invalid/{filename}",
            "filename": filename,
            "bytes": path.stat().st_size,
            "sha256": _sha(path),
        })
    manifest = {
        "schema_version": 1,
        "artifact_type": "publicdata.indec-engho-source-set/v1",
        "publisher": "INDEC",
        "dataset_family": "ENGHo",
        "survey_vintage": "2017-2018",
        "source_landing_page": "https://example.invalid",
        "documentation": [],
        "selection_rule": "fixed_explicit_official_2017_18_source_set",
        "sources": entries,
        "tool_version": "1.0.0",
    }
    (root / "source-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return root


def create_bad_archive(root: Path, kind: str) -> Path:
    source = create_engho_sources(root)
    path = source / "engho2018_hogares.zip"
    if kind == "traversal":
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("../engho2018_hogares.txt", "id|pondera\n1|1\n")
    elif kind == "duplicate":
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("a/engho2018_hogares.txt", "id|pondera\n1|1\n")
            archive.writestr("b/ENGHO2018_HOGARES.TXT", "id|pondera\n1|1\n")
    elif kind == "unsupported":
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("engho2018_hogares.xlsx", b"fake")
    elif kind == "corrupt":
        path.write_bytes(b"not-a-zip")
    else:
        raise ValueError(kind)
    manifest_path = source / "source-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for item in manifest["sources"]:
        if item["filename"] == path.name:
            item["bytes"] = path.stat().st_size
            item["sha256"] = _sha(path)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return source


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    print(create_engho_sources(parser.parse_args().output))

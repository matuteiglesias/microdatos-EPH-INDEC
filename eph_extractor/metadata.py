# metadata.py

import json
from pathlib import Path

def read_processed_metadata(metadata_file: str) -> dict:
    """
    Lee metadata de ejecuciones procesadas desde metadata_file.
    Devuelve un dict con la estructura guardada o un dict vacío si no existe.
    """
    path = Path(metadata_file)
    if not path.is_file():
        return {}
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def write_processed_metadata(metadata_file: str, data: dict) -> None:
    """
    Escribe metadata de ejecuciones procesadas en metadata_file.
    Sobrescribe el archivo existente.
    """
    path = Path(metadata_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

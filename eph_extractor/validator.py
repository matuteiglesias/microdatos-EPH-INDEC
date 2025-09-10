# validator.py

import json
from jsonschema import validate, ValidationError
from pathlib import Path
import hashlib

def validate_schema(file_path: str, schema_path: str) -> bool:
    """
    Valida que el JSON o CSV convertido a dict cumpla con el JSON Schema en schema_path.
    Para CSV, asume primero convertirlo a lista de registros (dicts).
    Lanza ValidationError si no cumple; devuelve True si es válido.
    """
    # Cargar schema
    schema = json.loads(Path(schema_path).read_text(encoding='utf-8'))
    # Cargar contenido
    content = json.loads(Path(file_path).read_text(encoding='utf-8'))
    try:
        validate(instance=content, schema=schema)
        return True
    except ValidationError as e:
        # Podríamos loggear e.message aquí
        raise

def check_checksums(dir_path: str, metadata_path: str) -> dict:
    """
    Verifica checksums SHA256 de archivos en dir_path según metadata en metadata_path.
    Devuelve un dict mapping filename -> bool (True si coincide, False si no).
    """
    # Carga metadata
    metadata = json.loads(Path(metadata_path).read_text(encoding='utf-8'))
    results = {}
    for fname, expected in metadata.get('checksums', {}).items():
        file_path = Path(dir_path) / fname
        if not file_path.is_file():
            results[fname] = False
            continue
        # Calcular SHA256
        h = hashlib.sha256()
        with file_path.open('rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        results[fname] = (h.hexdigest() == expected)
    return results

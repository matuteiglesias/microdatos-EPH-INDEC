# config.py

import os
from pathlib import Path

def load_config(config_path: str = None) -> dict:
    """
    Carga configuración desde un archivo YAML o utiliza valores por defecto.

    El orden de carga es:
      1. Archivo especificado por config_path (si existe).
      2. settings.yaml ubicado junto a este módulo.
      3. Valores por defecto hardcodeados.
      4. Variables de entorno que sobreescriben claves.

    Retorna un dict con las claves:
      - ftp_url
      - default_output_dir
      - default_schema_dir
    """
    # Valores por defecto
    config = {
        'ftp_url': "https://www.indec.gob.ar/ftp/cuadros/menusuperior/eph/",
        'default_output_dir': "/data/eph/raw",
        'default_schema_dir': "schemas"
    }

    # Ruta al settings.yaml del paquete
    pkg_settings = Path(__file__).parent / 'settings.yaml'
    # Si existe un settings externo o config_path, cargarlo
    for path in filter(None, [config_path, str(pkg_settings)]):
        p = Path(path)
        if p.is_file():
            # Settings intentionally remain a flat scalar mapping, avoiding a
            # runtime YAML dependency for offline fixture use.
            loaded = {}
            for line in p.read_text(encoding='utf-8').splitlines():
                line = line.split('#', 1)[0].strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    loaded[key.strip()] = value.strip().strip('"\'')
            config.update(loaded)

    # Finalmente, permitir override por variables de entorno
    for key in config.keys():
        env_val = os.getenv(key.upper())
        if env_val is not None:
            config[key] = env_val

    return config

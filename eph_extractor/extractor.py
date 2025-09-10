# extractor.py
import glob
import os
import shutil
from pathlib import Path
import pandas as pd
# import pysal as ps
import libpysal as lps

from simpledbf import Dbf5

def extract_dbf_to_csv(input_dir: str, output_dir: str, drop_cols: list = None) -> None:
    """
    Extrae todos los .dbf en `input_dir`, los convierte a TXT (;-sep) en `output_dir`,
    mueve cada DBF a input_dir/dbf_backup/, y elimina carpetas vacías sobrantes.
    """
    input_path  = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 1) Prepara backup de los DBF originales
    backup = input_path / 'dbf_backup'
    backup.mkdir(parents=True, exist_ok=True)

    # 2) Columnas a descartar
    drop_set = set(drop_cols) if drop_cols else set()

    def _dbf_to_df(pth: Path) -> pd.DataFrame:
        # First try with pysal
        try:
            db = lps.io.open(str(pth))
            headers = [h for h in db.header if h not in drop_set]
            data    = {h: db.by_col(h) for h in headers}
            db.close()
            return pd.DataFrame(data)
        except UnicodeDecodeError:
            # fallback to simpledbf with Latin-1
            df = Dbf5(str(pth), codec='latin1').to_dataframe()
            # drop unwanted cols
            return df[[c for c in df.columns if c not in drop_set]]

    # 3) Recorre recursivamente cada DBF
    # for dbf_path in input_path.rglob('*.dbf'):
    for dbf_path in input_path.rglob('*'):
        # Solo queremos archivos con sufijo .dbf ó .DBF u otras combinaciones
        if dbf_path.is_file() and dbf_path.suffix.lower() == '.dbf':



            # skip anything under dbf_backup
            if 'dbf_backup' in [p.name for p in dbf_path.parents]:
                continue

            # Decide categoría por la ruta
            parts = [p.lower() for p in dbf_path.parts]
            if 'hogar' in parts:
                cat = 'hogar'
            elif 'indiv' in parts or 'individual' in parts:
                cat = 'individual'
            else:
                cat = 'other'

            dest_dir = output_path / cat
            dest_dir.mkdir(parents=True, exist_ok=True)
            txt_name = dbf_path.stem + '.txt'
            txt_path = dest_dir / txt_name

            # Saltar si ya existe
            if txt_path.exists():
                print(f"INFO: {txt_path.name} ya procesado, omitiendo")
            else:
                print(f"INFO: Procesando {dbf_path} → {cat}")
                try:
                    df = _dbf_to_df(dbf_path)
                    df.to_csv(txt_path, index=False, sep=';', quotechar='"', escapechar='\\')
                    print(f"INFO: TXT generado → {txt_path}")

                # always move the DBF into backup, so we don’t retry it next time
                except Exception as e:
                    print(f"WARNING: fallo al convertir {dbf_path.name}: {e}")
                    # skip this file
                    continue

            target = backup / dbf_path.name
            if not target.exists():
                try:
                    shutil.move(str(dbf_path), str(target))
                    print(f"INFO: DBF movido a backup → {target}")
                except Exception as e:
                    print(f"WARNING: no pude mover {dbf_path.name} a backup: {e}")

    # 4) Limpiar carpetas vacías (menos dbf_backup)
    for folder in sorted(input_path.rglob('*'), key=lambda p: -len(p.parts)):
        if folder.is_dir() and folder.name != 'dbf_backup' and not any(folder.iterdir()):
            try:
                folder.rmdir()
                print(f"INFO: Carpeta vacía eliminada → {folder}")
            except Exception:
                pass

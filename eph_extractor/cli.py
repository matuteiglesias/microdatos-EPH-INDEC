## eph_extractor/

# cli.py
import sys
from click import group, option
from eph_extractor.downloader import download_quarter, list_available_quarters
from eph_extractor.validator import validate_schema, check_checksums
from eph_extractor.extractor import extract_dbf_to_csv
from eph_extractor.metadata import read_processed_metadata, write_processed_metadata
from eph_extractor.config import load_config
from click import pass_context
import os
import shutil

@group()
def cli():
    """CLI para eph-extractor: subcomandos fetch, extract, verify"""
    pass


@cli.command()
@option('--dir', 'in_dir', type=str, required=True, help='Directorio con raw data (ZIP y DBF)')
def verify(in_dir):
    """Valida integridad y checksum de los archivos descargados"""
    cfg = load_config()
    metadata_file = f"{in_dir}/processed.json"
    try:
        results = check_checksums(in_dir, metadata_file)
        failed = [f for f, ok in results.items() if not ok]
        if failed:
            print(f"ERROR: Checksum mismatch en: {failed}")
            sys.exit(1)
        print("INFO: Todos los archivos pasaron las validaciones.")
    except Exception as e:
        print(f"ERROR en validación: {e}")
        sys.exit(1)


@cli.command()
@option('--dir', 'in_dir',  type=str, required=True, help='Directorio con raw DBF y TXT extraídos')
@option('--out','out_dir', type=str, required=True, help='Directorio para TXT/CSV de salida')
def extract(in_dir, out_dir):
    """
    1) Convierte todos los .dbf de `in_dir` → TXT en `out_dir`  
    2) Reubica cualquier *.txt ya presente en `in_dir` → `out_dir`  
    3) Limpia el raw (carpetas vacías, backups, zips/rar) y avisa de sobrantes
    """
    try:
        # 1) legacy .dbf → TXT + backup
        extract_dbf_to_csv(in_dir, out_dir)

        # 2) move any existing .txt under in_dir into out_dir subfolders
        for root, _, files in os.walk(in_dir):
            for fname in files:
                if fname.lower().endswith('.txt'):
                    src = Path(root) / fname
                    lower = fname.lower()
                    if 'hogar' in lower or lower.startswith('hog_'):
                        dest_sub = Path(out_dir) / 'hogar'
                    elif 'indiv' in lower or lower.startswith('ind_'):
                        dest_sub = Path(out_dir) / 'individual'
                    else:
                        dest_sub = Path(out_dir) / 'other'
                    dest_sub.mkdir(parents=True, exist_ok=True)
                    dst = dest_sub / fname
                    if not dst.exists():
                        shutil.move(str(src), str(dst))
                        print(f"INFO: Moved TXT → {dst}")

        # 3a) remove any top-level archives
        input_path = Path(in_dir)
        for ext in ('*.zip','*.rar'):
            for arc in input_path.glob(ext):
                try:
                    arc.unlink()
                    print(f"INFO: Removed archive → {arc.name}")
                except Exception as e:
                    print(f"WARNING: could not remove {arc.name}: {e}")

        # 3b) remove stray TXT at root
        for txt in input_path.glob('*.txt'):
            try:
                txt.unlink()
                print(f"INFO: Removed stray TXT → {txt.name}")
            except Exception as e:
                print(f"WARNING: could not remove {txt.name}: {e}")

        # 3c) zap any empty dirs (including old EPH_usu_… folders)
        for sub in input_path.iterdir():
            if sub.is_dir() and not any(sub.iterdir()):
                try:
                    sub.rmdir()
                    print(f"INFO: Removed empty dir → {sub.name}")
                except Exception:
                    pass

        # 3d) report any unexpected leftovers
        leftovers = [f for f in os.listdir(in_dir)
                     if os.path.isfile(os.path.join(in_dir, f))
                     and not f.lower().endswith(('.dbf','.txt'))]
        if leftovers:
            print(f"WARNING: Unexpected files left in {in_dir}: {leftovers}")

        print(f"INFO: Extract complete. Output in {out_dir}")

    except Exception as e:
        print(f"ERROR al extraer: {e}")
        # sys.exit(1)

        
@cli.command()
@option('--year', type=int, required=True, help='Año del trimestre a descargar')
@option('--quarter', type=str, required=True, help='Trimestre (Q1, Q2, Q3, Q4)')
@option('--out', 'out_dir', type=str, required=True, help='Directorio de salida para raw data')
@option('--keep-zip/--no-keep-zip', default=False, help='Conservar el ZIP tras la extracción')
def fetch(year, quarter, out_dir, keep_zip):
    """Descarga y extrae un trimestre específico, si no fue procesado antes"""
    cfg = load_config()
    metadata_file = f"{out_dir}/processed.json"
    processed = read_processed_metadata(metadata_file)
    key = f"{year}-{quarter}"
    if key in processed:
        print(f"INFO: Trimestre {key} ya procesado, omitiendo descarga.")
        return
    try:
        download_quarter(year, quarter, out_dir)
        # Actualización de metadata
        processed[key] = {'status': 'downloaded'}
        write_processed_metadata(metadata_file, processed)
        print(f"INFO: Trimestre {key} descargado correctamente.")

        # --- LIMPIEZA POST-DESCARGA ---
        if not keep_zip:
            import os, shutil

            # 1) Elimina el ZIP
            zip_name    = f"EPH_usu_{quarter[-1]}_Trim_{year}_txt.zip"
            zip_path    = os.path.join(out_dir, zip_name)
            if os.path.isfile(zip_path):
                os.remove(zip_path)
                print(f"INFO: ZIP eliminado → {zip_path}")

            # 2) Elimina carpeta temporal (misma raíz que el ZIP)
            tmp_folder  = zip_name.replace('.zip','')
            tmp_path    = os.path.join(out_dir, tmp_folder)
            if os.path.isdir(tmp_path):
                shutil.rmtree(tmp_path)
                print(f"INFO: Carpeta temporal eliminada → {tmp_path}")


        # Dentro de fetch_range, tras el bucle:
        cleanup_download_folder(Path(out_dir))

    except RuntimeError as e:
        # Cuando el ZIP no existe o es demasiado pequeño
        print(f"WARNING: {e}")
        return
    except Exception as e:
        # Errores inesperados: aquí sí detenemos
        print(f"ERROR: Fallo al descargar {year}-{quarter}: {e}")
        sys.exit(1)

@cli.command()
@option('--start-year', type=int, required=True, help='Año inicial (inclusive)')
@option('--end-year',   type=int, required=True, help='Año final   (inclusive)')
@option('--out', 'out_dir', type=str, required=True, help='Directorio de salida para raw data')
@option('--keep-zip/--no-keep-zip', default=False, help='Conservar los ZIPs tras la extracción')
@pass_context
def fetch_range(ctx, start_year, end_year, out_dir, keep_zip):
    """
    Recorrer todos los trimestres de start_year a end_year.
    Internamente llama al subcomando `fetch` para cada (año, trimestre).
    """
    quarters = ['Q1','Q2','Q3','Q4']
    for y in range(start_year, end_year+1):
        for q in quarters:
            key = f"{y}-{q}"
            try:
                # Simula: eph-extractor fetch --year y --quarter q --out out_dir [--keep-zip]
                ctx.invoke(fetch, year=y, quarter=q, out_dir=out_dir, keep_zip=keep_zip)
            except Exception as e:
                # Si el ZIP no existe (ej. años muy viejos o nombres inconsistentes),
                # simplemente lo reportamos y continuamos.
                print(f"WARNING: no se pudo procesar {key}: {e}")


    # Dentro de fetch_range, tras el bucle:
    cleanup_download_folder(Path(out_dir))
    print(f"INFO: fetch_range completado para {start_year}–{end_year}")



    # Al final de eph_extractor/cli.py
import re
from pathlib import Path

def cleanup_download_folder(base_dir: Path) -> None:
    """
    Normaliza nombres y limpia remanentes en base_dir:
    - Renombra *.txt.txt → *.txt
    - Unifica prefijos y case: usu_hogar_*, usu_individual_*
    - Elimina carpetas vacías (p.ej. directorios ZIP originales)
    """
    # 1) Renombrar dobles extensiones
    for p in base_dir.rglob("*.txt.txt"):
        new = p.with_name(p.name.replace(".txt.txt", ".txt"))
        p.rename(new)
        print(f"INFO: Renombrado {p.name} → {new.name}")

    # 2) Unificar nombres case-insensitive
    for p in base_dir.rglob("*.txt"):
        stem = p.stem.lower()
        # ya viene con prefijo usu_
        if stem.startswith("usu_"):
            correct = stem
        else:
            # intentar extraer Txxx
            m = re.search(r"(t\\d{3})", stem)
            if m:
                t = m.group(1)
                if "hogar" in stem:
                    correct = f"usu_hogar_{t}"
                elif "individual" in stem:
                    correct = f"usu_individual_{t}"
                else:
                    continue
            else:
                continue
        newname = correct + p.suffix
        if p.name != newname:
            p.rename(p.with_name(newname))
            print(f"INFO: Nombre normalizado {p.name} → {newname}")

    # 3) Eliminar carpetas vacías
    for d in base_dir.rglob("*"):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
            print(f"INFO: Carpeta vacía eliminada → {d}")

    print(f"INFO: Limpieza de {base_dir} completada.")

# downloader.py
from datetime import datetime
from pathlib import Path
import requests
import urllib
import zipfile
import shutil
from eph_extractor.config import load_config



def list_available_quarters(n: int) -> list:
    """Genera una lista de los últimos n trimestres como tuplas (year, quarter)"""
    current = datetime.now()
    year, month = current.year, current.month
    quarter = (month - 1) // 3 + 1
    quarters = []
    for _ in range(n):
        quarters.append((year, f"Q{quarter}"))
        quarter -= 1
        if quarter == 0:
            year -= 1
            quarter = 4
    return quarters


def download_quarter(year: int, quarter: str, dest: str) -> None:
    """Descarga el ZIP/RAR del INDEC (moderno o legacy) y extrae su contenido en dest."""
    cfg = load_config()
    base_url = cfg.get('ftp_url')
    dest_path = Path(dest)
    dest_path.mkdir(parents=True, exist_ok=True)


    # Construcción de posibles nombres de archivo en orden de prioridad
    attempts = []
    qnum = quarter[-1]
    yy = str(year)[-2:]

    # 0) very-early “EPH_usu” pattern w/o “_txt” suffix?
    attempts.append(f"EPH_usu_{qnum}_Trim_{year}.zip")
    attempts.append(f"EPH_usu_{qnum}_Trim_{year}.rar")

    # 0b) uppercase DBF naming: “Hog_t” / “Ind_t”
    attempts.append(f"Hog_t{qnum}{yy}.DBF")
    attempts.append(f"Ind_t{qnum}{yy}.DBF")

    attempts += [
    f"Hog_t{qnum}{yy}.DBF",
    f"Ind_t{qnum}{yy}.DBF",
    f"t{qnum}{yy}.zip",     # no “_dbf” suffix
    f"t{qnum}{yy}.rar",
    ]



# https://www.indec.gob.ar/ftp/cuadros/menusuperior/eph/EPH_usu_2doTrim_2016_txt.zip
# https://www.indec.gob.ar/ftp/cuadros/menusuperior/eph/EPH_usu_3erTrim_2016_txt.zip
# https://www.indec.gob.ar/ftp/cuadros/menusuperior/eph/EPH_usu_4toTrim_2016_txt.zip
# https://www.indec.gob.ar/ftp/cuadros/menusuperior/eph/EPH_usu_1er_Trim_2017_txt.zip
# https://www.indec.gob.ar/ftp/cuadros/menusuperior/eph/EPH_usu_2_Trim_2017_txt.zip
# https://www.indec.gob.ar/ftp/cuadros/menusuperior/eph/EPH_usu_3_Trim_2017_txt.zip
# https://www.indec.gob.ar/ftp/cuadros/menusuperior/eph/EPH_usu_4_Trim_2017_txt.zip

    # 1) Convención moderna estandarizada
    attempts.append(f"EPH_usu_{qnum}_Trim_{year}_txt.zip")

    # 2) Casos irregulares 2016-2017 (ordinales en español)
    if year == 2016:
        attempts += [
            f"EPH_usu_{qnum}erTrim_{year}_txt.zip",
            f"EPH_usu_{qnum}doTrim_{year}_txt.zip",
            f"EPH_usu_{qnum}er_Trim_{year}_txt.zip",
            f"EPH_usu_{qnum}toTrim_{year}_txt.zip"
        ]


    if year == 2017 and qnum == '1':
        attempts.append(f"EPH_usu_1er_Trim_{year}_txt.zip")

    # 3) Legado ZIP de DBF
    attempts.append(f"t{qnum}{yy}_dbf.zip")

    # 4) Legado RAR de DBF
    attempts.append(f"t{qnum}{yy}_dbf.rar")

    selected = None
    size = 0
    # Probar URLs hasta hallar uno válido
    for fn in attempts:
        trial = f"{base_url}{fn}"
        print(f"INFO: Probando {trial}")
        try:
            with urllib.request.urlopen(trial) as resp:
                size = int(resp.info().get('Content-Length', -1))
        except Exception:
            continue
        if size < 100_000:  # <0.1MB es indicativo de no disponible
            continue
        selected = (fn, trial)
        break

    if not selected:
        raise RuntimeError(f"No se encontró ZIP/RAR válido para {year}-{quarter}")

    filename, url = selected

    local_archive = dest_path / filename
    url = base_url + filename

    size_mb = size / (1 << 20)
    print(f"INFO: Archivo seleccionado {filename} ({size_mb:.2f} MB)")

    local_zip = dest_path / filename
    # Descargar si no existe
    if not local_zip.exists():
        print(f"INFO: Descargando {filename}")
        resp = requests.get(url)
        resp.raise_for_status()
        local_zip.write_bytes(resp.content)
        print(f"INFO: Guardado en {local_zip}")
    else:
        print(f"INFO: {filename} ya existe, omitiendo descarga.")


    normalized = fn.lower().replace('hog_','hogar_').replace('ind_','individual_')
    local_archive.rename(dest_path / normalized)
    filename = normalized

    # ⚠️ ¡MUY IMPORTANTE! Actualizar la referencia al fichero renombrado
    # para que try_zip()/try_rar() apunten al archivo correcto.
    local_archive = dest_path / normalized

    # 2) Intentar desempaquetar
    members = []
    def try_zip(path):
        try:
            print(f"INFO: Extrayendo ZIP {path.name}")
            with zipfile.ZipFile(path, 'r') as zf:
                zf.extractall(dest_path)
                return zf.namelist()
        except Exception as e:
            raise RuntimeError(f"ZIP fallo: {e}")

    def try_rar(path):
        try:
            from patoolib import extract_archive
        except ImportError:
            raise RuntimeError("patoolib no instalado")
        try:
            print(f"INFO: Extrayendo RAR {path.name}")
            extract_archive(str(path), outdir=str(dest_path))
            return [p.name for p in dest_path.iterdir() if p.is_file()]
        except Exception as e:
            raise RuntimeError(f"RAR fallo: {e}")

    # Decide order
    ext = local_archive.suffix.lower()
    tried = set()

    for method in (('zip', try_zip), ('rar', try_rar)):
        kind, fn = method
        if ext == f'.{kind}' or (ext not in ('.zip','.rar') and kind == 'zip'):
            try:
                members = fn(local_archive)
                break
            except RuntimeError as e:
                print(f"WARNING: {e}")
                tried.add(kind)



    # —————————————————————————————————————
    #  Extra handling for legacy DBFs dumped at the root
    # —————————————————————————————————————
    # make sure our subfolders exist
    (dest_path / 'hogar').mkdir(exist_ok=True)
    (dest_path / 'individual').mkdir(exist_ok=True)

    # move any stray Hog_t*.DBF into hogar/
    for stray in dest_path.glob('Hog_t*.DBF'):
        target = dest_path / 'hogar' / stray.name
        print(f"INFO: Normalizing stray DBF → moving {stray.name} into hogar/")
        stray.rename(target)

    # move any stray Ind_t*.DBF into individual/
    for stray in dest_path.glob('Ind_t*.DBF'):
        target = dest_path / 'individual' / stray.name
        print(f"INFO: Normalizing stray DBF → moving {stray.name} into individual/")
        stray.rename(target)


    # Organizar en subcarpetas
    for member in members:
        src = dest_path / member
        if not src.is_file():
            continue
        key = member.lower()
        if 'hogar' in key:
            sub = dest_path / 'hogar'
        elif 'indiv' in key:
            sub = dest_path / 'individual'
        else:
            sub = dest_path / 'other'
        sub.mkdir(exist_ok=True)
        shutil.move(str(src), str(sub / Path(member).name))
    print(f"INFO: Organización completa para {year}-{quarter}")

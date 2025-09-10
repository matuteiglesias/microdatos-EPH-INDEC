
# microdatos-EPH-INDEC

![Python](https://img.shields.io/badge/python-3.7%2B-blue) ![License](https://img.shields.io/badge/license-MIT-lightgrey)


Con **microdatos-EPH-INDEC** tenes las **bases de datos EPH** listas para análisis en un par de segundos.


## Descripción

**microdatos-EPH-INDEC** es una **herramienta de línea de comandos (CLI)** en Python para **descargar**, **extraer** y **convertir** los **microdatos de la Encuesta Permanente de Hogares (EPH)** del **INDEC** en formatos **TXT/CSV**. Automatiza todo el flujo: desde los ZIP/RAR trimestrales en DBF hasta tus datasets listos para análisis (`hogar`, `individual`, `other`).

> 🚀 **Beneficios**:  
> - Descarga instantanea de **microdatos EPH INDEC** (2003–presente)  
> - Conversión de **DBF a CSV/TXT** con separación `;`  
> - Organización automática en carpetas: `hogar/`, `individual/`, `other/`  
> - Limpieza de archivos residuales (ZIP, RAR, backups, carpetas vacías)  
> - Fallbacks robustos para formatos legacy e inconsistencias en nombres de archivos

---

## Público objetivo

- **Investigadores** (economía, sociología, demografía)  
- **Analistas de datos** que necesitan **datasets EPH** reproducibles  
- **Estudiantes** y **profesionales** que trabajan con series de empleo, pobreza e ingresos  

---

## Características

- `fetch-range`: descarga **microdatos EPH** por rango de años y trimestres  
- `fetch`: baja un trimestre específico  
- `extract`: convierte todos los `.zip` y `.rar` a `.dbf`, y estos a `.txt/.csv`.  
- Soporte de convenciones modernas e irre­gulares (2016–2017)  
- Normalización de nombres (`usu_hogar`, `usu_individual`)  
- Manejo de **DBF**, **ZIP**, **RAR** (patoolib)  
- Backup automático de `.dbf` procesados  
- Manejo de **nombres de archivos inesperados** y **fallos de escapechar**  

---

## Instalación

1. Clona el repositorio y entra en él:
   ```bash
   git clone https://github.com/tu-usuario/microdatos-EPH-INDEC.git
   cd microdatos-EPH-INDEC
    ```

2. Crea un entorno virtual e instala:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install .
   ```
3. (Opcional) Instala extras:

   ```bash
   pip install patool    # Para RAR
   pip install simpledbf # Fallback Latin-1
   pip install pysal     # Lectura DBF nativa
   ```

---

## Configuración

En el archivo `eph_extractor/settings.yaml` se apunta al FTP del INDEC:

```yaml
ftp_url: "https://www.indec.gob.ar/ftp/cuadros/menusuperior/eph/"
```

---

## Uso

Situate en la carpeta donde quieras tener los microdatos, por ejemplo:

```bash
mkdir microdatos-eph
cd microdatos-eph
```

Opcionalmente, para remover residuos de pruebas previas:

```bash
rm -rf raw/eph
```

### 1) Descargar microdatos (DBF/ZIP)

```bash
# Todos los trimestres de 2003 a 2025 en raw/dbf/
eph-extractor fetch-range \
  --start-year 2003 \
  --end-year   2025 \
  --out        raw/eph
```

### 2) Extraer y convertir a TXT/CSV

```bash
# Convierte .dbf → .txt (sep=";") y organiza en raw/txt/
eph-extractor extract \
  --dir raw/eph \
  --out raw/txt
```

### 3) Atajos

* Solo un trimestre:

  ```bash
  eph-extractor fetch  --year 2024 --quarter Q3 --out raw/eph
  eph-extractor extract --dir raw/eph       --out raw/txt
  ```
* Mantener ZIP/RAR con `--keep-zip`

---

## Estructura de salida

```
raw/
└── eph/
    ├── hogar/        # usu_hogar_t*.txt
    ├── individual/   # usu_individual_t*.txt
    └── other/        # notas, PDF, etc.
```

Todos los `.dbf` procesados van a `raw/dbf/dbf_backup/`.

---

## Palabras clave

> **microdatos EPH INDEC** • **Descarga EPH trimestral** • **CLI Python EPH** • **DBF a CSV** • **Datos ENCUESTA PERMANENTE DE HOGARES** • **Bases de datos EPH txt** • **microdatos hogar individual** • **INDEC microdatos** • **Series longitudinales EPH**

---

## Soporte y Contribución

1. **Issues**: abri un ticket si encuentras errores o sugerencias.
2. **Pull requests**: mejoras de funcionalidades, nuevos formatos, tests.
3. **Licencia**: MIT.

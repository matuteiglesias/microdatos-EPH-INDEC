
## Microdatos de la Encuesta Permanente de Hogares INDEC

### Introducción


Welcome to the INDEC EPH microdata repository! Here you will find the individual and household microdata from the Encuesta Permanente de Hogares (EPH) survey conducted by INDEC, the National Institute of Statistics and Census of Argentina. The EPH is a quarterly household survey that provides information on various topics such as employment, education, and living conditions. If you use these data in your research or analysis, please be sure to cite the INDEC website (www.indec.gob.ar) as the primary source of the data. In addition to the microdata, this repository also includes a notebook with code for downloading historical data in dbf format, as well as new data releases. 

Thank you for visiting and we hope these data are useful to you!

---

La EPH es una encuesta de hogares que se realiza trimestralmente y permite obtener información sobre la estructura y el funcionamiento de los hogares, las características de las personas que los integran y sus actividades económicas.

El script principal "actualizador.py" tiene como objetivo descargar, descomprimir y organizar los datos de la Encuesta Permanente de Hogares (EPH) del INDEC. Este script descarga los archivos ZIP de la EPH desde el sitio web del INDEC, los descomprime y organiza los archivos descomprimidos en las carpetas "individual" y "hogar", según corresponda.

El notebook "extract_dbf_files.ipynb" se utiliza para descargar series históricas de la EPH. Este cuaderno contiene códigos para descargar y procesar archivos DBF de la EPH de años anteriores, y generar archivos CSV a partir de ellos. Los archivos DBF son un formato antiguo de base de datos, y este cuaderno muestra cómo convertirlos a un formato más moderno y utilizable.

###  Instalación y uso

clonar repositorio para tener los microdatos en tu PC.

`git clone https://github.com/matuteiglesias/microdatos-EPH-INDEC.git`
###   Requisitos previos y dependencias

Instalar librerias con pip. I.e. en una terminal, o en una interfaz de python:

`pip install requests` 

`pip install zipfile` 

etc...

**Para acceder a los microdatos**

Python:

```python
import pandas as pd
import requests

# Define the URL for the data file
url = 'https://raw.githubusercontent.com/matuteiglesias/microdatos-EPH-INDEC/master/microdatos/individual/usu_individual_t104.txt'

# Download the data file
response = requests.get(url)
if response.status_code == 200:
    data = response.content.decode('utf-8')
    # Convert the data to a DataFrame
    df = pd.read_csv(pd.compat.StringIO(data), delimiter=';')
    print(df.head())
else:
    print(f"File not found: {url}")
```

R:

```R
library(httr)
library(readr)

# Define the URL for the data file
url <- 'https://raw.githubusercontent.com/matuteiglesias/microdatos-EPH-INDEC/master/microdatos/individual/usu_individual_t104.txt'

# Download the data file
response <- GET(url)
if (status_code(response) == 200) {
    data <- content(response, "text")
    # Convert the data to a DataFrame
    df <- read_delim(data, delim = ";")
    print(head(df))
} else {
    print(paste("File not found:", url))
}
```

**Para utilizar el script `actualizador.py`**

`python actualizador.py`
 
Por default descarga los ultimos 5 trimestres disponibles.


### Actualizaciones Automaticas:

El codigo en actualizador.py se corre todos los dias localmente, y asi se incorporan nuevos datos publicados por INDEC en un plazo de menos de 24 hs. Por lo general, los microdatos se publican cerca de 130 dias despues de terminado cada trimestre.

Gracias a esto, **no necesita correr los scripts de python, el git clone por si solo ya contiene todos los microdatos que hayan sido publicados desde 2003.**


<!-- Description of the data -->
<!-- se podria agregar un cosito que diga cuando se subio el ultimo dataset... -->

Las ultimas actualizaciones se dieron en fechas:

   - 2021Q3: 12-02-2022 (135 dias)
   - 2021Q4: 14-05-2022 (134 dias)
   - 2022Q1: 05-08-2022 (127 dias)
   - 2022Q2: 05-11-2022 (122 dias)
   
###  Fuentes y citas
**Enlace a la página del INDEC donde se encuentran los datos originales**

Cualquier publicación basada en los archivos de microdatos de la EPH debe citar a INDEC como la fuente primaria de los datos. Link a los [datos originales, 2016-2022](https://www.indec.gob.ar/indec/web/Institucional-Indec-BasesDeDatos)
    
 **Citar solucion de sotware si te resulto de ayuda:**

Iglesias, M. (Fecha de acceso). Microdatos EPH INDEC. Recuperado de https://github.com/matuteiglesias/microdatos-EPH-INDEC.

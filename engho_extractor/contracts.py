"""Stable source and table contracts for INDEC ENGHo 2017/18 custody."""
from __future__ import annotations

from dataclasses import dataclass

ARTIFACT_TYPE = "publicdata.indec-engho-microdata/v1"
DATASET_FAMILY = "ENGHo"
SURVEY_VINTAGE = "2017-2018"
EXTRACTION_CONTRACT_VERSION = "engho-2017-18-zip-text-v1"
OFFICIAL_BASE_URL = "https://www.indec.gob.ar/ftp/cuadros/menusuperior/engho"
SOURCE_LANDING_PAGE = "https://www.indec.gob.ar/Institucional/Indec/BasesDeDatos"
DOCUMENTATION = (
    {
        "kind": "user_manual",
        "url": "https://www.indec.gob.ar/ftp/cuadros/menusuperior/engho/engho2017_18_manual_uso_bases.pdf",
    },
    {
        "kind": "replicate_weight_methodology",
        "url": "https://www.indec.gob.ar/ftp/cuadros/menusuperior/engho/engho2017_18_nota_tecnica_4.pdf",
    },
)


@dataclass(frozen=True)
class SourceSpec:
    role: str
    filename: str
    normalized_filename: str
    required_columns: tuple[str, ...]

    @property
    def url(self) -> str:
        return f"{OFFICIAL_BASE_URL}/{self.filename}"


SOURCES = (
    SourceSpec("expenditures", "engho2018_gastos.zip", "expenditures.txt",
               ("id", "miembro", "articulo", "forma_pago", "tipo_negocio", "modo_adq", "lugar_adq")),
    SourceSpec("persons", "engho2018_personas.zip", "persons.txt", ("id", "miembro")),
    SourceSpec("households", "engho2018_hogares.zip", "households.txt", ("id",)),
    SourceSpec("replicate_weights", "engho2018_replicas.zip", "replicate_weights.txt", ("id",)),
    SourceSpec("articles", "engho2018_articulos.zip", "articles.txt", ("articulo",)),
)
SOURCE_BY_ROLE = {item.role: item for item in SOURCES}
SOURCE_BY_FILENAME = {item.filename: item for item in SOURCES}
REQUIRED_ROLES = tuple(item.role for item in SOURCES)

# Published dimensions from INDEC's user manual. These are commissioning targets,
# not parser assumptions and are never required by synthetic/unit fixtures.
PUBLISHED_ROW_TARGETS = {
    "households": 21_547,
    "persons": 68_675,
    "expenditures": 901_804,
    "replicate_weights": 21_547,
    "articles": 1_224,
}

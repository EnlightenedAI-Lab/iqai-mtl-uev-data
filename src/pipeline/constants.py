"""Official Ville de Montréal evaluation-unit identities. Do not invent fields."""

DATASET_ID = "4ad6baea-4d2c-460f-a8bf-5d000db498f7"
DATASET_SLUG = "unites-evaluation-fonciere"
DATASET_TITLE = "Unités d'évaluation foncière"
PROVIDER = "Ville de Montréal"
PUBLISHER_UNIT = "Service des finances et de l'évaluation foncière"
CATALOG_URL = "https://donnees.montreal.ca/dataset/unites-evaluation-fonciere"
PACKAGE_API_URL = (
    "https://donnees.montreal.ca/api/3/action/package_show"
    "?id=unites-evaluation-fonciere"
)
LICENSE_ID = "CC-BY-4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
LICENSE_NAME = "Creative Commons Attribution 4.0 International"

GEOJSON_RESOURCE_ID = "866a3dbc-8b59-48ff-866d-f2f9d3bbee9d"
GEOJSON_DOWNLOAD_URL = (
    "https://donnees.montreal.ca/dataset/"
    f"{DATASET_ID}/resource/{GEOJSON_RESOURCE_ID}/download/"
    "uniteevaluationfonciere.geojson.zip"
)
GEOJSON_CRS_DECLARED = "WGS84"
SHP_RESOURCE_ID = "43c2cccf-a439-429b-a3c8-5d4ebce53e1b"
SHP_CRS_DECLARED = "MTM8 NAD83"

OBJECT_CLASS = "evaluation_unit"
OBJECT_CLASS_LABEL = "EVALUATION UNIT"
IDENTITY_FIELD_PREFERRED = "ID_UEV"

LEGAL_NOTE = (
    "This is a municipal property-assessment / evaluation-unit division "
    "(unité d'évaluation foncière). It has no legal cadastral value and "
    "must not be confused with cadastre or proof of ownership."
)

# Official data dictionary (publisher text, 2026-08-19 package metadata).
# Meanings are copied from the CKAN methodology block; they are not IQAI guesses.
OFFICIAL_FIELDS = {
    "ID_UEV": {
        "meaning": "Identifiant unique système.",
        "official_type": "numérique",
        "operator_use": "Stable source identity.",
        "keep": True,
    },
    "CIVIQUE_DEBUT": {
        "meaning": "Numéro civique (plage - début).",
        "official_type": "numérique",
        "operator_use": "Address range start.",
        "keep": True,
    },
    "CIVIQUE_FIN": {
        "meaning": "Numéro civique (plage - fin).",
        "official_type": "numérique",
        "operator_use": "Address range end.",
        "keep": True,
    },
    "NOM_RUE": {
        "meaning": "Nom de rue.",
        "official_type": "texte variable",
        "operator_use": "Street name.",
        "keep": True,
    },
    "SUITE_DEBUT": {
        "meaning": "Numéro unité (appartement ou local).",
        "official_type": "texte variable",
        "operator_use": "Unit/suite number.",
        "keep": True,
    },
    "ETAGE_HORS_SOL": {
        "meaning": (
            "Nombre d'étages maximal: si l'UEF comprend un seul bâtiment, "
            "étages du bâtiment; si plusieurs bâtiments, étages du bâtiment "
            "en comptant le plus d'étages."
        ),
        "official_type": "numérique",
        "operator_use": "Above-ground storeys (assessment rule, not survey).",
        "keep": True,
    },
    "NOMBRE_LOGEMENT": {
        "meaning": "Nombre de logements.",
        "official_type": "numérique",
        "operator_use": "Dwelling count on the evaluation unit.",
        "keep": True,
    },
    "ANNEE_CONSTRUCTION": {
        "meaning": "Année de construction.",
        "official_type": "numérique",
        "operator_use": "Construction year on the roll.",
        "keep": True,
    },
    "CODE_UTILISATION": {
        "meaning": "Codification CUBF.",
        "official_type": "numérique",
        "operator_use": "CUBF land-use code; basis for use aggregation.",
        "keep": True,
    },
    "LETTRE_DEBUT": {
        "meaning": "Première lettre de l'appartement.",
        "official_type": "texte variable",
        "operator_use": "Apartment letter start.",
        "keep": True,
    },
    "LETTRE_FIN": {
        "meaning": "Dernière lettre de l'appartement.",
        "official_type": "texte variable",
        "operator_use": "Apartment letter end.",
        "keep": True,
    },
    "LIBELLE_UTILISATION": {
        "meaning": "Descriptif CUBF.",
        "official_type": "texte variable",
        "operator_use": "CUBF land-use label.",
        "keep": True,
    },
    "CATEGORIE_UEF": {
        "meaning": "Catégorie unité évaluation (Régulier ou Condominium).",
        "official_type": "liste de valeur",
        "operator_use": "Regular vs condominium evaluation unit.",
        "keep": True,
    },
    "MATRICULE83": {
        "meaning": "Matricule au rôle foncier (système géographique NAD83 MT8).",
        "official_type": "numérique",
        "operator_use": "Assessment-roll matricule; not a substitute for ID_UEV.",
        "keep": True,
    },
    "SUPERFICIE_TERRAIN": {
        "meaning": (
            "Superficie du terrain pour fin d'évaluation foncière (mètres carrés)."
        ),
        "official_type": "numérique",
        "operator_use": "Land area for assessment purposes.",
        "keep": True,
    },
    "SUPERFICIE_BATIMENT": {
        "meaning": (
            "Surface brute correspondant à la somme des aires de chacun des "
            "étages du bâtiment principal et, le cas échéant, de l'attique. "
            "Ne s'applique pas si plusieurs bâtiments principaux. Copropriété "
            "divise: surface brute des étages de la partie privative (m²)."
        ),
        "official_type": "numérique",
        "operator_use": "Building area for assessment purposes; often null for multi-building units.",
        "keep": True,
    },
    "NO_ARROND_ILE_CUM": {
        "meaning": "Identifiant de l'arrondissement (référence identifiant MAMH).",
        "official_type": "numérique",
        "operator_use": "Borough identifier code; not joined to a borough name table in V1.",
        "keep": True,
    },
    "MUNICIPALITE": {
        "meaning": "Identifiant interne de la municipalité.",
        "official_type": "numérique",
        "operator_use": "Agglomeration municipality code.",
        "keep": True,
    },
}

MUNICIPALITY_CODES = {
    "02": "Baie-D'Urfé",
    "03": "Beaconsfield",
    "04": "Côte-Saint-Luc",
    "05": "Dollard-Des Ormeaux",
    "06": "Dorval",
    "07": "Hampstead",
    "10": "Kirkland",
    "09": "L'Île-Dorval",
    "13": "Mont-Royal",
    "50": "Montréal",
    "14": "Montréal-Est",
    "15": "Montréal-Ouest",
    "20": "Pointe-Claire",
    "23": "Sainte-Anne-de-Bellevue",
    "22": "Senneville",
    "29": "Westmount",
}

NULL_NUMERIC_SENTINEL = -1

USER_AGENT = "IQAI-Data-Fabric-Helper/mtl-uev-v1 (open-data; cc-by-4.0)"
COORD_DECIMALS = 6
CELL_DEG = 0.01
MAX_CELL_FEATURES = 3500
MAX_CELL_BYTES = 1_800_000
MIN_CELL_DEG = 0.0025
ORIGIN_X = -74.10
ORIGIN_Y = 45.35

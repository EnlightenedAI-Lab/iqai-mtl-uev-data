"""Build the citywide Montréal evaluation-unit static spatial package.

Standalone on purpose: one file, official CKAN GeoJSON zip, partitioned cells.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import sys
import time
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

import ijson
from shapely.geometry import shape
from shapely.ops import unary_union
from shapely.validation import make_valid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pipeline.constants import (  # noqa: E402
    CATALOG_URL,
    CELL_DEG,
    DATASET_ID,
    DATASET_TITLE,
    GEOJSON_CRS_DECLARED,
    IDENTITY_FIELD_PREFERRED,
    LEGAL_NOTE,
    LICENSE_ID,
    LICENSE_NAME,
    LICENSE_URL,
    MAX_CELL_BYTES,
    MAX_CELL_FEATURES,
    MIN_CELL_DEG,
    MUNICIPALITY_CODES,
    OBJECT_CLASS,
    OBJECT_CLASS_LABEL,
    OFFICIAL_FIELDS,
    ORIGIN_X,
    ORIGIN_Y,
    PACKAGE_API_URL,
    PROVIDER,
    PUBLISHER_UNIT,
    USER_AGENT,
    COORD_DECIMALS,
    NULL_NUMERIC_SENTINEL,
)

CACHE = ROOT / "cache"
DIST = ROOT / "dist"
SITE = ROOT / "_site"
SOURCE_ZIP = CACHE / "source" / "uniteevaluationfonciere.geojson.zip"


def log(message: str) -> None:
    print(message, flush=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def dump_json(path: Path, payload: Any) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    path.write_text(text, encoding="utf-8")
    return path.stat().st_size


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def as_number(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value == int(value):
            return int(value)
        return float(value)
    return value


def quantize_coords(value: Any) -> Any:
    if isinstance(value, Decimal):
        return round(float(value), COORD_DECIMALS)
    if isinstance(value, (int, float)):
        return round(float(value), COORD_DECIMALS)
    if isinstance(value, list):
        return [quantize_coords(item) for item in value]
    return value


def walk_coords(value: Any) -> Iterator[tuple[float, float]]:
    if not value:
        return
    if isinstance(value[0], (int, float, Decimal)) and len(value) >= 2:
        yield float(value[0]), float(value[1])
        return
    for item in value:
        yield from walk_coords(item)


def geom_bbox(geom: dict | None) -> list[float] | None:
    if not geom:
        return None
    xs: list[float] = []
    ys: list[float] = []
    for x, y in walk_coords(geom.get("coordinates")):
        xs.append(x)
        ys.append(y)
    if not xs:
        return None
    return [min(xs), min(ys), max(xs), max(ys)]


def is_lonlat(bbox: list[float] | None) -> bool:
    if not bbox:
        return False
    return abs(bbox[0]) <= 180 and abs(bbox[2]) <= 180 and abs(bbox[1]) <= 90 and abs(bbox[3]) <= 90


def compact_geometry(geom: dict) -> dict:
    return {"type": geom.get("type"), "coordinates": quantize_coords(geom.get("coordinates"))}


def geometry_hash(geom: dict | None) -> str:
    payload = json.dumps(geom, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def prepare_geometry(geom: dict | None) -> tuple[dict | None, list[float] | None, bool]:
    if not geom:
        return None, None, False
    compact = compact_geometry(geom)
    try:
        g = shape(compact)
    except Exception:
        return None, None, False
    if g.is_empty:
        return None, None, False
    repaired = False
    if not g.is_valid:
        g = make_valid(g)
        repaired = True
    if g.is_empty:
        return None, None, repaired
    if g.geom_type == "GeometryCollection":
        polys = [part for part in g.geoms if part.geom_type in {"Polygon", "MultiPolygon"}]
        if not polys:
            return None, None, repaired
        g = unary_union(polys)
        repaired = True
    if g.geom_type not in {"Polygon", "MultiPolygon"}:
        return None, None, repaired
    out = compact_geometry(json.loads(json.dumps(g.__geo_interface__)))
    return out, geom_bbox(out), repaired


def normalize_null(value: Any) -> Any:
    if value == NULL_NUMERIC_SENTINEL:
        return None
    if value == "-1":
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def stringify_id(value: Any) -> str | None:
    value = normalize_null(value)
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    text = str(value).strip()
    return text or None


def http_json(url: str, timeout: int = 90) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def fetch_package() -> dict:
    payload = http_json(PACKAGE_API_URL)
    if not payload.get("success"):
        raise SystemExit(f"CKAN package_show failed: {payload}")
    return payload["result"]


def geojson_resource(package: dict) -> dict:
    for resource in package.get("resources") or []:
        fmt = str(resource.get("format") or "").lower()
        url = str(resource.get("url") or "").lower()
        if fmt == "geojson" or url.endswith(".geojson.zip"):
            return resource
    raise SystemExit("No GeoJSON resource in CKAN package")


def download_file(url: str, dest: Path, timeout: int = 900) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    started = time.time()
    retrieved_at = utc_now()
    with urllib.request.urlopen(req, timeout=timeout) as res, tmp.open("wb") as out:
        headers = {k.lower(): v for k, v in res.headers.items()}
        final_url = res.geturl()
        while True:
            chunk = res.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
    tmp.replace(dest)
    return {
        "url": url,
        "final_url": final_url,
        "retrieved_at": retrieved_at,
        "elapsed_s": round(time.time() - started, 3),
        "bytes": dest.stat().st_size,
        "http_last_modified": headers.get("last-modified"),
        "etag": headers.get("etag"),
        "content_type": headers.get("content-type"),
    }


def cell_key(ix: int, iy: int, size: float) -> str:
    step = f"{size:.4f}".rstrip("0").rstrip(".")
    return f"c_{step}_{ix}_{iy}"


def make_cell_bbox(ix: int, iy: int, size: float) -> list[float]:
    minx = ORIGIN_X + ix * size
    miny = ORIGIN_Y + iy * size
    return [round(minx, 6), round(miny, 6), round(minx + size, 6), round(miny + size, 6)]


def pick_identity(props: dict) -> tuple[str | None, str | None]:
    for key in (IDENTITY_FIELD_PREFERRED, "ID_UEV", "id_uev", "IDUEV"):
        if key not in props:
            continue
        ident = stringify_id(props.get(key))
        if ident:
            return key, ident
    return None, None


def source_props(props: dict) -> dict:
    out = {}
    for key, value in (props or {}).items():
        value = as_number(value)
        if isinstance(value, float) and value.is_integer() and abs(value) < 1e15:
            out[key] = int(value)
        else:
            out[key] = value
    return out


def normalized_unit(props: dict, identity_field: str, source_id: str) -> dict:
    src = source_props(props)
    mun = stringify_id(src.get("MUNICIPALITE"))
    mun_key = mun.zfill(2) if mun and mun.isdigit() else (mun or "")
    return {
        "source_id": source_id,
        "source_id_field": identity_field,
        "civic_from": normalize_null(src.get("CIVIQUE_DEBUT")),
        "civic_to": normalize_null(src.get("CIVIQUE_FIN")),
        "street": normalize_null(src.get("NOM_RUE")),
        "suite": normalize_null(src.get("SUITE_DEBUT")),
        "letter_from": normalize_null(src.get("LETTRE_DEBUT")),
        "letter_to": normalize_null(src.get("LETTRE_FIN")),
        "storeys": normalize_null(src.get("ETAGE_HORS_SOL")),
        "dwellings": normalize_null(src.get("NOMBRE_LOGEMENT")),
        "year_built": normalize_null(src.get("ANNEE_CONSTRUCTION")),
        "cubf_code": stringify_id(normalize_null(src.get("CODE_UTILISATION"))),
        "cubf_label": normalize_null(src.get("LIBELLE_UTILISATION")),
        "category": normalize_null(src.get("CATEGORIE_UEF")),
        "matricule83": stringify_id(src.get("MATRICULE83")),
        "land_area_m2": normalize_null(src.get("SUPERFICIE_TERRAIN")),
        "building_area_m2": normalize_null(src.get("SUPERFICIE_BATIMENT")),
        "borough_code": stringify_id(src.get("NO_ARROND_ILE_CUM")),
        "municipality_code": mun,
        "municipality_name": MUNICIPALITY_CODES.get(mun_key),
        "source": src,
    }


def assemble_cell(key: str, ix: int, iy: int, size: float, records: list[dict]) -> dict:
    grouped: dict[str, list] = defaultdict(list)
    geom_by_hash: dict[str, dict] = {}
    for rec in records:
        grouped[rec["ghash"]].append(rec["unit"])
        geom_by_hash[rec["ghash"]] = rec["geometry"]
    features = []
    for ghash, units in grouped.items():
        features.append(
            {
                "type": "Feature",
                "geometry": geom_by_hash[ghash],
                "properties": {
                    "object_class": OBJECT_CLASS,
                    "object_class_label": OBJECT_CLASS_LABEL,
                    "unit_count": len(units),
                    "source_ids": [unit["source_id"] for unit in units],
                    "units": units,
                    "stacked": len(units) > 1,
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "cell": key,
        "bbox": make_cell_bbox(ix, iy, size),
        "footprint_count": len(features),
        "unit_count": len(records),
        "features": features,
    }


def maybe_split_cell(size: float, ix: int, iy: int, records: list[dict], cells_out: dict) -> None:
    key = cell_key(ix, iy, size)
    payload = assemble_cell(key, ix, iy, size, records)
    encoded_len = len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    too_big = (
        payload["unit_count"] > MAX_CELL_FEATURES or encoded_len > MAX_CELL_BYTES
    ) and (size / 2) >= MIN_CELL_DEG
    if not too_big:
        cells_out[key] = payload
        return
    child = size / 2
    buckets: dict[tuple[int, int], list] = defaultdict(list)
    for rec in records:
        bbox = rec["bbox"]
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        ci = math.floor((cx - ORIGIN_X) / child)
        cj = math.floor((cy - ORIGIN_Y) / child)
        buckets[(ci, cj)].append(rec)
    log(f"split {key} units={payload['unit_count']} bytes={encoded_len} -> {len(buckets)} children")
    for (ci, cj), rows in buckets.items():
        maybe_split_cell(child, ci, cj, rows, cells_out)


def write_field_dictionary(observed: dict[str, dict]) -> dict:
    fields = []
    seen = set()
    for name, spec in OFFICIAL_FIELDS.items():
        obs = observed.get(name) or {}
        fields.append(
            {
                "name": name,
                "origin": "publisher_dictionary",
                "meaning": spec["meaning"],
                "official_type": spec["official_type"],
                "observed_types": obs.get("types") or [],
                "null_count": obs.get("nulls", 0),
                "observed_count": obs.get("count", 0),
                "nullable": True,
                "keep": spec["keep"],
                "operator_use": spec["operator_use"],
            }
        )
        seen.add(name)
    for name, obs in observed.items():
        if name in seen:
            continue
        fields.append(
            {
                "name": name,
                "origin": "observed_in_source_file",
                "meaning": None,
                "official_type": None,
                "observed_types": obs.get("types") or [],
                "null_count": obs.get("nulls", 0),
                "observed_count": obs.get("count", 0),
                "nullable": True,
                "keep": True,
                "operator_use": (
                    "Present in the official GeoJSON extract; meaning not copied "
                    "from the publisher dictionary."
                ),
            }
        )
    payload = {
        "dataset": DATASET_TITLE,
        "dataset_id": DATASET_ID,
        "identity_field": IDENTITY_FIELD_PREFERRED,
        "numeric_null_sentinel": -1,
        "numeric_null_rule": "Publisher: numeric value -1 is equivalent to Null / not applicable.",
        "fields": fields,
    }
    dump_json(DIST / "field-dictionary.json", payload)
    return payload


def copy_site() -> None:
    runtime = ROOT / "src" / "runtime"
    proof = ROOT / "src" / "proof"
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "js").mkdir(parents=True)
    (SITE / "css").mkdir(parents=True)
    shutil.copytree(DIST, SITE / "data")
    for folder in (runtime, proof):
        if not folder.exists():
            continue
        for src in folder.glob("*.js"):
            shutil.copy2(src, SITE / "js" / src.name)
        for src in folder.glob("*.css"):
            shutil.copy2(src, SITE / "css" / src.name)
        for src in folder.glob("*.html"):
            shutil.copy2(src, SITE / src.name)


def build() -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    DIST.mkdir(parents=True, exist_ok=True)
    package = fetch_package()
    resource = geojson_resource(package)
    url = resource["url"]
    log(f"official GeoJSON resource {resource.get('id')} last_modified={resource.get('last_modified')}")
    if SOURCE_ZIP.exists() and SOURCE_ZIP.stat().st_size > 1_000_000:
        log(f"reuse just-downloaded zip {SOURCE_ZIP} ({SOURCE_ZIP.stat().st_size} bytes)")
        dl = {
            "url": url,
            "final_url": url,
            "retrieved_at": utc_now(),
            "elapsed_s": 0,
            "bytes": SOURCE_ZIP.stat().st_size,
            "http_last_modified": resource.get("last_modified"),
            "etag": None,
            "content_type": "application/zip",
            "reused_local_current_extract": True,
        }
    else:
        log(f"download {url}")
        dl = download_file(url, SOURCE_ZIP)
    zip_sha = sha256_file(SOURCE_ZIP)

    observed: dict[str, dict] = {}
    identity_field = None
    ids: set[str] = set()
    duplicate_ids = 0
    null_geom = 0
    invalid_geom = 0
    empty_geom = 0
    geom_types: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    feature_count = 0
    city_bbox = None
    first_bbox = None
    stacked_hash: Counter[str] = Counter()
    cells_raw: dict[tuple[float, int, int], list] = defaultdict(list)
    member = None
    uncompressed = 0

    with zipfile.ZipFile(SOURCE_ZIP) as zf:
        names = [
            name
            for name in zf.namelist()
            if name.lower().endswith((".geojson", ".json")) and not name.endswith("/")
        ]
        if not names:
            raise SystemExit(f"no geojson in zip: {zf.namelist()}")
        member = names[0]
        uncompressed = zf.getinfo(member).file_size
        log(f"stream {member} uncompressed={uncompressed}")
        with zf.open(member) as handle:
            for feature in ijson.items(handle, "features.item"):
                feature_count += 1
                props = feature.get("properties") or {}
                geom = feature.get("geometry")
                field, source_id = pick_identity(props)
                if field:
                    identity_field = identity_field or field
                for key, value in props.items():
                    slot = observed.setdefault(key, {"count": 0, "nulls": 0, "types": set()})
                    slot["count"] += 1
                    if value is None or value == "" or value == -1 or value == Decimal(-1):
                        slot["nulls"] += 1
                    slot["types"].add(type(value).__name__)
                if not geom:
                    null_geom += 1
                    continue
                compact, bbox, repaired = prepare_geometry(geom)
                if first_bbox is None:
                    first_bbox = bbox
                if compact is None or bbox is None:
                    empty_geom += 1
                    continue
                if repaired:
                    invalid_geom += 1
                if city_bbox is None:
                    city_bbox = bbox[:]
                else:
                    city_bbox[0] = min(city_bbox[0], bbox[0])
                    city_bbox[1] = min(city_bbox[1], bbox[1])
                    city_bbox[2] = max(city_bbox[2], bbox[2])
                    city_bbox[3] = max(city_bbox[3], bbox[3])
                geom_types[compact.get("type") or "Unknown"] += 1
                if not source_id:
                    continue
                if source_id in ids:
                    duplicate_ids += 1
                    continue
                ids.add(source_id)
                ghash = geometry_hash(compact)
                stacked_hash[ghash] += 1
                unit = normalized_unit(props, field or IDENTITY_FIELD_PREFERRED, source_id)
                categories[str(unit.get("category"))] += 1
                rec = {"ghash": ghash, "geometry": compact, "bbox": bbox, "unit": unit}
                cx = (bbox[0] + bbox[2]) / 2
                cy = (bbox[1] + bbox[3]) / 2
                ix = math.floor((cx - ORIGIN_X) / CELL_DEG)
                iy = math.floor((cy - ORIGIN_Y) / CELL_DEG)
                cells_raw[(CELL_DEG, ix, iy)].append(rec)
                if feature_count % 50000 == 0:
                    log(f"  scanned {feature_count} kept {len(ids)}")

    if not is_lonlat(first_bbox):
        raise SystemExit(f"source coordinates are not WGS84 lon/lat: first bbox {first_bbox}")

    for meta in observed.values():
        meta["types"] = sorted(meta["types"])

    dictionary = write_field_dictionary(observed)
    stacked_groups = sum(1 for n in stacked_hash.values() if n > 1)
    stacked_units = sum(n for n in stacked_hash.values() if n > 1)
    unique_footprints = len(stacked_hash)

    cells_out: dict[str, dict] = {}
    for (size, ix, iy), rows in cells_raw.items():
        maybe_split_cell(size, ix, iy, rows, cells_out)

    cells_dir = DIST / "cells"
    if cells_dir.exists():
        for old in cells_dir.glob("*.json"):
            old.unlink()
    cell_manifest = []
    max_bytes = 0
    for key, payload in sorted(cells_out.items()):
        path = cells_dir / f"{key}.json"
        nbytes = dump_json(path, payload)
        max_bytes = max(max_bytes, nbytes)
        cell_manifest.append(
            {
                "id": key,
                "path": f"cells/{key}.json",
                "bbox": payload["bbox"],
                "unit_count": payload["unit_count"],
                "footprint_count": payload["footprint_count"],
                "bytes": nbytes,
            }
        )

    extras = {item.get("key"): item.get("value") for item in (package.get("extras") or [])}
    manifest = {
        "package": "iqai.mtl.evaluation-units.v1",
        "object_class": OBJECT_CLASS,
        "object_class_label": OBJECT_CLASS_LABEL,
        "provider": PROVIDER,
        "publisher_unit": PUBLISHER_UNIT,
        "dataset": DATASET_TITLE,
        "dataset_id": DATASET_ID,
        "catalog_url": CATALOG_URL,
        "license": {"id": LICENSE_ID, "name": LICENSE_NAME, "url": LICENSE_URL},
        "crs": "EPSG:4326",
        "geometry_type": "Polygon",
        "identity_field": identity_field or IDENTITY_FIELD_PREFERRED,
        "legal_note": LEGAL_NOTE,
        "bbox": city_bbox,
        "cell_scheme": {
            "type": "lonlat-grid-adaptive",
            "origin": [ORIGIN_X, ORIGIN_Y],
            "base_cell_deg": CELL_DEG,
            "min_cell_deg": MIN_CELL_DEG,
            "coord_decimals": COORD_DECIMALS,
        },
        "counts": {
            "features_scanned": feature_count,
            "units_kept": len(ids),
            "unique_footprints": unique_footprints,
            "stacked_groups": stacked_groups,
            "stacked_units": stacked_units,
            "null_geometry": null_geom,
            "empty_geometry": empty_geom,
            "invalid_geometry_repaired": invalid_geom,
            "duplicate_source_ids_dropped": duplicate_ids,
            "cells": len(cell_manifest),
        },
        "geometry_types": dict(geom_types),
        "categories": dict(categories),
        "max_cell_bytes": max_bytes,
        "cells": cell_manifest,
    }
    dump_json(DIST / "manifest.json", manifest)
    provenance = {
        "retrieved_at": dl["retrieved_at"],
        "official_resource_url": url,
        "resource_id": resource.get("id"),
        "resource_name": resource.get("name"),
        "resource_last_modified": resource.get("last_modified"),
        "package_metadata_modified": package.get("metadata_modified"),
        "source_filename": Path(url).name,
        "zip_member": member,
        "compressed_bytes": SOURCE_ZIP.stat().st_size,
        "extracted_bytes": uncompressed,
        "format": "GeoJSON zip",
        "declared_crs": GEOJSON_CRS_DECLARED,
        "runtime_crs": "EPSG:4326",
        "sha256_zip": zip_sha,
        "http_last_modified": dl.get("http_last_modified"),
        "etag": dl.get("etag"),
        "download_elapsed_s": dl.get("elapsed_s"),
        "update_frequency": package.get("frequency") or extras.get("frequency"),
        "temporal": "2017-09-28/ (open-ended catalog coverage; not a capture date)",
        "legal_note": LEGAL_NOTE,
        "attribution": (
            "Données © Ville de Montréal — Unités d'évaluation foncière "
            "(CC BY 4.0). IQAI static spatial package is a derived partition "
            "for viewport access; it is not an official municipal service."
        ),
    }
    dump_json(DIST / "provenance.json", provenance)
    (DIST / "ATTRIBUTION.md").write_text(
        (
            "# Attribution\n\n"
            "Source: Ville de Montréal — Unités d'évaluation foncière\n"
            f"Catalogue: {CATALOG_URL}\n"
            f"Licence: {LICENSE_NAME} ({LICENSE_URL})\n\n"
            f"{LEGAL_NOTE}\n\n"
            "IQAI partitions the official extract for viewport fetching. "
            "This package is not legal cadastre and not proof of ownership.\n"
        ),
        encoding="utf-8",
    )
    copy_site()
    summary = {
        "units": len(ids),
        "cells": len(cell_manifest),
        "max_cell_bytes": max_bytes,
        "zip_sha256": zip_sha,
        "identity_field": identity_field,
        "bbox": city_bbox,
        "compressed_bytes": SOURCE_ZIP.stat().st_size,
        "extracted_bytes": uncompressed,
        "retrieved_at": dl["retrieved_at"],
        "official_resource_url": url,
        "resource_last_modified": resource.get("last_modified"),
        "categories": dict(categories),
        "stacked_groups": stacked_groups,
        "stacked_units": stacked_units,
    }
    dump_json(DIST / "build-summary.json", summary)
    log(json.dumps(summary))
    return {
        "manifest": manifest,
        "provenance": provenance,
        "dictionary": dictionary,
        "summary": summary,
    }


if __name__ == "__main__":
    build()

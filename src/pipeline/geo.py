from __future__ import annotations

import hashlib
import json
from typing import Any, Iterator

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.validation import make_valid

from .constants import COORD_DECIMALS, NULL_NUMERIC_SENTINEL


def quantize_coords(value: Any) -> Any:
    if isinstance(value, (int, float)):
        return round(float(value), COORD_DECIMALS)
    if isinstance(value, list):
        return [quantize_coords(item) for item in value]
    return value


def walk_coords(value: Any) -> Iterator[tuple[float, float]]:
    if not value:
        return
    if isinstance(value[0], (int, float)) and len(value) >= 2:
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


def shapely_geom(geom: dict | None) -> tuple[BaseGeometry | None, bool]:
    if not geom:
        return None, False
    try:
        g = shape(geom)
    except Exception:
        return None, False
    if g.is_empty:
        return None, False
    repaired = False
    if not g.is_valid:
        g = make_valid(g)
        repaired = True
    if g.is_empty:
        return None, repaired
    if g.geom_type == "GeometryCollection":
        polys = [part for part in g.geoms if part.geom_type in {"Polygon", "MultiPolygon"}]
        if not polys:
            return None, repaired
        g = unary_union(polys)
        repaired = True
    if g.geom_type not in {"Polygon", "MultiPolygon"}:
        return None, repaired
    return g, repaired


def geometry_to_geojson(g: BaseGeometry) -> dict:
    geom = json.loads(json.dumps(g.__geo_interface__))
    return compact_geometry(geom)


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


def sha256_file(path, chunk: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()

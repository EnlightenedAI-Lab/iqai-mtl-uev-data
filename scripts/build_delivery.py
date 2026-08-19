"""Build display + exact delivery fabrics from the accepted V1 cell package.

Does not re-download the official Ville de Montréal extract.
"""
from __future__ import annotations

import gzip
import json
import math
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

from shapely.geometry import mapping, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
DELIVERY = ROOT / "delivery"
SITE = ROOT / "_site"
ORIGIN_X = -74.1
ORIGIN_Y = 45.35
LAT0 = 45.5
M_PER_DEG_LAT = 111_320.0
M_PER_DEG_LON = 111_320.0 * math.cos(math.radians(LAT0))

LAYERS = {
    "overview": {
        "cell_deg": 0.04,
        "simplify_deg": 0.00018,
        "quantize": 4,
        "keep_area_m2": 2500.0,
        "min_span": 0.10,
    },
    "medium": {
        "cell_deg": 0.02,
        "simplify_deg": 0.00006,
        "quantize": 5,
        "keep_area_m2": 0.0,
        "min_span": 0.035,
    },
    "detail": {
        "cell_deg": 0.01,
        "simplify_deg": 0.00002,
        "quantize": 5,
        "keep_area_m2": 0.0,
        "min_span": 0.0,
    },
}


def log(msg: str) -> None:
    print(msg, flush=True)


def dump_json(path: Path, payload: Any) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    path.write_bytes(raw)
    return len(raw)


def dump_gzip_json(path: Path, payload: Any) -> tuple[int, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    gz = gzip.compress(raw, compresslevel=7)
    path.write_bytes(gz)
    return len(raw), len(gz)


def quantize(value: Any, decimals: int) -> Any:
    if isinstance(value, (int, float)):
        return round(float(value), decimals)
    if isinstance(value, list):
        return [quantize(item, decimals) for item in value]
    return value


def compact_geom(geom: dict | None, decimals: int) -> dict | None:
    if not geom:
        return None
    return {"type": geom.get("type"), "coordinates": quantize(geom.get("coordinates"), decimals)}


def geom_coords(geom: dict | None) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []

    def walk(value: Any) -> None:
        if not value:
            return
        if isinstance(value[0], (int, float)):
            out.append((float(value[0]), float(value[1])))
            return
        for item in value:
            walk(item)

    if geom:
        walk(geom.get("coordinates"))
    return out


def area_m2(geom) -> float:
    return abs(geom.area) * M_PER_DEG_LON * M_PER_DEG_LAT


def simplify_geom(geom_dict: dict, simplify_deg: float, decimals: int) -> dict | None:
    try:
        geom = shape(geom_dict)
        if geom.is_empty:
            return None
        if simplify_deg > 0:
            geom = geom.simplify(simplify_deg, preserve_topology=True)
        if geom.is_empty:
            return None
        if geom.geom_type not in {"Polygon", "MultiPolygon"}:
            geom = geom.buffer(0)
        if geom.is_empty or geom.geom_type not in {"Polygon", "MultiPolygon"}:
            return None
        return compact_geom(mapping(geom), decimals)
    except Exception:
        return compact_geom(geom_dict, decimals)


def display_cell_id(ix: int, iy: int, size: float) -> str:
    step = f"{size:.4f}".rstrip("0").rstrip(".")
    return f"d_{step}_{ix}_{iy}"


def display_cell_bbox(ix: int, iy: int, size: float) -> list[float]:
    minx = ORIGIN_X + ix * size
    miny = ORIGIN_Y + iy * size
    return [round(minx, 6), round(miny, 6), round(minx + size, 6), round(miny + size, 6)]


def assign_cell(lon: float, lat: float, size: float) -> tuple[int, int]:
    return math.floor((lon - ORIGIN_X) / size), math.floor((lat - ORIGIN_Y) / size)


def footprint_center(pts: list[tuple[float, float]], fallback: list[float]) -> tuple[float, float]:
    if not pts:
        return (fallback[0] + fallback[2]) / 2, (fallback[1] + fallback[3]) / 2
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def assemble_site() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "js").mkdir(parents=True)
    (SITE / "css").mkdir(parents=True)
    shutil.copytree(DELIVERY, SITE / "data")
    runtime = ROOT / "src" / "runtime"
    proof = ROOT / "src" / "proof"
    for src in runtime.glob("*.js"):
        shutil.copy2(src, SITE / "js" / src.name)
    for src in proof.glob("*.js"):
        shutil.copy2(src, SITE / "js" / src.name)
    for src in proof.glob("*.css"):
        shutil.copy2(src, SITE / "css" / src.name)
    for src in proof.glob("*.html"):
        shutil.copy2(src, SITE / src.name)
    (SITE / ".nojekyll").write_text("", encoding="utf-8")


def build() -> dict:
    src_manifest = json.loads((DIST / "manifest.json").read_text(encoding="utf-8"))
    provenance = json.loads((DIST / "provenance.json").read_text(encoding="utf-8"))
    cells_dir = DIST / "cells"
    if not cells_dir.exists():
        raise SystemExit("dist/cells missing; accepted V1 package is required")

    reset_dir(DELIVERY)
    display_buckets: dict[str, dict[str, list]] = {name: defaultdict(list) for name in LAYERS}
    exact_index: list[dict] = []
    id_shards: dict[str, dict[str, str]] = defaultdict(dict)
    exact_raw_bytes = 0
    exact_gz_bytes = 0
    source_cells = sorted(cells_dir.glob("*.json"))
    log(f"source cells {len(source_cells)}")

    for i, path in enumerate(source_cells, start=1):
        cell = json.loads(path.read_text(encoding="utf-8"))
        exact_features = []
        for feat in cell.get("features") or []:
            props = feat.get("properties") or {}
            geom = feat.get("geometry")
            units_in = props.get("units") or []
            compact_units = []
            ids = []
            for unit in units_in:
                sid = str(unit.get("source_id") or "")
                if not sid:
                    continue
                ids.append(sid)
                compact_units.append({"id": sid, "src": unit.get("source") or {}})
                id_shards[sid[-2:].zfill(2)][sid] = cell["cell"]
            if not ids or not geom:
                continue
            pts = geom_coords(geom)
            exact_features.append({"g": compact_geom(geom, 6), "ids": ids, "u": compact_units})
            cx, cy = footprint_center(pts, cell["bbox"])
            try:
                geom_obj = shape(geom)
                a_m2 = area_m2(geom_obj)
            except Exception:
                a_m2 = 0.0
            for layer_name, spec in LAYERS.items():
                display_geom = simplify_geom(geom, spec["simplify_deg"], spec["quantize"])
                if not display_geom:
                    continue
                ix, iy = assign_cell(cx, cy, spec["cell_deg"])
                key = display_cell_id(ix, iy, spec["cell_deg"])
                display_buckets[layer_name][key].append(
                    {
                        "i": ids[0],
                        "n": len(ids),
                        "c": cell["cell"],
                        "a": int(a_m2),
                        "g": display_geom,
                        "keep": a_m2 >= spec["keep_area_m2"],
                    }
                )

        raw, gz = dump_gzip_json(
            DELIVERY / "exact" / "cells" / f"{cell['cell']}.json.gz",
            {
                "cell": cell["cell"],
                "bbox": cell["bbox"],
                "unit_count": cell.get("unit_count"),
                "footprint_count": len(exact_features),
                "features": exact_features,
            },
        )
        exact_raw_bytes += raw
        exact_gz_bytes += gz
        exact_index.append(
            {
                "id": cell["cell"],
                "path": f"exact/cells/{cell['cell']}.json.gz",
                "bbox": cell["bbox"],
                "unit_count": cell.get("unit_count"),
                "footprint_count": cell.get("footprint_count"),
                "bytes_gz": gz,
            }
        )
        if i % 100 == 0:
            log(f"  exact {i}/{len(source_cells)}")

    layer_manifest = []
    display_stats = {}
    for layer_name, spec in LAYERS.items():
        cells_out = []
        bytes_total = 0
        feat_total = 0
        fill_total = 0
        layer_dir = DELIVERY / "display" / layer_name
        size = spec["cell_deg"]
        for key, recs in sorted(display_buckets[layer_name].items()):
            parts = key.split("_")
            ix, iy = int(parts[-2]), int(parts[-1])
            kept = []
            fill_geoms = []
            for rec in recs:
                if rec["keep"] or spec["keep_area_m2"] <= 0:
                    kept.append({"i": rec["i"], "n": rec["n"], "c": rec["c"], "g": rec["g"]})
                else:
                    try:
                        fill_geoms.append(shape(rec["g"]))
                    except Exception:
                        pass
            fill = None
            if fill_geoms:
                try:
                    merged = unary_union(fill_geoms)
                    if not merged.is_empty:
                        merged = merged.simplify(spec["simplify_deg"], preserve_topology=True)
                        fill = compact_geom(mapping(merged), spec["quantize"])
                        fill_total += 1
                except Exception:
                    fill = None
            payload = {
                "id": key,
                "layer": layer_name,
                "bbox": display_cell_bbox(ix, iy, size),
                "fill": fill,
                "features": kept,
            }
            raw_n, gz_n = dump_gzip_json(layer_dir / f"{key}.json.gz", payload)
            bytes_total += gz_n
            feat_total += len(kept) + (1 if fill else 0)
            cells_out.append(
                {
                    "id": key,
                    "path": f"display/{layer_name}/{key}.json.gz",
                    "bbox": payload["bbox"],
                    "feature_count": len(kept),
                    "has_fill": bool(fill),
                    "bytes": gz_n,
                    "bytes_raw": raw_n,
                }
            )
        layer_manifest.append(
            {
                "id": layer_name,
                "min_span": spec["min_span"],
                "cell_deg": spec["cell_deg"],
                "simplify_deg": spec["simplify_deg"],
                "keep_area_m2": spec["keep_area_m2"],
                "cells": cells_out,
            }
        )
        display_stats[layer_name] = {
            "cells": len(cells_out),
            "bytes": bytes_total,
            "features": feat_total,
            "fill_cells": fill_total,
        }
        log(f"display {layer_name} cells={len(cells_out)} bytes={bytes_total} features={feat_total}")

    id_bytes = 0
    for shard, mapping_ids in id_shards.items():
        id_bytes += dump_json(DELIVERY / "exact" / "ids" / f"{shard}.json", mapping_ids)

    manifest = {
        "package": "iqai.mtl.evaluation-units.v1.1",
        "object_class": "evaluation_unit",
        "identity_field": src_manifest.get("identity_field", "ID_UEV"),
        "provider": src_manifest.get("provider"),
        "dataset": src_manifest.get("dataset"),
        "dataset_id": src_manifest.get("dataset_id"),
        "catalog_url": src_manifest.get("catalog_url"),
        "license": src_manifest.get("license"),
        "crs": "EPSG:4326",
        "legal_note": src_manifest.get("legal_note"),
        "bbox": src_manifest.get("bbox"),
        "source_package": "iqai.mtl.evaluation-units.v1",
        "fabrics": {
            "display": {
                "note": "Simplified footprints for drawing. Not exact source geometry.",
                "layers": layer_manifest,
            },
            "exact": {
                "note": "Canonical ID_UEV, exact geometry, and original source attributes.",
                "id_index": {"dir": "exact/ids", "shard": "last2"},
                "cells": exact_index,
            },
        },
        "counts": src_manifest.get("counts"),
        "display_stats": display_stats,
        "exact_stats": {
            "cells": len(exact_index),
            "bytes_raw": exact_raw_bytes,
            "bytes_gz": exact_gz_bytes,
            "id_index_bytes": id_bytes,
        },
    }
    dump_json(DELIVERY / "manifest.json", manifest)
    dump_json(DELIVERY / "provenance.json", provenance)
    shutil.copy2(DIST / "ATTRIBUTION.md", DELIVERY / "ATTRIBUTION.md")
    if (DIST / "field-dictionary.json").exists():
        shutil.copy2(DIST / "field-dictionary.json", DELIVERY / "field-dictionary.json")
    assemble_site()
    summary = {
        "package": manifest["package"],
        "display": display_stats,
        "exact_gz_bytes": exact_gz_bytes,
        "exact_raw_bytes": exact_raw_bytes,
        "id_index_bytes": id_bytes,
        "identity_field": manifest["identity_field"],
    }
    dump_json(DELIVERY / "delivery-summary.json", summary)
    log(json.dumps(summary))
    return summary


if __name__ == "__main__":
    build()

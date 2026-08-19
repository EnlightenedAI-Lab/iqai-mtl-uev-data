from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .constants import PACKAGE_API_URL, USER_AGENT


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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

"""Geocodifica inversa con Nominatim (OpenStreetMap) e cache locale."""
import json
import time
import logging
import urllib.parse
import urllib.request

from poller.db import get_db

log = logging.getLogger("ex30.geocode")
USER_AGENT = "ex30-mate/1.0 (self-hosted personal use)"
_last_call = 0.0


def _label(data: dict):
    a = data.get("address") or {}
    road = (a.get("road") or a.get("pedestrian") or a.get("footway")
            or a.get("path") or a.get("cycleway"))
    city = (a.get("city") or a.get("town") or a.get("village")
            or a.get("municipality") or a.get("hamlet") or a.get("suburb"))
    if road and a.get("house_number"):
        road = f"{road} {a['house_number']}"
    parts = [p for p in (road, city) if p]
    if parts:
        return ", ".join(parts)
    name = data.get("display_name")
    return ", ".join(name.split(", ")[:2]) if name else None


def _fetch(lat: float, lon: float):
    global _last_call
    wait = 1.1 - (time.time() - _last_call)
    if wait > 0:
        time.sleep(wait)
    qs = urllib.parse.urlencode({
        "format": "jsonv2", "lat": f"{lat:.6f}", "lon": f"{lon:.6f}",
        "zoom": 18, "addressdetails": 1, "accept-language": "it",
    })
    req = urllib.request.Request(
        f"https://nominatim.openstreetmap.org/reverse?{qs}",
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
        _last_call = time.time()
        return _label(data)
    except Exception as e:
        _last_call = time.time()
        log.warning(f"Geocodifica fallita: {e}")
        return None


def reverse(lat, lon):
    if lat is None or lon is None:
        return None
    key = f"{float(lat):.4f},{float(lon):.4f}"
    conn = get_db()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS geocache (key TEXT PRIMARY KEY, label TEXT NOT NULL)")
        row = conn.execute("SELECT label FROM geocache WHERE key = ?", (key,)).fetchone()
        if row:
            return row[0]
    finally:
        conn.close()

    label = _fetch(float(lat), float(lon))
    if label:
        conn = get_db()
        try:
            conn.execute("INSERT OR REPLACE INTO geocache (key, label) VALUES (?, ?)", (key, label))
            conn.commit()
        finally:
            conn.close()
    return label

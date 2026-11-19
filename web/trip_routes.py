"""Percorso stradale di un viaggio (OSRM), con cache in trips.route_json."""
import json
import math
import urllib.request

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from poller.db import get_db

router = APIRouter()
MAX_WAYPOINTS = 25


def _dist_m(a, b) -> float:
    r = 6371000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _osrm(points):
    coords = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in points)
    url = f"https://router.project-osrm.org/route/v1/driving/{coords}?overview=full&geometries=geojson"
    req = urllib.request.Request(url, headers={"User-Agent": "ex30-mate/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data.get("code") != "Ok":
            return None
        return [[lat, lon] for lon, lat in data["routes"][0]["geometry"]["coordinates"]]
    except Exception:
        return None


@router.get("/api/trips/{trip_id}/route")
def trip_route(trip_id: int):
    conn = get_db()
    try:
        t = conn.execute("""SELECT route_json, start_lat, start_lon, end_lat, end_lon,
                                   CAST(strftime('%s', start_time) AS INTEGER) * 1000 AS t0,
                                   CAST(strftime('%s', end_time) AS INTEGER) * 1000 AS t1
                            FROM trips WHERE id = ?""", (trip_id,)).fetchone()
        if not t:
            return JSONResponse({"error": "not found"}, status_code=404)
        if t["route_json"]:
            return {"coords": json.loads(t["route_json"]), "source": "cache"}

        rows = conn.execute("""SELECT latitude, longitude FROM positions
                               WHERE timestamp_ms BETWEEN ? AND ?
                                 AND latitude IS NOT NULL AND longitude IS NOT NULL
                               ORDER BY timestamp_ms""",
                            (t["t0"] - 120000, t["t1"] + 300000)).fetchall()
        raw = []
        if t["start_lat"] is not None:
            raw.append((t["start_lat"], t["start_lon"]))
        raw += [(r[0], r[1]) for r in rows]
        if t["end_lat"] is not None:
            raw.append((t["end_lat"], t["end_lon"]))

        pts = []
        for p in raw:
            if not pts or _dist_m(pts[-1], p) >= 30:
                pts.append(p)
        if len(pts) > MAX_WAYPOINTS:
            step = (len(pts) - 1) / (MAX_WAYPOINTS - 1)
            pts = [pts[round(i * step)] for i in range(MAX_WAYPOINTS)]
        if len(pts) < 2:
            return {"coords": [[p[0], p[1]] for p in pts], "source": "raw"}

        route = _osrm(pts)
        if route:
            conn.execute("UPDATE trips SET route_json = ? WHERE id = ?", (json.dumps(route), trip_id))
            conn.commit()
            return {"coords": route, "source": "osrm"}
        return {"coords": [[p[0], p[1]] for p in pts], "source": "raw"}
    finally:
        conn.close()

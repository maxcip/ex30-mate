"""Uso: python -m poller.backfill addresses | merge ID1 ID2"""
import re
import sys
from datetime import datetime

from poller.db import get_db
from poller.sessions import _place, BATTERY_KWH

COORD = re.compile(r"^-?\d+\.\d+,\s*-?\d+\.\d+$")
FMT = "%Y-%m-%d %H:%M:%S"


def fix_addresses():
    conn = get_db()
    jobs = (("trips", (("start_address", "start_lat", "start_lon"), ("end_address", "end_lat", "end_lon"))),
            ("charges", (("address", "lat", "lon"),)))
    n = 0
    for table, cols in jobs:
        for r in conn.execute(f"SELECT * FROM {table}").fetchall():
            for a, la, lo in cols:
                val = (r[a] or "").strip()
                if r[la] is None or r[lo] is None:
                    continue
                if val in ("", "Casa") or COORD.match(val):
                    new = _place(r[la], r[lo])
                    conn.execute(f"UPDATE {table} SET {a} = ? WHERE id = ?", (new, r["id"]))
                    conn.commit()
                    n += 1
                    print(f"{table} {r['id']}: {new}")
    conn.close()
    print(f"Aggiornati {n} indirizzi")


def merge(a: int, b: int):
    conn = get_db()
    rows = sorted((conn.execute("SELECT * FROM trips WHERE id = ?", (i,)).fetchone() for i in (a, b)),
                  key=lambda r: r["start_time"])
    t1, t2 = rows
    dist = round((t2["end_odometer"] or 0) - (t1["start_odometer"] or 0), 1)
    used = max(0.0, (t1["start_soc"] or 0) - (t2["end_soc"] or 0))
    energy = round(used / 100.0 * BATTERY_KWH, 2)
    eff = round(energy * 1000.0 / dist, 1) if energy > 0 and dist > 0 else None
    minutes = max(1.0, (datetime.strptime(t2["end_time"], FMT) - datetime.strptime(t1["start_time"], FMT)).total_seconds() / 60)
    speed = round(dist / (minutes / 60.0), 1)
    conn.execute("""UPDATE trips SET end_time=?, end_soc=?, end_odometer=?, end_lat=?, end_lon=?, end_address=?,
                    distance_km=?, used_soc=?, energy_kwh=?, efficiency_wh_km=?, duration_min=?, avg_speed_kmh=?,
                    route_json=NULL WHERE id=?""",
                 (t2["end_time"], t2["end_soc"], t2["end_odometer"], t2["end_lat"], t2["end_lon"], t2["end_address"],
                  dist, round(used, 1), energy, eff, round(minutes, 1), speed, t1["id"]))
    conn.execute("DELETE FROM trips WHERE id = ?", (t2["id"],))
    conn.commit()
    conn.close()
    print(f"Uniti {t1['id']} e {t2['id']}: {dist} km, {round(minutes)} min")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "addresses":
        fix_addresses()
    elif len(sys.argv) == 4 and sys.argv[1] == "merge":
        merge(int(sys.argv[2]), int(sys.argv[3]))
    else:
        print(__doc__)

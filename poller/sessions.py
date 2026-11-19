"""Rileva ricariche e viaggi dalle letture del poller e li salva nel database."""
import os
import json
import math
import logging
from datetime import datetime, timezone

from poller.db import get_db
from poller import geocode

log = logging.getLogger("ex30.sessions")

BATTERY_KWH = float(os.environ.get("BATTERY_KWH", "64"))
HOME_PRICE = float(os.environ.get("HOME_PRICE_KWH", "0.47"))
PUBLIC_PRICE = float(os.environ.get("PUBLIC_PRICE_KWH", "0.65"))
HOME_LAT = os.environ.get("HOME_LAT", "").strip()
HOME_LON = os.environ.get("HOME_LON", "").strip()
HOME_RADIUS_M = float(os.environ.get("HOME_RADIUS_M", "200"))

DC_THRESHOLD_KW = 22.0
CHARGE_END_READINGS = 2
MIN_CHARGE_SOC = 1.0
MIN_CHARGE_MIN = 3.0
MIN_TRIP_KM = 1.0
MOVE_METERS = 60.0
TRIP_IDLE_SECONDS = 900
TRIP_MERGE_SECONDS = 1500
STATE_KEY = "tracker_state"


def _ts(sec: float) -> str:
    return datetime.fromtimestamp(sec, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _dist_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _is_home(lat, lon):
    if not HOME_LAT or not HOME_LON or lat is None or lon is None:
        return None
    try:
        return _dist_m(float(HOME_LAT), float(HOME_LON), float(lat), float(lon)) <= HOME_RADIUS_M
    except ValueError:
        return None


def _place(lat, lon) -> str:
    if lat is None or lon is None:
        return ""
    label = geocode.reverse(lat, lon) or f"{lat:.5f}, {lon:.5f}"
    return f"{label} (Casa)" if _is_home(lat, lon) else label


class SessionTracker:
    def __init__(self):
        self.state = self._load()

    def _load(self) -> dict:
        default = {"charge": None, "trip": None, "last": None, "last_closed": None}
        try:
            conn = get_db()
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (STATE_KEY,)).fetchone()
            conn.close()
            if row and row["value"]:
                default.update(json.loads(row["value"]))
        except Exception as e:
            log.warning(f"Stato tracker non leggibile: {e}")
        return default

    def _save(self):
        conn = get_db()
        try:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                         (STATE_KEY, json.dumps(self.state)))
            conn.commit()
        finally:
            conn.close()

    def update(self, status: dict):
        now = status["timestamp_ms"] / 1000.0
        self._charges(status, now)
        self._trips(status, now)
        self.state["last"] = {
            "odo": status.get("odometer_km"), "soc": status.get("soc"),
            "lat": status.get("latitude"), "lon": status.get("longitude"), "ts": now,
        }
        self._save()

    # ---------- Ricariche ----------

    def _charges(self, status: dict, now: float):
        st = self.state
        ch = st.get("charge")
        charging = bool(status.get("charging"))
        soc = status.get("soc")
        power = float(status.get("charge_power_kw") or 0.0)

        if charging:
            if ch is None:
                prev = st.get("last") or {}
                prev_soc = prev.get("soc")
                start_soc = min(soc, prev_soc) if prev_soc is not None and soc is not None else soc
                ch = {"start_ts": now, "start_soc": start_soc,
                      "lat": status.get("latitude"), "lon": status.get("longitude"),
                      "max_kw": power, "sum_kw": 0.0, "n_kw": 0,
                      "last_soc": soc, "last_ts": now, "idle": 0}
                st["last_closed"] = None
                log.info(f"Ricarica iniziata a {soc}%")
            ch["max_kw"] = max(ch["max_kw"], power)
            if power > 0:
                ch["sum_kw"] += power
                ch["n_kw"] += 1
            ch["last_soc"] = soc
            ch["last_ts"] = now
            ch["idle"] = 0
            st["charge"] = ch
        elif ch is not None:
            ch["idle"] += 1
            if soc is not None and soc > ch["last_soc"]:
                ch["last_soc"] = soc
            if ch["idle"] >= CHARGE_END_READINGS:
                self._close_charge(ch)
                st["charge"] = None

    def _close_charge(self, ch: dict):
        added = (ch["last_soc"] or 0) - (ch["start_soc"] or 0)
        minutes = (ch["last_ts"] - ch["start_ts"]) / 60.0
        if added < MIN_CHARGE_SOC or minutes < MIN_CHARGE_MIN:
            log.info(f"Ricarica scartata (+{added:.1f}%, {minutes:.1f} min)")
            return

        energy = round(added / 100.0 * BATTERY_KWH, 2)
        max_kw = round(ch["max_kw"], 2)
        avg_kw = round(ch["sum_kw"] / ch["n_kw"], 2) if ch["n_kw"] else 0.0
        ctype = "DC" if max_kw > DC_THRESHOLD_KW else "AC"
        home = _is_home(ch["lat"], ch["lon"])
        if home is None:
            home = ctype == "AC"
        price = HOME_PRICE if home else PUBLIC_PRICE
        cost = round(energy * price, 2)
        name = "Casa" if home else "Colonnina"
        address = _place(ch["lat"], ch["lon"])

        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO charges (vehicle_id, start_time, end_time, duration_min, start_soc, end_soc, added_soc,
                                     energy_kwh, gross_kwh, charge_type, max_power_kw, avg_power_kw,
                                     location_name, address, lat, lon, cost, cost_per_kwh, is_home, note)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (_ts(ch["start_ts"]), _ts(ch["last_ts"]), round(minutes, 1),
                  round(ch["start_soc"], 1), round(ch["last_soc"], 1), round(added, 1),
                  energy, ctype, max_kw, avg_kw, name, address, ch["lat"], ch["lon"],
                  cost, price, 1 if home else 0, "Rilevata automaticamente"))
            conn.commit()
        finally:
            conn.close()
        log.info(f"Ricarica salvata: +{added:.1f}%, {energy} kWh, {cost} EUR, {ctype}")

    # ---------- Viaggi ----------

    @staticmethod
    def _moved(status: dict, prev) -> bool:
        if not prev:
            return False
        odo, p_odo = status.get("odometer_km"), prev.get("odo")
        if odo and p_odo and odo - p_odo >= 1:
            return True
        lat, lon = status.get("latitude"), status.get("longitude")
        plat, plon = prev.get("lat"), prev.get("lon")
        if None not in (lat, lon, plat, plon):
            return _dist_m(plat, plon, lat, lon) >= MOVE_METERS
        return False

    def _trips(self, status: dict, now: float):
        st = self.state
        trip = st.get("trip")
        prev = st.get("last")
        odo = status.get("odometer_km")
        if not odo:
            return
        moved = self._moved(status, prev) and not status.get("charging")

        if trip is None:
            if not moved:
                return
            lc = st.get("last_closed")
            if lc and now - lc["trip"]["end_ts"] <= TRIP_MERGE_SECONDS:
                trip = lc["trip"]
                self._delete_trip(lc["id"])
                trip["idle_since"] = None
                log.info("Viaggio ripreso: unito al precedente")
            else:
                trip = {"start_ts": prev["ts"], "start_odo": prev["odo"], "start_soc": prev["soc"],
                        "start_lat": prev["lat"], "start_lon": prev["lon"],
                        "end_ts": now, "end_odo": odo, "end_soc": status.get("soc"),
                        "end_lat": status.get("latitude"), "end_lon": status.get("longitude"),
                        "idle_since": None}
                log.info(f"Viaggio iniziato, odometro {odo} km")
            st["last_closed"] = None
            st["trip"] = trip

        if status.get("soc") is not None:
            trip["end_soc"] = status["soc"]
        if status.get("latitude") is not None and status.get("longitude") is not None:
            trip["end_lat"] = status["latitude"]
            trip["end_lon"] = status["longitude"]

        if moved:
            trip["end_odo"] = max(trip["end_odo"], odo)
            trip["end_ts"] = now
            trip["idle_since"] = None
        else:
            if trip["idle_since"] is None:
                trip["idle_since"] = now
            if now - trip["idle_since"] >= TRIP_IDLE_SECONDS:
                row_id = self._close_trip(trip)
                st["trip"] = None
                st["last_closed"] = {"id": row_id, "trip": trip} if row_id else None

    def _delete_trip(self, trip_id: int):
        conn = get_db()
        try:
            conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
            conn.commit()
        finally:
            conn.close()

    def _close_trip(self, trip: dict):
        dist = round(trip["end_odo"] - trip["start_odo"], 1)
        if dist < MIN_TRIP_KM:
            return None
        start_soc = trip["start_soc"] if trip["start_soc"] is not None else 0.0
        end_soc = trip["end_soc"] if trip["end_soc"] is not None else start_soc
        used = max(0.0, start_soc - end_soc)
        energy = round(used / 100.0 * BATTERY_KWH, 2)
        eff = round(energy * 1000.0 / dist, 1) if energy > 0 else None
        minutes = max(1.0, (trip["end_ts"] - trip["start_ts"]) / 60.0)
        avg_speed = round(dist / (minutes / 60.0), 1)
        start_addr = _place(trip["start_lat"], trip["start_lon"])
        end_addr = _place(trip["end_lat"], trip["end_lon"])

        conn = get_db()
        try:
            cur = conn.execute("""
                INSERT INTO trips (vehicle_id, start_time, end_time, duration_min, distance_km, start_soc, end_soc, used_soc,
                                   start_odometer, end_odometer, avg_speed_kmh, max_speed_kmh, energy_kwh, efficiency_wh_km,
                                   start_address, end_address, start_lat, start_lon, end_lat, end_lon, note)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (_ts(trip["start_ts"]), _ts(trip["end_ts"]), round(minutes, 1), dist,
                  round(start_soc, 1), round(end_soc, 1), round(used, 1),
                  trip["start_odo"], trip["end_odo"], avg_speed, energy, eff,
                  start_addr, end_addr,
                  trip["start_lat"], trip["start_lon"], trip["end_lat"], trip["end_lon"],
                  "Rilevato automaticamente"))
            conn.commit()
            row_id = cur.lastrowid
        finally:
            conn.close()
        log.info(f"Viaggio salvato: {dist} km, {round(minutes)} min, {start_addr} -> {end_addr}")
        return row_id

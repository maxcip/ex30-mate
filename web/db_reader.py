"""Database reader and statistics engine for Volvo EX30 Mate web UI."""
import sqlite3
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

from poller.db import DB_PATH, get_db

CURRENCIES = {
    "EUR": {"symbol": "€", "pos": "after", "dec": 2},
    "USD": {"symbol": "$", "pos": "before", "dec": 2},
    "GBP": {"symbol": "£", "pos": "before", "dec": 2},
    "SEK": {"symbol": "kr", "pos": "after", "dec": 2},
    "NOK": {"symbol": "kr", "pos": "after", "dec": 2},
}

def get_setting(key: str, default: str = "") -> str:
    try:
        conn = get_db()
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        conn.close()
        return row["value"] if row else default
    except Exception:
        return default

def set_setting(key: str, value: str):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_currency() -> dict:
    code = get_setting("currency", "EUR")
    return CURRENCIES.get(code, CURRENCIES["EUR"])

def get_language() -> str:
    return get_setting("language", "it")

def get_vehicles() -> list[dict]:
    try:
        conn = get_db()
        rows = conn.execute("SELECT * FROM vehicles").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []

def get_vehicle() -> tuple[dict | None, list[dict]]:
    vehicles = get_vehicles()
    if not vehicles:
        return None, []
    vin = get_setting("selected_vin", "")
    selected = next((v for v in vehicles if v["vin"] == vin), vehicles[0])
    return selected, vehicles

def get_latest_status(vehicle_id: int = 1) -> dict | None:
    try:
        conn = get_db()
        row = conn.execute("""
            SELECT * FROM positions WHERE vehicle_id = ?
            ORDER BY timestamp_ms DESC LIMIT 1
        """, (vehicle_id,)).fetchone()
        conn.close()
        if not row:
            return None
        d = dict(row)
        # Compute age in seconds
        now_ms = int(time.time() * 1000)
        ts = d.get("timestamp_ms") or now_ms
        d["data_age_s"] = max(0, (now_ms - ts) // 1000)
        d["data_age"] = d["data_age_s"] > 120
        d["ready"] = d.get("gear") in ("D", "R", "N") or d.get("speed_kmh", 0) > 0
        d["charge_completed"] = d.get("soc", 0) >= 95 and not d.get("charging")
        d["ready"] = d.get("gear") in ("D", "R") or d.get("speed_kmh", 0) > 0
        return d
    except Exception:
        return None

def get_recent_trips(vehicle_id: int = 1, limit: int = 5) -> list[dict]:
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT * FROM trips WHERE vehicle_id = ?
            ORDER BY start_time DESC LIMIT ?
        """, (vehicle_id, limit)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []

def get_last_charge(vehicle_id: int = 1) -> dict | None:
    try:
        conn = get_db()
        row = conn.execute("""
            SELECT * FROM charges WHERE vehicle_id = ?
            ORDER BY end_time DESC LIMIT 1
        """, (vehicle_id,)).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None

def charge_energy_view(charge: dict) -> dict:
    kwh = charge.get("energy_kwh") or 0.0
    gross = charge.get("gross_kwh") or (kwh * 1.08)
    return {
        "headline_kwh": kwh,
        "headline": "battery",
        "battery_kwh": kwh,
        "gross_kwh": gross,
        "gross_lost_kwh": max(0, gross - kwh),
        "gross_eff": (kwh / gross * 100) if gross > 0 else 90,
        "wallbox_eff": None
    }

def range_at_charge_target(range_km: float, soc: float, target_pct: float = 100.0) -> dict:
    if not soc or soc <= 0 or not range_km:
        return {"km": range_km or 0, "pct": target_pct}
    max_range = range_km / (soc / 100.0)
    target_range = max_range * (target_pct / 100.0)
    return {"km": target_range, "pct": target_pct}

def never_reported_temps() -> list:
    return []

def home_prices_by_solar() -> bool:
    return False

def _billed_kwh(charge: dict) -> float:
    return charge.get("energy_kwh") or 0.0

def billed_basis(charge: dict) -> str:
    return "kWh"

def display_tz_name() -> str:
    return "UTC"

def _local_dt(s: str | None):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

def get_all_vehicles() -> list[dict]:
    return get_vehicles()

def get_all_trips(vehicle_id: int = 1) -> list[dict]:
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT * FROM trips WHERE vehicle_id = ? ORDER BY start_time DESC
        """, (vehicle_id,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []

def get_all_charges(vehicle_id: int = 1) -> list[dict]:
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT * FROM charges WHERE vehicle_id = ? ORDER BY start_time DESC
        """, (vehicle_id,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []

def get_events(vehicle_id: int = 1, limit: int = 50) -> list[dict]:
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT * FROM events WHERE vehicle_id = ? ORDER BY timestamp DESC LIMIT ?
        """, (vehicle_id, limit)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []

def get_battery_history(vehicle_id: int = 1, hours: int = 24) -> list[dict]:
    try:
        conn = get_db()
        cutoff = int((time.time() - hours * 3600) * 1000)
        rows = conn.execute("""
            SELECT soc, range_km, charge_power_kw, timestamp_ms, recorded_at
            FROM positions WHERE vehicle_id = ? AND timestamp_ms >= ?
            ORDER BY timestamp_ms ASC
        """, (vehicle_id, cutoff)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []

def get_charge_stats(vehicle_id: int = 1) -> dict:
    try:
        conn = get_db()
        row = conn.execute("""
            SELECT COUNT(*) AS n,
                   SUM(energy_kwh) AS energy,
                   SUM(cost) AS cost,
                   AVG(avg_power_kw) AS avg_power,
                   MAX(max_power_kw) AS max_power
            FROM charges WHERE vehicle_id = ?
        """, (vehicle_id,)).fetchone()
        conn.close()
        d = dict(row) if row else {}
        return {
            "n": d.get("n") or 0,
            "energy": d.get("energy") or 0.0,
            "cost": d.get("cost") or 0.0,
            "avg_power": d.get("avg_power") or 0.0,
            "max_power": d.get("max_power") or 0.0,
        }
    except Exception:
        return {"n": 0, "energy": 0.0, "cost": 0.0, "avg_power": 0.0, "max_power": 0.0}

def get_maintenance(vehicle_id: int = 1) -> list[dict]:
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT * FROM maintenance WHERE vehicle_id = ? ORDER BY due_km ASC
        """, (vehicle_id,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []

def get_schedules(vehicle_id: int = 1) -> list[dict]:
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT * FROM schedules WHERE vehicle_id = ? ORDER BY id ASC
        """, (vehicle_id,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []

def get_vehicle_detail(vehicle_id: int = 1) -> dict | None:
    try:
        conn = get_db()
        row = conn.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None

def get_statistics_summary(vehicle_id: int = 1) -> dict:
    try:
        conn = get_db()
        trip_stats = conn.execute("""
            SELECT SUM(distance_km) as total_dist,
                   SUM(energy_kwh) as total_energy,
                   COUNT(*) as total_trips,
                   AVG(efficiency_wh_km) as avg_eff
            FROM trips WHERE vehicle_id = ?
        """, (vehicle_id,)).fetchone()

        charge_stats = conn.execute("""
            SELECT SUM(energy_kwh) as total_charged,
                   SUM(cost) as total_cost,
                   COUNT(*) as total_charges
            FROM charges WHERE vehicle_id = ?
        """, (vehicle_id,)).fetchone()
        conn.close()

        return {
            "total_dist": trip_stats["total_dist"] or 0,
            "total_energy": trip_stats["total_energy"] or 0,
            "total_trips": trip_stats["total_trips"] or 0,
            "avg_eff": trip_stats["avg_eff"] or 165,
            "total_charged": charge_stats["total_charged"] or 0,
            "total_cost": charge_stats["total_cost"] or 0,
            "total_charges": charge_stats["total_charges"] or 0,
        }
    except Exception:
        return {
            "total_dist": 0, "total_energy": 0, "total_trips": 0, "avg_eff": 165,
            "total_charged": 0, "total_cost": 0, "total_charges": 0
        }

"""Database schema and write operations for Volvo EX30 Mate."""
import os
import sqlite3
import time
import logging
from pathlib import Path

log = logging.getLogger("ex30.db")

def get_data_dir() -> Path:
    env_dir = os.environ.get("DATA_DIR")
    if env_dir:
        data_dir = Path(env_dir)
    else:
        data_dir = Path("/data")
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        data_dir = Path(__file__).resolve().parent.parent / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir

DB_PATH = get_data_dir() / "volvo_mate.db"

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Settings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")

    # Vehicles
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vehicles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vin TEXT UNIQUE,
        car_type TEXT DEFAULT 'Volvo EX30',
        model_variant TEXT DEFAULT 'Single Motor Extended Range',
        battery_capacity_kwh REAL DEFAULT 64.0,
        color TEXT DEFAULT 'Vapour Grey',
        year INTEGER DEFAULT 2024,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # Positions (Live Telemetry stream)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id INTEGER,
        timestamp_ms INTEGER,
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        soc REAL,
        range_km REAL,
        odometer_km REAL,
        speed_kmh REAL,
        gear TEXT,
        vehicle_state TEXT,
        charging_status INTEGER,
        cable_connected INTEGER,
        charging INTEGER,
        charge_power_kw REAL,
        remaining_charge_min INTEGER,
        latitude REAL,
        longitude REAL,
        outside_temp REAL,
        inside_temp REAL,
        climate_target_temp REAL,
        battery_temp REAL,
        is_locked INTEGER,
        climate_on INTEGER,
        trunk_open INTEGER,
        doors_open INTEGER,
        windows_open INTEGER,
        tire_pressure_fl REAL,
        tire_pressure_fr REAL,
        tire_pressure_rl REAL,
        tire_pressure_rr REAL,
        FOREIGN KEY(vehicle_id) REFERENCES vehicles(id)
    )""")

    # Index for fast telemetry query
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pos_ts ON positions(timestamp_ms)")

    # Trips
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trips (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id INTEGER,
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        duration_min REAL,
        distance_km REAL,
        start_soc REAL,
        end_soc REAL,
        used_soc REAL,
        start_odometer REAL,
        end_odometer REAL,
        avg_speed_kmh REAL,
        max_speed_kmh REAL,
        energy_kwh REAL,
        efficiency_wh_km REAL,
        start_address TEXT,
        end_address TEXT,
        start_lat REAL,
        start_lon REAL,
        end_lat REAL,
        end_lon REAL,
        note TEXT,
        drive_mode TEXT DEFAULT 'Comfort',
        cost REAL,
        route_json TEXT,
        FOREIGN KEY(vehicle_id) REFERENCES vehicles(id)
    )""")

    # Charges
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS charges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id INTEGER,
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        duration_min REAL,
        start_soc REAL,
        end_soc REAL,
        added_soc REAL,
        energy_kwh REAL,
        gross_kwh REAL,
        charge_type TEXT DEFAULT 'AC',
        max_power_kw REAL,
        avg_power_kw REAL,
        location_name TEXT,
        address TEXT,
        lat REAL,
        lon REAL,
        cost REAL,
        cost_per_kwh REAL,
        is_home INTEGER DEFAULT 0,
        confirmed INTEGER DEFAULT 1,
        note TEXT,
        power_curve_json TEXT,
        FOREIGN KEY(vehicle_id) REFERENCES vehicles(id)
    )""")

    # Events Log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id INTEGER,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        event_type TEXT,
        title TEXT,
        description TEXT,
        lat REAL,
        lon REAL,
        FOREIGN KEY(vehicle_id) REFERENCES vehicles(id)
    )""")

    # Default settings & vehicle initialization
    cursor.execute("SELECT COUNT(*) FROM vehicles")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO vehicles (vin, car_type, model_variant, battery_capacity_kwh, color, year)
        VALUES ('YV1EX30E8RB019842', 'Volvo EX30', 'Single Motor Extended Range', 64.0, 'Vapour Grey', 2024)
        """)

    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('language', 'it')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('currency', 'EUR')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('unit_system', 'metric')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('home_price_kwh', '0.25')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('public_price_kwh', '0.65')")

    conn.commit()
    conn.close()
    log.info("Database schema initialized successfully.")

if __name__ == "__main__":
    init_db()

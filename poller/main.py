"""Background Poller for Volvo EX30."""
import time
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from poller.db import get_db, init_db
from poller.volvo_api import VolvoApiClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("ex30.poller")

def seed_demo_data(conn):
    """Seed initial sample trips and charges if database is empty."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM trips")
    if cursor.fetchone()[0] > 0:
        return

    log.info("Seeding initial Volvo EX30 demo trips and charges...")
    now = time.time()

    # Seed trips
    for i in range(10):
        t_start = now - (i * 86400) - 3600
        t_end = t_start + 1800
        dist = round(random.uniform(15.0, 65.0), 1)
        energy = round(dist * 0.165, 2)
        cursor.execute("""
            INSERT INTO trips (vehicle_id, start_time, end_time, duration_min, distance_km, start_soc, end_soc, used_soc,
                               start_odometer, end_odometer, avg_speed_kmh, max_speed_kmh, energy_kwh, efficiency_wh_km,
                               start_address, end_address, start_lat, start_lon, end_lat, end_lon, note)
            VALUES (1, datetime(?, 'unixepoch'), datetime(?, 'unixepoch'), 30.0, ?, 85.0, 75.0, 10.0,
                    14000.0, 14000.0 + ?, 55.0, 110.0, ?, 165.0,
                    'Milano Centro', 'Bergamo Stazione', 45.4642, 9.1900, 45.6983, 9.6773, 'Commute test')
        """, (t_start, t_end, dist, dist, energy))

    # Seed charges
    for i in range(5):
        t_start = now - (i * 172800) - 7200
        t_end = t_start + 5400
        kwh = round(random.uniform(25.0, 52.0), 1)
        cost = round(kwh * 0.35, 2)
        cursor.execute("""
            INSERT INTO charges (vehicle_id, start_time, end_time, duration_min, start_soc, end_soc, added_soc,
                                 energy_kwh, gross_kwh, charge_type, max_power_kw, avg_power_kw, location_name, address, lat, lon, cost, is_home)
            VALUES (1, datetime(?, 'unixepoch'), datetime(?, 'unixepoch'), 90.0, 30.0, 90.0, 60.0,
                    ?, ?, 'AC', 11.0, 11.0, 'Home Wallbox', 'Via Roma 1, Milano', 45.4642, 9.1900, ?, 1)
        """, (t_start, t_end, kwh, kwh * 1.08, cost))

    conn.commit()
    log.info("Demo data seeded successfully.")

import random

def main_loop():
    init_db()
    conn = get_db()
    seed_demo_data(conn)
    conn.close()

    client = VolvoApiClient()
    log.info("Volvo EX30 Poller started.")

    while True:
        try:
            status = client.get_status()
            if status:
                conn = get_db()
                conn.execute("""
                    INSERT INTO positions (
                        vehicle_id, timestamp_ms, soc, range_km, odometer_km, speed_kmh, gear,
                        vehicle_state, charging_status, cable_connected, charging, charge_power_kw,
                        latitude, longitude, outside_temp, inside_temp, climate_target_temp,
                        battery_temp, is_locked, climate_on, trunk_open, doors_open, windows_open,
                        tire_pressure_fl, tire_pressure_fr, tire_pressure_rl, tire_pressure_rr
                    ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    status["timestamp_ms"], status["soc"], status["range_km"], status["odometer_km"],
                    status["speed_kmh"], status["gear"], status["vehicle_state"], status["charging_status"],
                    status["cable_connected"], status["charging"], status["charge_power_kw"],
                    status["latitude"], status["longitude"], status["outside_temp"], status["inside_temp"],
                    status["climate_target_temp"], status["battery_temp"], status["is_locked"],
                    status["climate_on"], status["trunk_open"], status["doors_open"], status["windows_open"],
                    status["tire_pressure_fl"], status["tire_pressure_fr"], status["tire_pressure_rl"], status["tire_pressure_rr"]
                ))
                conn.commit()
                conn.close()
        except Exception as e:
            log.error(f"Poller error: {e}")

        time.sleep(30)

if __name__ == "__main__":
    main_loop()

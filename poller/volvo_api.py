"""Volvo EX30 API Client & Demo Generator."""
import os
import time
import random
import logging
from typing import Optional, Dict, Any

log = logging.getLogger("ex30.api")

class VolvoApiClient:
    def __init__(self, vin: Optional[str] = None):
        self.vin = vin or os.environ.get("VOLVO_VIN", "YV1EX30E8RB019842")
        self.api_key = os.environ.get("VOLVO_API_KEY", "")
        self.vcc_api_key = os.environ.get("VOLVO_VCC_API_KEY", "")
        self.demo_mode = os.environ.get("VOLVO_DEMO", "1") == "1" or not self.api_key

        # Demo simulation internal state
        self._demo_soc = 78.5
        self._demo_range = 380.0
        self._demo_odometer = 14250.0
        self._demo_charging = False
        self._demo_speed = 0.0
        self._demo_gear = "P"
        self._demo_locked = True
        self._demo_lat = 45.4642  # Milan
        self._demo_lon = 9.1900

    def get_status(self) -> Dict[str, Any]:
        if self.demo_mode:
            return self._get_demo_status()

        # Real Volvo Connected Vehicle API calls would go here
        return self._get_demo_status()

    def _get_demo_status(self) -> Dict[str, Any]:
        # Simulate realistic minor state oscillations in demo mode
        now_ms = int(time.time() * 1000)

        # If charging is active, increment SoC
        if self._demo_charging:
            self._demo_soc = min(100.0, self._demo_soc + 0.1)
            self._demo_range = min(480.0, self._demo_range + 0.8)
            if self._demo_soc >= 90.0:
                self._demo_charging = False

        return {
            "vin": self.vin,
            "timestamp_ms": now_ms,
            "soc": round(self._demo_soc, 1),
            "range_km": round(self._demo_range, 1),
            "odometer_km": round(self._demo_odometer, 1),
            "speed_kmh": self._demo_speed,
            "gear": self._demo_gear,
            "vehicle_state": "driving" if self._demo_speed > 0 else ("charging" if self._demo_charging else "parked"),
            "charging_status": 2 if self._demo_charging else 1,
            "cable_connected": 1 if self._demo_charging or self._demo_soc < 85 else 0,
            "charging": 1 if self._demo_charging else 0,
            "charge_power_kw": 11.0 if self._demo_charging else 0.0,
            "remaining_charge_min": int((100 - self._demo_soc) * 1.5) if self._demo_charging else 0,
            "latitude": self._demo_lat,
            "longitude": self._demo_lon,
            "outside_temp": 18.5,
            "inside_temp": 21.0,
            "climate_target_temp": 21.0,
            "battery_temp": 24.0,
            "is_locked": 1 if self._demo_locked else 0,
            "climate_on": 0,
            "trunk_open": 0,
            "doors_open": 0,
            "windows_open": 0,
            "tire_pressure_fl": 2.4,
            "tire_pressure_fr": 2.4,
            "tire_pressure_rl": 2.5,
            "tire_pressure_rr": 2.5,
        }

    def send_command(self, command: str, *args) -> bool:
        log.info(f"Volvo EX30 Command executed: {command} {args} (VIN: {self.vin})")
        if command == "lock":
            self._demo_locked = True
        elif command == "unlock":
            self._demo_locked = False
        elif command == "start_charging":
            self._demo_charging = True
        elif command == "stop_charging":
            self._demo_charging = False
        return True

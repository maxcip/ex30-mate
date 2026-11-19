"""Volvo EX30 client: legge e comanda l'auto tramite Home Assistant (o demo)."""
import os
import sys
import json
import time
import logging
from typing import Optional, Dict, Any

import requests

log = logging.getLogger("ex30.api")

HTTP_TIMEOUT = 15
BAD = (None, "", "unknown", "unavailable", "none")


class VolvoApiClient:
    def __init__(self, vin: Optional[str] = None):
        self.vin = vin or os.environ.get("VOLVO_VIN", "")
        self.demo_mode = os.environ.get("VOLVO_DEMO", "1") == "1"
        self.ha_url = os.environ.get("HA_URL", "").rstrip("/")
        self.ha_token = os.environ.get("HA_TOKEN", "")
        self.p = os.environ.get("HA_PREFIX", "volvo_ex30")
        self.soc_entity = os.environ.get("HA_SOC_ENTITY", f"sensor.{self.p}_battery")

        self._demo_soc = 78.5
        self._demo_range = 380.0
        self._demo_odometer = 14250.0
        self._demo_charging = False
        self._demo_speed = 0.0
        self._demo_gear = "P"
        self._demo_locked = True
        self._demo_lat = 45.4642
        self._demo_lon = 9.1900

    # ---------- Home Assistant ----------

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.ha_token}",
            "Content-Type": "application/json",
        }

    def _states(self) -> Optional[dict]:
        if not self.ha_url or not self.ha_token:
            log.error("HA_URL o HA_TOKEN mancanti.")
            return None
        try:
            r = requests.get(f"{self.ha_url}/api/states", headers=self._headers(), timeout=HTTP_TIMEOUT)
        except requests.RequestException as e:
            log.error(f"Home Assistant non raggiungibile: {e}")
            return None
        if r.status_code != 200:
            log.error(f"GET /api/states -> {r.status_code} {r.text[:200]}")
            return None
        return {s["entity_id"]: s for s in r.json()}

    @staticmethod
    def _s(states: dict, entity_id: str) -> Optional[str]:
        obj = states.get(entity_id)
        if not obj:
            return None
        val = obj.get("state")
        return None if val in BAD else val

    def _f(self, states: dict, entity_id: str) -> Optional[float]:
        val = self._s(states, entity_id)
        try:
            return float(val) if val is not None else None
        except ValueError:
            return None

    def _any_on(self, states: dict, entity_ids: list) -> int:
        return 1 if any(self._s(states, e) == "on" for e in entity_ids) else 0

    # ---------- Stato ----------

    def get_status(self) -> Optional[Dict[str, Any]]:
        if self.demo_mode:
            return self._get_demo_status()

        st = self._states()
        if st is None:
            return None

        p = self.p
        soc = self._f(st, self.soc_entity)
        if soc is None:
            log.warning(f"{self.soc_entity} non disponibile, lettura saltata.")
            return None

        charging_state = self._s(st, f"sensor.{p}_charging_state") or "not_charging"
        connection = self._s(st, f"sensor.{p}_charging_connection_status") or "disconnected"
        is_charging = charging_state.startswith("charging")
        power_w = self._f(st, f"sensor.{p}_charging_power") or 0.0
        remaining = self._f(st, f"sensor.{p}_estimated_charging_time") or 0.0

        loc = st.get(f"device_tracker.{p}_location", {}).get("attributes", {})
        lat = loc.get("latitude")
        lon = loc.get("longitude")

        doors = [f"binary_sensor.{p}_door_{x}" for x in ("front_left", "front_right", "rear_left", "rear_right")]
        doors.append(f"binary_sensor.{p}_hood")
        windows = [f"binary_sensor.{p}_window_{x}" for x in ("front_left", "front_right", "rear_left", "rear_right")]
        windows.append(f"binary_sensor.{p}_sunroof")

        return {
            "vin": self.vin,
            "timestamp_ms": int(time.time() * 1000),
            "soc": round(soc, 1),
            "range_km": round(self._f(st, f"sensor.{p}_distance_to_empty_battery") or 0.0, 1),
            "odometer_km": round(self._f(st, f"sensor.{p}_odometer") or 0.0, 1),
            "speed_kmh": 0.0,
            "gear": "P",
            "vehicle_state": "charging" if is_charging else "parked",
            "charging_status": 2 if is_charging else 1,
            "cable_connected": 1 if (connection == "connected" or charging_state != "not_charging") else 0,
            "charging": 1 if is_charging else 0,
            "charge_power_kw": round(power_w / 1000.0, 2),
            "remaining_charge_min": int(remaining) if is_charging else 0,
            "latitude": lat,
            "longitude": lon,
            "outside_temp": None,
            "inside_temp": None,
            "climate_target_temp": None,
            "battery_temp": None,
            "is_locked": 1 if self._s(st, f"lock.{p}_lock") == "locked" else 0,
            "climate_on": 1 if self._s(st, f"switch.{p}_preclimatizzazione") == "on" else 0,
            "trunk_open": 1 if self._s(st, f"binary_sensor.{p}_tailgate") == "on" else 0,
            "doors_open": self._any_on(st, doors),
            "windows_open": self._any_on(st, windows),
            "tire_pressure_fl": None,
            "tire_pressure_fr": None,
            "tire_pressure_rl": None,
            "tire_pressure_rr": None,
        }

    # ---------- Comandi ----------

    def _call_service(self, domain: str, service: str, entity_id: str) -> bool:
        try:
            r = requests.post(
                f"{self.ha_url}/api/services/{domain}/{service}",
                headers=self._headers(),
                json={"entity_id": entity_id},
                timeout=HTTP_TIMEOUT,
            )
        except requests.RequestException as e:
            log.error(f"Servizio {domain}.{service} fallito: {e}")
            return False
        if r.status_code != 200:
            log.error(f"{domain}.{service} -> {r.status_code} {r.text[:200]}")
            return False
        return True

    def send_command(self, command: str, *args) -> bool:
        log.info(f"Comando: {command} {args}")
        if self.demo_mode:
            return self._demo_command(command)

        p = self.p
        mapping = {
            "lock": ("lock", "lock", f"lock.{p}_lock"),
            "unlock": ("lock", "unlock", f"lock.{p}_lock"),
            "honk": ("button", "press", f"button.{p}_honk"),
            "flash": ("button", "press", f"button.{p}_flash"),
            "honk_flash": ("button", "press", f"button.{p}_honk_flash"),
            "precondition": ("button", "press", f"button.{p}_start_climatization"),
            "stop_precondition": ("button", "press", f"button.{p}_stop_climatization"),
        }
        target = mapping.get(command)
        if not target:
            log.warning(f"Comando non supportato: {command}")
            return False
        return self._call_service(*target)

    # ---------- Demo ----------

    def _demo_command(self, command: str) -> bool:
        if command == "lock":
            self._demo_locked = True
        elif command == "unlock":
            self._demo_locked = False
        elif command == "start_charging":
            self._demo_charging = True
        elif command == "stop_charging":
            self._demo_charging = False
        return True

    def _get_demo_status(self) -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        if self._demo_charging:
            self._demo_soc = min(100.0, self._demo_soc + 0.1)
            self._demo_range = min(480.0, self._demo_range + 0.8)
            if self._demo_soc >= 90.0:
                self._demo_charging = False
        return {
            "vin": self.vin or "YV1EX30E8RB019842",
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        print(json.dumps(VolvoApiClient().get_status(), indent=2))
    else:
        print("Uso: python -m poller.volvo_api status")

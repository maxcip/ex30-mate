"""Units formatting for Volvo EX30 Mate."""

def decimal_point(s: str) -> str:
    return s.replace(".", ",")

def dist(val, decimals: int = 1) -> str:
    if val is None:
        return "—"
    return f"{float(val):.{decimals}f} km"

def dist_val(val) -> float:
    if val is None or val == "":
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0

def dist_unit() -> str:
    return "km"

def speed_unit() -> str:
    return "km/h"

def speed_val(val) -> float:
    if val is None:
        return 0.0
    return float(val)

def temp(val, decimals: int = 0) -> str:
    if val is None:
        return "—"
    return f"{float(val):.{decimals}f} °C"

def temp_val(val) -> float:
    if val is None:
        return 0.0
    return float(val)

def temp_unit() -> str:
    return "°C"

def pressure(val) -> str:
    if val is None:
        return "—"
    return f"{float(val):.1f} bar"

def pressure_unit() -> str:
    return "bar"

def eff_unit() -> str:
    return "Wh/km"

def elev_unit() -> str:
    return "m"

def get_unit_system() -> str:
    return "metric"

def dist100_unit() -> str:
    return "kWh/100km"

def cost100_val(energy, dist) -> float:
    if not dist or dist <= 0:
        return 0.0
    return (energy / dist) * 100

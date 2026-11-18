"""Volvo EX30 Mate — Web application."""
import time
from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web import db_reader
from web import i18n
from web import units
from poller.volvo_api import VolvoApiClient

app = FastAPI(title="Volvo EX30 Mate")
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Jinja template filters & globals
def _t(key: str) -> str:
    lang = db_reader.get_language()
    return i18n.t(key, lang)

def _nice(x) -> str:
    if x is None:
        return "—"
    return units.decimal_point(f"{float(x):.2f}".rstrip("0").rstrip("."))

def _dec(x, n: int = 1) -> str:
    if x is None:
        return "—"
    return units.decimal_point(f"{float(x):.{n}f}")

def _money(x) -> str:
    if x is None:
        return "—"
    cur = db_reader.get_currency()
    s = f"{float(x):,.{max(cur['dec'], 2)}f}"
    if db_reader.get_language() != "en":
        s = s.translate(str.maketrans({",": ".", ".": ","}))
    sym = cur["symbol"]
    return f"{sym}{s}" if cur["pos"] == "before" else f"{s} {sym}"

def _price_3(x) -> str:
    if x is None:
        return "—"
    s = f"{float(x):,.3f}"
    if db_reader.get_language() != "en":
        s = s.translate(str.maketrans({",": ".", ".": ","}))
    return s

templates.env.filters["nice"] = _nice
templates.env.filters["dec"] = _dec
templates.env.filters["money"] = _money
templates.env.filters["price3"] = _price_3
templates.env.filters["dist"] = units.dist
templates.env.filters["temp"] = units.temp
templates.env.filters["int"] = lambda x: "" if x is None else str(int(round(float(x))))
templates.env.filters["string"] = lambda x: "" if x is None else str(x)

templates.env.globals.update(
    t=_t,
    dist_unit=units.dist_unit,
    speed_unit=units.speed_unit,
    temp_unit=units.temp_unit,
    dist_val=units.dist_val,
    speed_val=units.speed_val,
    temp_val=units.temp_val,
    charge_energy=db_reader.charge_energy_view,
    range_estimates=lambda r, s: {"limit_est": {"km": r, "pct": 100}, "full_est": {"km": r, "pct": 100}, "show_both": False},
    absent_temps=db_reader.never_reported_temps,
    fmt_dur=lambda m: _fmt_dur(m),
    soc_color=lambda s: _soc_color(s),
    state_color=lambda s: _state_color(s),
    state_label=lambda s: _state_label(s),
)

def _render(request: Request, name: str, ctx: dict, **kwargs):
    """Compatibility wrapper: the installed Starlette requires the request as
    the first positional argument and the context as a keyword."""
    return templates.TemplateResponse(request, name, ctx, **kwargs)

def _fmt_dur(minutes):
    if not minutes:
        return "—"
    m = int(round(float(minutes)))
    h, mm = divmod(m, 60)
    return f"{h}h {mm}m" if h else f"{mm}m"

def _soc_color(soc):
    soc = float(soc or 0)
    r = round(239 - (soc / 100) * 215)
    g = round(130 + (soc / 100) * 125)
    b = round(16 - (soc / 100) * 14)
    return f"rgb({r},{g},{b})"

def _state_label(s):
    if not s:
        return "—"
    if s.get("ready") is None:
        return "—"
    return "Pronto" if s.get("ready") else "Spento"

def _ctx(request: Request, page: str) -> dict:
    vehicle, vehicles = db_reader.get_vehicle()
    vid = vehicle["id"] if vehicle else 1
    status = db_reader.get_latest_status(vid)
    currency = db_reader.get_currency()
    stats = db_reader.get_statistics_summary(vid)
    charge_stats = db_reader.get_charge_stats(vid)
    return {
        "request": request,
        "page": page,
        "vehicle": vehicle,
        "vehicles": vehicles,
        "status": status,
        "currency": currency,
        "cur": currency,
        "stats": stats,
        "charge_stats": charge_stats,
        "battery_history": db_reader.get_battery_history(vid),
        "trips": db_reader.get_all_trips(vid),
        "charges": db_reader.get_all_charges(vid),
        "events": db_reader.get_events(vid),
        "wallbox_enabled": False,
        "auth_enabled": False,
        "auth_unprotected": False,
        "auth_dismissed": True,
        "shell_version": None,
        "desktop_notice_dismissed": True,
        "research": False,
        "beta_notice_dismissed": True,
        "unconfigured_cars": None,
        "demo": True,
        "version": "1.0.0",
    }

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    ctx = _ctx(request, "overview")
    ctx["last_charge"] = db_reader.get_last_charge()
    ctx["recent_trips"] = db_reader.get_recent_trips(limit=4)
    ctx["last_position"] = {
        "lat": ctx["status"].get("latitude") if ctx["status"] else 45.4642,
        "lon": ctx["status"].get("longitude") if ctx["status"] else 9.1900,
        "ago": "3 min fa"
    } if ctx["status"] else {"lat": None, "lon": None, "ago": ""}
    return _render(request, "overview.html", ctx)

@app.get("/api/status-card", response_class=HTMLResponse)
def api_status_card(request: Request):
    ctx = _ctx(request, "overview")
    return _render(request, "partials/status_card.html", ctx)

@app.get("/api/overview-hero", response_class=HTMLResponse)
def api_overview_hero(request: Request):
    ctx = _ctx(request, "overview")
    return _render(request, "partials/overview_hero.html", ctx)

@app.post("/api/command/{cmd}", response_class=HTMLResponse)
def api_command(request: Request, cmd: str):
    client = VolvoApiClient()
    success = client.send_command(cmd)
    if success:
        return HTMLResponse(f'<div class="text-emerald-400 font-medium" data-accepted>Comando "{cmd}" eseguito con successo</div>')
    return HTMLResponse(f'<div class="text-rose-400 font-medium" data-warn>Errore esecuzione comando "{cmd}"</div>')

@app.get("/trips", response_class=HTMLResponse)
def trips_page(request: Request):
    ctx = _ctx(request, "trips")
    ctx["trips"] = db_reader.get_all_trips()
    return _render(request, "trips.html", ctx)

@app.get("/charges", response_class=HTMLResponse)
def charges_page(request: Request):
    ctx = _ctx(request, "charges")
    ctx["charges"] = db_reader.get_all_charges()
    return _render(request, "charges.html", ctx)

@app.get("/statistics", response_class=HTMLResponse)
def statistics_page(request: Request):
    ctx = _ctx(request, "statistics")
    ctx["stats"] = db_reader.get_statistics_summary()
    return _render(request, "statistics.html", ctx)

@app.get("/costs", response_class=HTMLResponse)
def costs_page(request: Request):
    ctx = _ctx(request, "costs")
    ac_e = sum((c.get("energy_kwh") or 0) for c in ctx["charges"] if (c.get("charge_type") or "AC") != "DC")
    dc_e = sum((c.get("energy_kwh") or 0) for c in ctx["charges"] if (c.get("charge_type") or "AC") == "DC")
    ac_n = sum(1 for c in ctx["charges"] if (c.get("charge_type") or "AC") != "DC")
    dc_n = sum(1 for c in ctx["charges"] if (c.get("charge_type") or "AC") == "DC")
    ctx["ac_energy"] = ac_e
    ctx["dc_energy"] = dc_e
    ctx["ac_count"] = ac_n
    ctx["dc_count"] = dc_n
    return _render(request, "costs.html", ctx)

@app.get("/map", response_class=HTMLResponse)
def map_page(request: Request):
    ctx = _ctx(request, "map")
    return _render(request, "map.html", ctx)

@app.get("/commands", response_class=HTMLResponse)
def commands_page(request: Request):
    ctx = _ctx(request, "commands")
    ctx["commands"] = [
        {"key": "lock", "icon": "🔒", "label": _t("hero_lock"), "help": _t("lock_confirm")},
        {"key": "unlock", "icon": "🔓", "label": _t("hero_unlock"), "help": _t("unlock_confirm")},
        {"key": "start_charging", "icon": "⚡", "label": _t("start_charging"), "help": _t("start_charging_help")},
        {"key": "stop_charging", "icon": "⏸", "label": _t("stop_charging"), "help": _t("stop_charging_help")},
        {"key": "honk", "icon": "📢", "label": _t("honk"), "help": _t("honk_help")},
        {"key": "flash", "label": "💡", "icon": "💡", "help": _t("flash_help")},
        {"key": "precondition", "icon": "🌡", "label": _t("precondition"), "help": _t("precondition_help")},
        {"key": "lock_trunk", "icon": "📦", "label": _t("trunk"), "help": _t("trunk_help")},
    ]
    return _render(request, "commands.html", ctx)

@app.get("/battery", response_class=HTMLResponse)
def battery_page(request: Request):
    ctx = _ctx(request, "battery")
    return _render(request, "battery.html", ctx)

@app.get("/maintenance", response_class=HTMLResponse)
def maintenance_page(request: Request):
    ctx = _ctx(request, "maintenance")
    ctx["maintenance_items"] = db_reader.get_maintenance()
    return _render(request, "maintenance.html", ctx)

@app.get("/scheduling", response_class=HTMLResponse)
def scheduling_page(request: Request):
    ctx = _ctx(request, "scheduling")
    ctx["schedules"] = db_reader.get_schedules()
    return _render(request, "scheduling.html", ctx)

@app.get("/navigation", response_class=HTMLResponse)
def navigation_page(request: Request):
    ctx = _ctx(request, "navigation")
    return _render(request, "navigation.html", ctx)

@app.get("/vehicle", response_class=HTMLResponse)
def vehicle_page(request: Request):
    ctx = _ctx(request, "vehicle")
    ctx["vehicle_detail"] = db_reader.get_vehicle_detail()
    return _render(request, "vehicle.html", ctx)

@app.get("/report", response_class=HTMLResponse)
def report_page(request: Request):
    ctx = _ctx(request, "report")
    ctx["stats"] = db_reader.get_statistics_summary()
    return _render(request, "report.html", ctx)

@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    ctx = _ctx(request, "settings")
    ctx["language"] = db_reader.get_language()
    ctx["currency_code"] = db_reader.get_setting("currency", "EUR")
    return _render(request, "settings.html", ctx)

@app.post("/api/settings/save", response_class=HTMLResponse)
def api_settings_save(request: Request,
                     language: str = Form("it"),
                     currency: str = Form("EUR")):
    db_reader.set_setting("language", language)
    db_reader.set_setting("currency", currency)
    return RedirectResponse(url="settings", status_code=303)

@app.post("/api/navigation", response_class=JSONResponse)
async def api_navigation(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    dest = (body.get("destination") or "").strip()
    if not dest:
        return JSONResponse({"ok": False, "message": _t("destination_required")})
    client = VolvoApiClient()
    ok = client.send_command("navigate", dest)
    return JSONResponse({"ok": ok, "message": _t("sent") if ok else _t("error"), "destination": dest})

@app.get("/api/refresh", response_class=HTMLResponse)
def api_refresh(request: Request):
    ctx = _ctx(request, "overview")
    ctx["last_charge"] = db_reader.get_last_charge()
    ctx["recent_trips"] = db_reader.get_recent_trips(limit=4)
    st = ctx["status"]
    ctx["last_position"] = {
        "lat": st.get("latitude") if st else None,
        "lon": st.get("longitude") if st else None,
        "ago": f"{st.get('data_age_s', 0)}s fa" if st else "",
    } if st else {"lat": None, "lon": None, "ago": ""}
    return _render(request, "partials/status_card.html", ctx)

@app.get("/api/demo/status", response_class=JSONResponse)
def api_demo_status():
    return JSONResponse({"demo": True, "restarting": False})

@app.post("/api/demo/disable", response_class=JSONResponse)
def api_demo_disable():
    return JSONResponse({"ok": True, "restarting": False})

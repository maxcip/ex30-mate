from poller.volvo_api import VolvoApiClient
from web.db_reader import get_language


def indicators():
    client = VolvoApiClient()
    try:
        states = (client._states() or {}) if not client.demo_mode else {}
    except (ValueError, KeyError, TypeError):
        states = {}
    it = get_language() == 'it'
    positions = ('front_left', 'front_right', 'rear_left', 'rear_right')
    names = ('Ant. sx', 'Ant. dx', 'Post. sx', 'Post. dx') if it else ('Front left', 'Front right', 'Rear left', 'Rear right')
    groups = [('Finestrini' if it else 'Windows', 'window'), ('Portiere' if it else 'Doors', 'door'), ('Bagagliaio' if it else 'Tailgate', 'tailgate'), ('Gomme' if it else 'Tyres', 'tire')]
    result = []
    for title, key in groups:
        items = [(key, title)] if key == 'tailgate' else [(f'{key}_{pos}', label) for pos, label in zip(positions, names)]
        readings = [(label, client._s(states, f'binary_sensor.{client.p}_{suffix}')) for suffix, label in items]
        alert = ('Pressione anomala' if key == 'tire' else 'Aperto') if it else ('Pressure warning' if key == 'tire' else 'Open')
        missing = 'Dato non disponibile' if it else 'Unavailable'
        ok = 'Nessun allarme' if it else 'No warning'
        active = [label for label, state in readings if state == 'on']
        color = '#991b1b' if active else '#166534' if all(s == 'off' for _, s in readings) else '#475569'
        summary = alert + (': ' + ', '.join(active) if key != 'tailgate' else '') if active else (ok if color == '#166534' else missing)
        result.append((title, color, summary, [(label, alert if s == 'on' else ok if s == 'off' else missing) for label, s in readings]))
    return result

// trip-track.js — draw a trip polyline on the overview map.
// Leaflet is loaded by overview.html before this file.
(function () {
  "use strict";

  function renderTrack(containerId, points, opts) {
    opts = opts || {};
    var el = document.getElementById(containerId);
    if (!el || typeof L === "undefined") return null;

    if (el._mateMap) {
      try { el._mateMap.remove(); } catch (e) { /* ignore */ }
    }

    var map = L.map(el, { zoomControl: true, attributionControl: true }).setView(
      opts.center || [45.4642, 9.19], opts.zoom || 13
    );

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map);

    if (points && points.length) {
      var latlngs = points.map(function (p) { return [p[0], p[1]]; });
      L.polyline(latlngs, { color: "#14b8a6", weight: 4, opacity: 0.85 }).addTo(map);
      map.fitBounds(latlngs, { padding: [24, 24] });
    } else if (opts.center) {
      L.marker(opts.center).addTo(map);
    }

    el._mateMap = map;
    return map;
  }

  window.MateMap = { renderTrack: renderTrack };
})();
// band-chart.js — shared helpers for the band / range charts used by the
// battery and statistics pages. Built on top of ApexCharts, which is loaded
// by base.html before this file.
(function () {
  "use strict";

  // Build a single-series area chart that fills between a low and a high
  // band. Used to visualise state-of-charge and range over time.
  function bandChart(el, series, opts) {
    opts = opts || {};
    var low = opts.low || 0;
    var high = opts.high || 100;
    var color = opts.color || "#14b8a6";
    var unit = opts.unit || "";
    var fmt = opts.fmt || function (v) { return v; };

    var data = series.map(function (p) {
      return { x: p.t, y: [p.low, p.high] };
    });

    var chart = new ApexCharts(el, {
      series: [{ name: "Band", data: data }],
      chart: {
        type: "area",
        height: opts.height || 260,
        toolbar: { show: false },
        zoom: { enabled: false },
        animations: { enabled: false },
      },
      colors: [color],
      fill: {
        type: "gradient",
        gradient: { shade: "dark", opacityFrom: 0.55, opacityTo: 0.05 },
      },
      stroke: { curve: "straight", width: 2, colors: [color] },
      grid: { strokeDashArray: 4, borderColor: "#334155" },
      xaxis: {
        type: "datetime",
        labels: { style: { colors: "#94a3b8" }, datetimeUTC: false },
        axisBorder: { show: false },
      },
      yaxis: {
        min: low,
        max: high,
        labels: { style: { colors: "#94a3b8" }, formatter: function (v) { return fmt(v) + unit; } },
      },
      tooltip: {
        theme: "dark",
        x: { format: "dd/MM HH:mm" },
        y: { formatter: function (v) { return fmt(v) + unit; } },
      },
    });
    chart.render();
    return chart;
  }

  // Render a simple sparkline (no axes) for the trip summary tiles.
  function sparkline(el, data, color) {
    color = color || "#14b8a6";
    var chart = new ApexCharts(el, {
      series: [{ name: "v", data: data.map(function (v) { return { x: null, y: v }; }) }],
      chart: { type: "area", height: 48, sparkline: { enabled: true }, animations: { enabled: false } },
      colors: [color],
      fill: { type: "gradient", gradient: { shade: "dark", opacityFrom: 0.6, opacityTo: 0 } },
      stroke: { width: 2, curve: "straight" },
      tooltip: { enabled: false },
    });
    chart.render();
    return chart;
  }

  window.MateCharts = { bandChart: bandChart, sparkline: sparkline };
})();
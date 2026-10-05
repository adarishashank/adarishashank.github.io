/* Charts: contribution heatmap, column chart, horizontal bars. Plain SVG, sized to the container
 * in real pixels (so text never scales), redrawn on resize. Single-series, so no legends; values
 * live in the tooltip and selective direct labels. */
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

  function el(name, attrs, parent) {
    var n = document.createElementNS(NS, name);
    for (var k in attrs) if (attrs[k] != null) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function text(parent, x, y, str, attrs) {
    var t = el("text", Object.assign({ x: x, y: y }, attrs || {}), parent);
    t.textContent = str;
    return t;
  }
  function fmtDate(iso, withYear) {
    var d = new Date(iso + "T00:00:00");
    return DAYS[d.getDay()] + ", " + d.getDate() + " " + MONTHS[d.getMonth()] + (withYear === false ? "" : " " + d.getFullYear());
  }
  function plural(n, unit) { return n + " " + unit + (n === 1 ? "" : "s"); }
  function nice(max) {
    if (max <= 0) return 1;
    if (max <= 4) return Math.ceil(max);
    var exp = Math.pow(10, Math.floor(Math.log10(max))), f = max / exp;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * exp;
  }
  function onResize(node, draw) {
    var last = 0;
    draw();
    if (!("ResizeObserver" in window)) return;
    new ResizeObserver(function () {
      var w = node.clientWidth;
      if (Math.abs(w - last) > 4) { last = w; draw(); }
    }).observe(node);
  }
  function bindTip(target, html) {
    target.addEventListener("mouseenter", function (e) { window.Tip && Tip.show(html(), e.clientX, e.clientY); });
    target.addEventListener("mousemove", function (e) { window.Tip && Tip.show(html(), e.clientX, e.clientY); });
    target.addEventListener("mouseleave", function () { window.Tip && Tip.hide(); });
  }
  // a bar with a 4px rounded data end and a square baseline end
  function barPath(x, y, w, h, horizontal) {
    if (w <= 0 || h <= 0) return "";
    if (horizontal) {
      var rh = Math.min(4, h / 2, w);
      return "M" + x + "," + y + "H" + (x + w - rh) + "Q" + (x + w) + "," + y + " " + (x + w) + "," + (y + rh) +
        "V" + (y + h - rh) + "Q" + (x + w) + "," + (y + h) + " " + (x + w - rh) + "," + (y + h) + "H" + x + "Z";
    }
    var r = Math.min(4, w / 2, h);
    return "M" + x + "," + (y + h) + "V" + (y + r) + "Q" + x + "," + y + " " + (x + r) + "," + y +
      "H" + (x + w - r) + "Q" + (x + w) + "," + y + " " + (x + w) + "," + (y + r) + "V" + (y + h) + "Z";
  }

  // ------------------------------------------------------------------ heatmap
  function heatmap(node, opts) {
    var cal = opts.calendar || [], t = opts.levels || [1, 2, 3, 4], unit = opts.unit || "contribution";
    if (!cal.length) { node.innerHTML = '<p class="chart-empty muted">No activity recorded yet.</p>'; return; }
    var weeks = Math.ceil(cal.length / 7), left = 30, top = 18, gap = 3;
    var total = cal.reduce(function (s, d) { return s + d.c; }, 0);
    onResize(node, function () {
      node.innerHTML = "";
      // size cells from the real container width so labels stay 11px; scroll sideways below ~9px cells
      var cell = Math.max(opts.minCell || 9, Math.min(16, Math.floor((node.clientWidth - left) / weeks) - gap));
      var step = cell + gap, W = left + weeks * step, H = top + 7 * step;
      var svg = el("svg", { width: W, height: H, viewBox: "0 0 " + W + " " + H, role: "img",
        "aria-label": plural(total, unit) + " between " + cal[0].d + " and " + cal[cal.length - 1].d }, node);

      [1, 3, 5].forEach(function (r) { text(svg, 0, top + r * step + cell - 2, DAYS[r]); });
      var lastMonth = -1, lastLabelW = -9;
      for (var w = 0; w < weeks; w++) {
        var first = cal[w * 7];
        if (!first) break;
        var m = new Date(first.d + "T00:00:00").getMonth();
        if (m !== lastMonth) {
          lastMonth = m;
          if (w - lastLabelW >= 3 && w < weeks - 2) { text(svg, left + w * step, 11, MONTHS[m]); lastLabelW = w; }
        }
      }
      var g = el("g", {}, svg);
      cal.forEach(function (d, i) {
        var lvl = d.c <= 0 ? 0 : d.c >= t[3] ? 4 : d.c >= t[2] ? 3 : d.c >= t[1] ? 2 : 1;
        var r = el("rect", { class: "cell l" + lvl, x: left + Math.floor(i / 7) * step, y: top + (i % 7) * step,
          width: cell, height: cell, rx: 2.5 }, g);
        r.addEventListener("mouseenter", function (e) {
          Tip.show("<b>" + (d.c ? plural(d.c, unit) : "No " + unit + "s") + "</b><br>" + fmtDate(d.d), e.clientX, e.clientY);
        });
      });
      g.addEventListener("mouseleave", function () { Tip.hide(); });
      node.scrollLeft = node.scrollWidth;  // newest weeks visible on narrow screens
    });
  }

  // ------------------------------------------------------------------ column chart
  function columns(node, opts) {
    onResize(node, function () {
      node.innerHTML = "";
      var vals = opts.values || [], labels = opts.labels || [], unit = opts.unit || "contribution";
      var W = Math.max(240, node.clientWidth), H = opts.height || 190;
      var padL = 30, padR = 6, padT = 18, padB = 24;
      var plotW = W - padL - padR, plotH = H - padT - padB;
      var max = nice(Math.max.apply(null, vals.concat([0])));
      var svg = el("svg", { width: W, height: H, viewBox: "0 0 " + W + " " + H, role: "img",
        "aria-label": opts.title + ": " + labels.map(function (l, i) { return l + " " + vals[i]; }).join(", ") }, node);

      var ticks = max <= 1 ? [0, 1] : [0, max / 2, max];
      ticks.forEach(function (tv) {
        if (Math.floor(tv) !== tv) return;
        var y = padT + plotH - (tv / max) * plotH;
        el("line", { class: tv === 0 ? "base" : "grid", x1: padL, x2: W - padR, y1: y, y2: y }, svg);
        text(svg, padL - 6, y + 4, String(tv), { "text-anchor": "end" });
      });

      var band = plotW / vals.length, bw = Math.min(24, band * 0.62);
      var peak = vals.indexOf(Math.max.apply(null, vals));
      vals.forEach(function (v, i) {
        var x = padL + i * band + (band - bw) / 2, h = (v / max) * plotH, y = padT + plotH - h;
        var grp = el("g", {}, svg);
        var hit = el("rect", { class: "bar-hit", x: padL + i * band, y: padT, width: band, height: plotH }, grp);
        if (h > 0) el("path", { class: "bar", d: barPath(x, y, bw, h) }, grp);
        if (i === peak && v > 0) text(grp, x + bw / 2, y - 5, String(v), { class: "val", "text-anchor": "middle" });
        var showLabel = vals.length <= 8 || i % 2 === (vals.length - 1) % 2;
        if (showLabel) text(svg, x + bw / 2, H - 6, labels[i], { "text-anchor": "middle" });
        bindTip(hit, function () { return "<b>" + plural(v, unit) + "</b><br>" + (opts.tipLabels ? opts.tipLabels[i] : labels[i]); });
        hit.addEventListener("mouseenter", function () { grp.classList.add("is-hover"); });
        hit.addEventListener("mouseleave", function () { grp.classList.remove("is-hover"); });
      });
    });
  }

  // ------------------------------------------------------------------ horizontal bars
  function hbars(node, opts) {
    var items = opts.items || [];
    if (!items.length) { node.innerHTML = '<p class="chart-empty muted">Nothing to show yet.</p>'; return; }
    onResize(node, function () {
      node.innerHTML = "";
      var W = Math.max(240, node.clientWidth), row = 26, bh = 14;
      var labelW = Math.min(110, W * 0.36), valW = 28;
      var H = items.length * row + 4, plotW = W - labelW - valW - 8;
      var max = Math.max.apply(null, items.map(function (d) { return d.value; }).concat([1]));
      var svg = el("svg", { width: W, height: H, viewBox: "0 0 " + W + " " + H, role: "img",
        "aria-label": opts.title + ": " + items.map(function (d) { return d.label + " " + d.value; }).join(", ") }, node);
      el("line", { class: "base", x1: labelW, x2: labelW, y1: 0, y2: H }, svg);
      items.forEach(function (d, i) {
        var y = i * row + (row - bh) / 2, w = (d.value / max) * plotW;
        var grp = el("g", {}, svg);
        var hit = el("rect", { class: "bar-hit", x: 0, y: i * row, width: W, height: row }, grp);
        text(grp, labelW - 8, y + bh - 3, d.label, { class: "label", "text-anchor": "end" });
        el("path", { class: "bar", d: barPath(labelW, y, w, bh, true) }, grp);
        text(grp, labelW + w + 6, y + bh - 3, String(d.value), { class: "val" });
        bindTip(hit, function () { return "<b>" + d.label + "</b><br>" + plural(d.value, opts.unit || "item"); });
      });
    });
  }

  window.Charts = { heatmap: heatmap, columns: columns, hbars: hbars, fmtDate: fmtDate, MONTHS: MONTHS };
})();

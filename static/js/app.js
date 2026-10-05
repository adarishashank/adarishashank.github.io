/* Page behaviour. Each block checks for its own markup, so one file serves every page. */
(function () {
  "use strict";
  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };
  var esc = window.esc;
  function json(id) { var n = document.getElementById(id); try { return n ? JSON.parse(n.textContent) : null; } catch (e) { return null; } }

  // ================================================================ chrome: sticky border, active nav, reveal
  (function chrome() {
    var bar = $("#topbar");
    if (bar) {
      var onScroll = function () { bar.classList.toggle("is-stuck", window.scrollY > 8); };
      window.addEventListener("scroll", onScroll, { passive: true }); onScroll();
    }
    var links = {};
    $$("[data-nav]").forEach(function (a) { links[a.getAttribute("data-nav")] = a; });
    if ("IntersectionObserver" in window && document.body.classList.contains("page-home")) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          var a = links[en.target.id === "services" || en.target.id === "certificates" ? "experience" : en.target.id];
          if (!a || !en.isIntersecting) return;
          Object.keys(links).forEach(function (k) { links[k].classList.remove("is-active"); });
          a.classList.add("is-active");
        });
      }, { rootMargin: "-40% 0px -55% 0px" });
      ["about", "skills", "projects", "experience", "certificates", "services", "contact"].forEach(function (id) { var s = document.getElementById(id); if (s) io.observe(s); });
      var rv = new IntersectionObserver(function (entries) { entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add("is-in"); rv.unobserve(en.target); } }); }, { rootMargin: "0px 0px -8% 0px" });
      $$(".sec__head, .proj, .xp, .cert, .tile-s, .principle, .svc").forEach(function (el) { el.classList.add("reveal"); rv.observe(el); });
    }
  })();

  // ================================================================ hero graph: a small force layout, no dependencies
  (function graph() {
    var host = $("#graph"), data = json("graph-data");
    if (!host || !data) return;
    var NS = "http://www.w3.org/2000/svg";
    var W = 600, H = 560, cx = W / 2, cy = H / 2;
    var nodes = [], edges = [], byId = {};
    function add(n) { nodes.push(n); byId[n.id] = n; return n; }
    add({ id: "me", kind: "me", r: 40, x: cx, y: cy, label: data.name });
    data.domains.forEach(function (d, i) {
      var a = -Math.PI / 2 + i * 2 * Math.PI / data.domains.length;
      add({ id: d.id, kind: "domain", r: 24, x: cx + Math.cos(a) * 178, y: cy + Math.sin(a) * 178, label: d.label, tone: d.tone, target: d.target, tip: d.tip });
      edges.push({ a: "me", b: d.id, len: 178, main: true });
    });
    data.tools.forEach(function (t, i) {
      var id = "t" + i, first = byId[t.to[0]];
      var a = Math.atan2(first.y - cy, first.x - cx) + (Math.random() - 0.5) * 1.2;
      add({ id: id, kind: "tool", r: 6, x: cx + Math.cos(a) * 262, y: cy + Math.sin(a) * 262, label: t.label, lm: 16 + t.label.length * 6.6 });
      t.to.forEach(function (d) { edges.push({ a: id, b: d, len: 108 }); });
    });

    var svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    var defs = document.createElementNS(NS, "defs");
    defs.innerHTML = '<clipPath id="g-clip"><circle cx="0" cy="0" r="36"/></clipPath>';
    svg.appendChild(defs);
    var gE = document.createElementNS(NS, "g"), gN = document.createElementNS(NS, "g");
    svg.appendChild(gE); svg.appendChild(gN);
    edges.forEach(function (e) {
      e.el = document.createElementNS(NS, "line");
      e.el.setAttribute("class", "g-edge" + (e.main ? " g-edge--main" : ""));
      gE.appendChild(e.el);
    });
    nodes.forEach(function (n) {
      var g = document.createElementNS(NS, "g");
      g.setAttribute("class", "g-node g-" + n.kind + (n.tone ? " tone-" + n.tone : ""));
      if (n.kind === "me") {
        g.innerHTML = '<image href="' + esc(data.avatar) + '" x="-36" y="-36" width="72" height="72" clip-path="url(#g-clip)" preserveAspectRatio="xMidYMid slice"/>' +
          '<circle class="ring" r="40"/><text y="58" text-anchor="middle">that\'s me</text>';
      } else if (n.kind === "domain") {
        g.innerHTML = '<circle r="' + n.r + '"/><text y="' + (n.r + 18) + '" text-anchor="middle">' + esc(n.label) + "</text>";
        g.setAttribute("data-tip", n.tip);
        g.addEventListener("click", function () { if (!n.dragged) { var t = $(n.target); if (t) t.scrollIntoView({ behavior: window.reducedMotion ? "auto" : "smooth" }); } });
        g.addEventListener("mouseenter", function () { focus(n); });
        g.addEventListener("mouseleave", function () { focus(null); });
      } else {
        g.innerHTML = '<circle r="' + n.r + '"/><text x="11" y="4">' + esc(n.label) + "</text>";
        n.txt = g.querySelector("text");
      }
      n.el = g;
      gN.appendChild(g);
      // drag
      var start = null;
      g.addEventListener("pointerdown", function (e) {
        e.preventDefault(); g.setPointerCapture(e.pointerId);
        var p = pt(e); start = { x: p.x - n.x, y: p.y - n.y }; n.fx = n.x; n.fy = n.y; n.dragged = false; alpha = Math.max(alpha, 0.5);
      });
      g.addEventListener("pointermove", function (e) {
        if (!start) return;
        var p = pt(e); n.fx = p.x - start.x; n.fy = p.y - start.y; n.dragged = true; alpha = Math.max(alpha, 0.3);
      });
      var up = function () { if (!start) return; start = null; n.fx = n.fy = null; setTimeout(function () { n.dragged = false; }, 50); };
      g.addEventListener("pointerup", up); g.addEventListener("pointercancel", up);
    });
    host.appendChild(svg);
    function pt(e) { var m = svg.getScreenCTM().inverse(), p = svg.createSVGPoint(); p.x = e.clientX; p.y = e.clientY; return p.matrixTransform(m); }
    function focus(n) {
      var keep = {};
      if (n) { keep[n.id] = true; keep.me = true; edges.forEach(function (e) { if (e.a === n.id || e.b === n.id) { keep[e.a] = true; keep[e.b] = true; } }); }
      nodes.forEach(function (m) { m.el.classList.toggle("g-faded", !!n && !keep[m.id]); });
      edges.forEach(function (e) { e.el.classList.toggle("g-faded", !!n && !(keep[e.a] && keep[e.b])); });
    }

    var alpha = 1;
    function tick() {
      // repulsion
      for (var i = 0; i < nodes.length; i++) for (var j = i + 1; j < nodes.length; j++) {
        var a = nodes[i], b = nodes[j], dx = b.x - a.x, dy = b.y - a.y, d2 = dx * dx + dy * dy + 0.01, d = Math.sqrt(d2);
        var k = (a.kind === "tool" && b.kind === "tool" ? 2600 : a.kind !== "tool" && b.kind !== "tool" ? 11000 : 3000) / d2;
        var fx = dx / d * k, fy = dy / d * k;
        a.vx -= fx; a.vy -= fy; b.vx += fx; b.vy += fy;
      }
      // springs
      edges.forEach(function (e) {
        var a = byId[e.a], b = byId[e.b], dx = b.x - a.x, dy = b.y - a.y, d = Math.sqrt(dx * dx + dy * dy) + 0.01;
        var f = (d - e.len) * 0.02, fx = dx / d * f, fy = dy / d * f;
        a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
      });
      nodes.forEach(function (n) {
        n.vx += (cx - n.x) * (n.kind === "me" ? 0.08 : 0.004); n.vy += (cy - n.y) * (n.kind === "me" ? 0.08 : 0.004);
        if (n.fx != null) { n.x = n.fx; n.y = n.fy; n.vx = n.vy = 0; return; }
        n.vx *= 0.82; n.vy *= 0.82;
        n.x += n.vx * alpha; n.y += n.vy * alpha;
        var m = n.r + 10;
        var lm = n.kind === "tool" ? n.lm : 0;
        n.x = Math.max(m + lm, Math.min(W - m - lm, n.x)); n.y = Math.max(m, Math.min(H - m - 16, n.y));
      });
    }
    function draw() {
      nodes.forEach(function (n) {
        n.el.setAttribute("transform", "translate(" + n.x.toFixed(1) + " " + n.y.toFixed(1) + ")");
        if (n.txt) { var left = n.x < cx; n.txt.setAttribute("x", left ? -11 : 11); n.txt.setAttribute("text-anchor", left ? "end" : "start"); }
      });
      edges.forEach(function (e) { var a = byId[e.a], b = byId[e.b]; e.el.setAttribute("x1", a.x); e.el.setAttribute("y1", a.y); e.el.setAttribute("x2", b.x); e.el.setAttribute("y2", b.y); });
    }
    nodes.forEach(function (n) { n.vx = n.vy = 0; });
    for (var k = 0; k < 220; k++) tick();   // settle before first paint
    draw();
    if (window.reducedMotion) return;
    alpha = 0.6;
    (function frame() {
      tick(); draw();
      alpha = Math.max(0.05, alpha * 0.985);
      requestAnimationFrame(frame);
    })();
  })();

  // ================================================================ intro film
  (function film() {
    var v = $("#intro-video"), btn = $("#intro-toggle");
    if (!v) return;
    var narrow = window.matchMedia && matchMedia("(max-width: 900px)").matches;
    var src = v.getAttribute(narrow ? "data-src-narrow" : "data-src-wide");
    if (src && v.currentSrc !== src) { v.src = src; v.load(); }
    function label(playing) {
      btn.setAttribute("aria-label", playing ? "Pause the film" : "Play the film");
      btn.setAttribute("aria-pressed", String(!playing));
      btn.querySelector("span").textContent = playing ? "Pause" : "Play";
      btn.classList.toggle("is-paused", !playing);
    }
    if (window.reducedMotion) { label(false); }
    else {
      var p = v.play();
      if (p && p.catch) p.catch(function () { label(false); });
      // only spend bandwidth while the film is on screen
      if ("IntersectionObserver" in window) {
        new IntersectionObserver(function (en) {
          if (btn.classList.contains("is-paused")) return;
          if (en[0].isIntersecting) { var q = v.play(); if (q && q.catch) q.catch(function () {}); } else v.pause();
        }, { threshold: 0.2 }).observe(v);
      }
    }
    btn.addEventListener("click", function () {
      if (v.paused) { var q = v.play(); if (q && q.catch) q.catch(function () {}); label(true); } else { v.pause(); label(false); }
    });
    v.addEventListener("play", function () { label(true); });
  })();

  // ================================================================ dialogs (projects, roles)
  (function dialogs() {
    function open(id, push) {
      var d = document.getElementById(id);
      if (!d || !d.showModal) return;
      d.showModal();
      if (push) history.replaceState(null, "", "#" + id.replace(/^dlg-/, ""));
    }
    document.addEventListener("click", function (e) {
      var b = e.target.closest("[data-dialog]");
      if (b) { open(b.getAttribute("data-dialog"), true); return; }
      var c = e.target.closest("[data-close]");
      if (c) { c.closest("dialog").close(); return; }
      var d = e.target.closest("dialog");
      if (d && e.target === d) d.close();   // click on the backdrop
    });
    $$("dialog").forEach(function (d) { d.addEventListener("close", function () { if (location.hash === "#" + d.id.replace(/^dlg-/, "")) history.replaceState(null, "", location.pathname); }); });
    var h = location.hash.slice(1);
    if (h && document.getElementById("dlg-" + h)) setTimeout(function () { open("dlg-" + h, false); }, 300);
  })();

  // ================================================================ figures in dialogs
  (function figures() {
    document.addEventListener("mousemove", function (e) {
      var t = e.target.closest && e.target.closest("[data-tip]");
      if (t) window.Tip.show(esc(t.getAttribute("data-tip")), e.clientX, e.clientY);
    });
    document.addEventListener("mouseout", function (e) {
      var t = e.target.closest && e.target.closest("[data-tip]");
      if (t && !(e.relatedTarget && t.contains(e.relatedTarget))) window.Tip.hide();
    });
  })();

  // ================================================================ SQL playground
  (function console_() {
    var root = $("#sql");
    if (!root || !window.MiniSQL) return;
    var editor = $("#sql-editor"), status = $("#sql-status"), result = $("#sql-result");
    var tablesUrl = root.getAttribute("data-tables"), tables = null, loading = null, last = null;
    function load() {
      if (!loading) loading = fetch(tablesUrl).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }).then(function (t) { tables = t; return t; });
      return loading;
    }
    function setStatus(msg, cls) { status.className = "sql__status mono" + (cls ? " " + cls : ""); status.innerHTML = msg; }
    function render(res, ms) {
      last = res;
      if (res.kind === "text") { result.innerHTML = "<pre>" + esc(res.text) + "</pre>"; setStatus("✓ ok · " + ms.toFixed(1) + " ms", "is-ok"); return; }
      var num = res.types.map(function (t) { return /int|double|float|decimal|bigint/.test(t); });
      var head = res.columns.map(function (c, i) { return '<th class="' + (num[i] ? "num" : "") + '">' + esc(c) + '<span class="th-type">' + esc(res.types[i]) + "</span></th>"; }).join("");
      var body = res.rows.map(function (r) {
        return "<tr>" + r.map(function (v, i) {
          if (v == null) return '<td class="null">null</td>';
          var shown = typeof v === "number" && Math.floor(v) !== v ? (Math.round(v * 1e4) / 1e4) : v;
          return '<td class="' + (num[i] ? "num" : "") + '">' + esc(shown) + "</td>";
        }).join("") + "</tr>";
      }).join("");
      result.innerHTML = res.rows.length ? '<table class="data-table"><thead><tr>' + head + "</tr></thead><tbody>" + body + "</tbody></table>" : "";
      var n = res.rows.length;
      setStatus("✓ " + n + " row" + (n === 1 ? "" : "s") + (res.total != null && res.total !== n ? " of " + res.total : "") + (res.truncated ? " (display capped)" : "") + " · " + ms.toFixed(1) + " ms" +
        (res.note ? ' · <span class="muted">' + esc(res.note) + "</span>" : "") + (n ? ' · <button type="button" class="link-btn mono" id="sql-csv">download csv</button>' : ""), "is-ok");
    }
    function run(sql) {
      if (sql != null) editor.value = sql;
      var q = editor.value.trim();
      if (!q) return;
      setStatus("running…");
      load().then(function () {
        var t0 = performance.now();
        try { render(MiniSQL.execute(q, tables), performance.now() - t0); }
        catch (err) { result.innerHTML = ""; setStatus(esc(err.message), "is-error"); }
      }).catch(function (err) { setStatus("Could not load tables (" + esc(err.message) + "). Serve the site over http, not file://.", "is-error"); });
    }
    function csv() {
      if (!last || last.kind !== "table") return;
      var cell = function (v) { if (v == null) return ""; var s = String(v); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
      var lines = [last.columns.map(cell).join(",")].concat(last.rows.map(function (r) { return r.map(cell).join(","); }));
      var a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([lines.join("\n") + "\n"], { type: "text/csv" }));
      a.download = "query_result.csv"; document.body.appendChild(a); a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
    }
    $("#sql-run").addEventListener("click", function () { run(); });
    editor.addEventListener("keydown", function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); run(); }
      if (e.key === "Tab" && !e.shiftKey) { e.preventDefault(); editor.setRangeText("  ", editor.selectionStart, editor.selectionEnd, "end"); }
    });
    root.addEventListener("click", function (e) {
      var p = e.target.closest("[data-sql]"); if (p) { run(p.getAttribute("data-sql")); return; }
      var t = e.target.closest("[data-table]"); if (t) { run("SELECT * FROM " + t.dataset.table + " LIMIT 20"); return; }
      if (e.target.id === "sql-csv") csv();
    });
    run();
  })();

  // ================================================================ activity page
  (function telemetry() {
    var data = json("telemetry-data");
    if (!data || !window.Charts) return;
    var heat = $("#heatmap");
    if (heat) Charts.heatmap(heat, { calendar: data.calendar, levels: data.levels, unit: "contribution", minCell: Number(heat.getAttribute("data-min-cell")) || 9 });
    var wd = $("#chart-weekday");
    if (wd) Charts.columns(wd, { title: "Contributions by weekday", unit: "contribution", labels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], values: data.weekday,
      tipLabels: ["Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays", "Sundays"].map(function (d) { return d + ", past year"; }) });
    var mo = $("#chart-monthly");
    if (mo) Charts.columns(mo, { title: "Contributions per month", unit: "contribution",
      labels: data.monthly.map(function (m) { return Charts.MONTHS[Number(m.m.slice(5)) - 1]; }),
      tipLabels: data.monthly.map(function (m) { return Charts.MONTHS[Number(m.m.slice(5)) - 1] + " " + m.m.slice(0, 4); }),
      values: data.monthly.map(function (m) { return m.c; }) });
    var lg = $("#chart-langs");
    if (lg) Charts.hbars(lg, { title: "Main language of my repositories", unit: "repo", items: data.languages.map(function (l) { return { label: l.name, value: l.repos }; }) });
    $$("[data-toggle-table]").forEach(function (b) {
      b.addEventListener("click", function () {
        var t = document.getElementById(b.getAttribute("data-toggle-table"));
        t.hidden = !t.hidden; b.setAttribute("aria-expanded", String(!t.hidden)); b.textContent = t.hidden ? "view as table" : "hide table";
      });
    });
    $$("[data-fresh]").forEach(function (d) { if (Date.now() - Date.parse(d.getAttribute("data-fresh")) > 48 * 3600 * 1000) d.classList.add("is-stale"); });
    var rows = $$(".gantt__row"), total = rows.reduce(function (s, r) { return s + Number(r.dataset.ms || 0); }, 0) || 1, acc = 0;
    rows.forEach(function (r) {
      var ms = Number(r.dataset.ms || 0), bar = $(".gantt__bar", r);
      bar.style.left = (acc / total * 100) + "%"; bar.style.width = Math.max(0.6, ms / total * 100) + "%"; acc += ms;
    });
    var list = $("#stream-list");
    if (!data.live || !list || !window.fetch) return;
    var seen = {};
    (data.events || []).forEach(function (e) { seen[e.id] = true; });
    var key = "gh-events-" + data.user, cached = null;
    try { cached = JSON.parse(sessionStorage.getItem(key) || "null"); } catch (e) { cached = null; }
    var fresh = cached && Date.now() - cached.t < 10 * 60 * 1000;
    (fresh ? Promise.resolve(cached.events) : fetch("https://api.github.com/users/" + encodeURIComponent(data.user) + "/events/public?per_page=30")
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (ev) { try { sessionStorage.setItem(key, JSON.stringify({ t: Date.now(), events: ev })); } catch (e) { /* ignore */ } return ev; }))
      .then(function (ev) {
        $("#stream-live").hidden = false;
        var incoming = ev.filter(function (e) { return !seen[e.id]; });
        if (!incoming.length) return;
        var empty = $(".ev--empty", list); if (empty) empty.remove();
        var offset = data.events.length + incoming.length - 1;
        list.insertAdjacentHTML("afterbegin", incoming.slice(0, 12).map(function (e, i) {
          return '<li class="ev is-new"><span class="ev__off">' + String(offset - i).padStart(4, "0") + "</span>" +
            '<time class="ev__ts" datetime="' + esc(e.created_at) + '">' + esc(e.created_at.slice(0, 16).replace("T", " ")) + "</time>" +
            '<span class="ev__type">' + esc(e.type.replace("Event", "")) + "</span>" +
            '<span class="ev__body"><a href="https://github.com/' + esc(e.repo.name) + '" rel="noopener" target="_blank">' + esc(e.repo.name.split("/").pop()) + "</a> <span class=\"muted\">" + esc(summary(e)) + "</span></span></li>";
        }).join(""));
      }).catch(function () { /* offline or rate-limited: the saved events still show */ });
    function summary(e) {
      var p = e.payload || {}, ref = (p.ref || "").replace("refs/heads/", "");
      switch (e.type) {
        case "PushEvent": var n = p.size || (p.commits || []).length; return n ? "pushed " + n + " commit" + (n === 1 ? "" : "s") + " to " + ref : "pushed to " + (ref || "a branch");
        case "CreateEvent": return "created " + (p.ref_type || "ref") + " " + (p.ref || "");
        case "PullRequestEvent": return (p.action || "") + " PR #" + ((p.pull_request || {}).number || "");
        case "IssuesEvent": return (p.action || "") + " issue #" + ((p.issue || {}).number || "");
        case "WatchEvent": return "starred the repo";
        case "ForkEvent": return "forked the repo";
        case "ReleaseEvent": return "released " + ((p.release || {}).tag_name || "");
        default: return e.type.replace("Event", "").toLowerCase();
      }
    }
  })();

  // ================================================================ contact form (and "Ask about this" buttons)
  (function contact() {
    var form = $("#contact-form");
    if (!form) return;
    var status = $("#contact-status"), f = form.elements, labels = {};
    $$("option", f.topic).forEach(function (o) { labels[o.value] = o.textContent; });
    document.addEventListener("click", function (e) {
      var b = e.target.closest("[data-service]");
      if (!b) return;
      f.topic.value = b.getAttribute("data-service");
      $("#contact").scrollIntoView({ behavior: window.reducedMotion ? "auto" : "smooth" });
      setTimeout(function () { f.name.focus({ preventScroll: true }); }, window.reducedMotion ? 0 : 500);
    });
    function setStatus(msg, cls) { status.className = "job__status" + (cls ? " " + cls : ""); status.innerHTML = msg; }
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var bad = [];
      [f.name, f.email, f.message].forEach(function (input) {
        var ok = input.value.trim() && (input.type !== "email" || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(input.value.trim()));
        input.setAttribute("aria-invalid", String(!ok)); if (!ok) bad.push(input);
      });
      if (bad.length) { setStatus("✗ Please check the highlighted fields", "is-error"); bad[0].focus(); return; }
      if (f._gotcha.value) { setStatus("✓ Sent", "is-ok"); return; }
      var topic = labels[f.topic.value], subject = "[" + topic + "] from " + f.name.value.trim();
      var body = ["Name: " + f.name.value.trim(), "Email: " + f.email.value.trim(), "About: " + topic, "", f.message.value.trim()].join("\n");
      var mailto = "mailto:" + form.getAttribute("data-email") + "?subject=" + encodeURIComponent(subject) + "&body=" + encodeURIComponent(body);
      var endpoint = form.getAttribute("data-endpoint");
      if (!endpoint) { window.location.href = mailto; setStatus("✓ Opening your email app…", "is-ok"); return; }
      setStatus("sending…");
      fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ _subject: subject, name: f.name.value.trim(), email: f.email.value.trim(), topic: topic, message: f.message.value.trim() }) })
        .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); setStatus("✓ Sent. I'll reply by email.", "is-ok"); form.reset(); })
        .catch(function () { setStatus('✗ Sending failed. <a href="' + mailto + '">Send it by email instead</a>', "is-error"); });
    });
  })();
})();

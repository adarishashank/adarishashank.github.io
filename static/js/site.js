/* Site-wide behaviour: theme, nav, relative times, email, copy, tooltip. */
(function () {
  "use strict";
  var doc = document.documentElement;

  // ---- theme: an explicit choice is stored; otherwise follow the OS
  function effectiveTheme() {
    var t = doc.getAttribute("data-theme");
    if (t) return t;
    return window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  var toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var next = effectiveTheme() === "dark" ? "light" : "dark";
      doc.setAttribute("data-theme", next);
      try { localStorage.setItem("theme", next); } catch (e) { /* private mode */ }
      document.dispatchEvent(new CustomEvent("themechange", { detail: next }));
    });
  }

  // ---- mobile nav
  var nav = document.getElementById("nav");
  var navToggle = document.getElementById("nav-toggle");
  if (nav && navToggle) {
    navToggle.addEventListener("click", function () {
      var open = nav.classList.toggle("is-open");
      navToggle.setAttribute("aria-expanded", String(open));
    });
    nav.addEventListener("click", function (e) {
      if (e.target.closest("a")) { nav.classList.remove("is-open"); navToggle.setAttribute("aria-expanded", "false"); }
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && nav.classList.contains("is-open")) { nav.classList.remove("is-open"); navToggle.setAttribute("aria-expanded", "false"); navToggle.focus(); }
    });
  }

  // ---- highlight the nav item for the section in view (home page)
  var links = {};
  document.querySelectorAll("[data-nav]").forEach(function (a) { links[a.getAttribute("data-nav")] = a; });
  if ("IntersectionObserver" in window && document.body.classList.contains("page-home")) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        var a = links[en.target.id];
        if (!a) return;
        if (en.isIntersecting) {
          Object.keys(links).forEach(function (k) { links[k].classList.remove("is-active"); });
          a.classList.add("is-active");
        }
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    Object.keys(links).forEach(function (id) { var s = document.getElementById(id); if (s) io.observe(s); });
  }

  // ---- relative times
  var UNITS = [["year", 31536000], ["month", 2592000], ["week", 604800], ["day", 86400], ["hour", 3600], ["minute", 60]];
  function rel(iso) {
    var t = Date.parse(iso);
    if (isNaN(t)) return null;
    var s = Math.round((Date.now() - t) / 1000);
    if (Math.abs(s) < 60) return "just now";
    for (var i = 0; i < UNITS.length; i++) {
      var n = Math.floor(Math.abs(s) / UNITS[i][1]);
      if (n >= 1) {
        var label = n + " " + UNITS[i][0] + (n === 1 ? "" : "s");
        return s >= 0 ? label + " ago" : "in " + label;
      }
    }
    return null;
  }
  window.relTime = rel;
  function paintRel(root) {
    (root || document).querySelectorAll("[data-reltime]").forEach(function (el) {
      var iso = el.getAttribute("datetime");
      var r = rel(iso);
      if (!r) return;
      el.textContent = r;
      el.title = new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
    });
  }
  window.paintRel = paintRel;
  paintRel();
  setInterval(paintRel, 60000);

  // ---- email: lightly obfuscated in the HTML, assembled on the client
  document.querySelectorAll("[data-email]").forEach(function (a) {
    var addr = a.getAttribute("data-email").replace(" [at] ", "@");
    a.href = "mailto:" + addr;
    a.title = addr;
  });

  // ---- copy-to-clipboard
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-copy]");
    if (!b) return;
    copyText(b.getAttribute("data-copy")).then(function () { flash(b, "copied ✓"); });
  });
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
    var ta = document.createElement("textarea");
    ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); } catch (err) { /* ignore */ }
    ta.remove();
    return Promise.resolve();
  }
  function flash(el, msg) {
    var old = el.textContent;
    el.textContent = msg;
    setTimeout(function () { el.textContent = old; }, 1400);
  }
  window.copyText = copyText;
  window.flashText = flash;

  // ---- shared tooltip (charts use it)
  var tip = document.getElementById("tip");
  window.Tip = {
    show: function (html, x, y) {
      if (!tip) return;
      tip.innerHTML = html;
      tip.hidden = false;
      var w = tip.offsetWidth, h = tip.offsetHeight, pad = 12;
      var left = Math.min(Math.max(8, x - w / 2), window.innerWidth - w - 8);
      var top = y - h - pad < 8 ? y + pad + 8 : y - h - pad;
      tip.style.left = left + "px";
      tip.style.top = top + "px";
    },
    hide: function () { if (tip) tip.hidden = true; },
  };
  window.addEventListener("scroll", function () { window.Tip.hide(); }, { passive: true });

  // ---- tiny helpers shared by page scripts
  window.esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  window.reducedMotion = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
})();

/* Blog index filters + writing heatmap; post page code highlighting, copy buttons, TOC tracking. */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  // ---------------------------------------------------------------- index
  var heat = $("#heatmap");
  var dataNode = document.getElementById("telemetry-data");
  if (heat && window.Charts && dataNode) {
    var data = JSON.parse(dataNode.textContent);
    Charts.heatmap(heat, { calendar: data.calendar, levels: data.levels, unit: heat.getAttribute("data-unit") || "post" });
  }

  var list = $("#post-list");
  if (list) {
    var state = { kind: "all", tag: null, q: "" };
    var params = new URLSearchParams(location.search);
    if (params.get("tag")) state.tag = params.get("tag").toLowerCase();

    function apply() {
      var shown = 0;
      $$(".post-row", list).forEach(function (li) {
        var ok = (state.kind === "all" || li.dataset.kind === state.kind) &&
          (!state.tag || (" " + li.dataset.tags + " ").indexOf(" " + state.tag + " ") >= 0) &&
          (!state.q || li.dataset.text.indexOf(state.q) >= 0);
        li.hidden = !ok;
        shown += ok;
      });
      $("#post-empty").hidden = shown > 0;
      $$(".seg__btn").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.kind === state.kind)); });
      $$(".tag-filter .chip").forEach(function (c) { c.setAttribute("aria-pressed", String(c.dataset.tag === state.tag)); });
    }
    document.addEventListener("click", function (e) {
      var k = e.target.closest(".seg__btn");
      if (k) { state.kind = k.dataset.kind; apply(); return; }
      var t = e.target.closest(".tag-filter .chip");
      if (t) {
        state.tag = state.tag === t.dataset.tag ? null : t.dataset.tag;
        var u = new URL(location.href);
        if (state.tag) u.searchParams.set("tag", state.tag); else u.searchParams.delete("tag");
        history.replaceState(null, "", u);
        apply();
      }
    });
    var search = $("#post-search");
    if (search) search.addEventListener("input", function () { state.q = search.value.trim().toLowerCase(); apply(); });
    apply();
  }

  // ---------------------------------------------------------------- post
  var prose = $("#prose");
  if (!prose) return;
  if (window.hljs) {
    $$("pre code", prose).forEach(function (c) {
      if (!/language-(text|plain)/.test(c.className)) window.hljs.highlightElement(c);
    });
  }
  $$("pre", prose).forEach(function (pre) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "copy-btn";
    b.textContent = "copy";
    b.addEventListener("click", function () {
      var code = pre.querySelector("code");
      window.copyText((code || pre).innerText).then(function () { window.flashText(b, "copied ✓"); });
    });
    pre.appendChild(b);
  });

  var toc = $$(".post__toc a");
  if (toc.length && "IntersectionObserver" in window) {
    var byId = {};
    toc.forEach(function (a) { byId[decodeURIComponent(a.hash.slice(1))] = a; });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting || !byId[en.target.id]) return;
        toc.forEach(function (a) { a.classList.remove("is-active"); });
        byId[en.target.id].classList.add("is-active");
      });
    }, { rootMargin: "-20% 0px -70% 0px" });
    $$("h2[id], h3[id]", prose).forEach(function (h) { io.observe(h); });
  }
})();

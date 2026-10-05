"""2D figures, rendered to inline SVG at build time.

Every colour comes from CSS classes (fn--source, fg--govern, ...), so figures follow the theme and
stay crisp at any size. Figures:
  diagram(spec)        architecture diagrams: groups, nodes with icons, curved edges with flow
  timeline(experience) career swimlanes 2017 → today
  skill_flow(...)      skill families → roles, ribbons sized by how many skills each role used
  ops_loop(...)        incident lifecycle as a ring
"""
from __future__ import annotations

import math
from html import escape

from .common import log, today_local

# ---------------------------------------------------------------- icons (24x24, stroked)
ICONS = {
    "db": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    "table": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 10v10"/>',
    "shield": '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6l-8-3z"/><path d="m9 12 2 2 4-4"/>',
    "cpu": '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9.5" y="9.5" width="5" height="5" rx="1"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "file": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7M21.5 20a6.5 6.5 0 0 0-4-6"/>',
    "chart": '<path d="M3 20h18"/><rect x="5" y="11" width="3" height="7" rx="1"/><rect x="10.5" y="6" width="3" height="12" rx="1"/><rect x="16" y="9" width="3" height="9" rx="1"/>',
    "bolt": '<path d="M13 2 4 14h7l-1 8 9-12h-7l1-8z"/>',
    "wave": '<circle cx="12" cy="12" r="2"/><path d="M8.5 8.5a5 5 0 0 0 0 7M15.5 8.5a5 5 0 0 1 0 7M5.6 5.6a9 9 0 0 0 0 12.8M18.4 5.6a9 9 0 0 1 0 12.8"/>',
    "bell": '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0"/>',
    "check": '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    "hash": '<path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18"/>',
    "layers": '<path d="m12 2 10 5-10 5L2 7l10-5z"/><path d="m2 12 10 5 10-5M2 17l10 5 10-5"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    "branch": '<circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="8" r="2"/><path d="M6 7v10M18 10c0 4-6 3-12 7"/>',
    "cloud": '<path d="M7 18a5 5 0 1 1 .9-9.9A6 6 0 0 1 19 10a4 4 0 0 1-1 8H7z"/>',
    "code": '<path d="m8 8-5 4 5 4M16 8l5 4-5 4M14 4l-4 16"/>',
    "eye": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "filter": '<path d="M3 5h18l-7 8v6l-4 2v-8L3 5z"/>',
    "flag": '<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>',
    "wrench": '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.6 2.6-2.4-.6-.6-2.4 2.6-2.6z"/>',
    "book": '<path d="M4 4h6a3 3 0 0 1 3 3v13a2 2 0 0 0-2-2H4z"/><path d="M20 4h-6a3 3 0 0 0-3 3v13a2 2 0 0 1 2-2h7z"/>',
    "lock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    "repeat": '<path d="M17 2l4 4-4 4"/><path d="M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4"/><path d="M21 13v2a3 3 0 0 1-3 3H3"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    "send": '<path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z"/>',
    "inbox": '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5h13L22 12v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6z"/>',
}


def icon(name: str, x: float, y: float, size: float = 20, cls: str = "fi") -> str:
    return (f'<svg class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'aria-hidden="true">{ICONS[name]}</svg>')


def _t(s) -> str:
    return escape(str(s), quote=True)


def _w(text: str, px: float) -> float:
    """Rough rendered width of Inter text: good enough to catch overflowing labels at build time."""
    narrow = sum(1 for c in text if c in "iljtf.,:;'|!() ")
    wide = sum(1 for c in text if c in "MWmw@%")
    return (len(text) - narrow * 0.5 + wide * 0.35) * px * 0.56


# ---------------------------------------------------------------- architecture diagrams
SIDES = {"r": (1, 0), "l": (-1, 0), "t": (0, -1), "b": (0, 1)}


def _port(n: dict, side: str, shift: float = 0):
    x, y, w, h = n["x"], n["y"], n["w"], n["h"]
    return {
        "r": (x + w, y + h / 2 + shift), "l": (x, y + h / 2 + shift),
        "t": (x + w / 2 + shift, y), "b": (x + w / 2 + shift, y + h),
    }[side]


def _edge(nodes: dict, e: dict) -> str:
    a, b = nodes[e["from"]], nodes[e["to"]]
    sa, sb = e.get("sides", "rl")
    p0 = _port(a, sa, e.get("shift_from", 0))
    p3 = _port(b, sb, e.get("shift_to", 0))
    d0, d3 = SIDES[sa], SIDES[sb]
    dist = math.hypot(p3[0] - p0[0], p3[1] - p0[1])
    k = max(24, dist * 0.42)
    end = (p3[0] + d3[0] * 7, p3[1] + d3[1] * 7)  # stop short so the arrowhead owns the tip
    c1 = (p0[0] + d0[0] * k, p0[1] + d0[1] * k)
    c2 = (end[0] + d3[0] * k, end[1] + d3[1] * k)
    d = f"M{p0[0]:.1f},{p0[1]:.1f} C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {end[0]:.1f},{end[1]:.1f}"
    nx, ny = -d3[1], d3[0]
    base = (p3[0] + d3[0] * 8, p3[1] + d3[1] * 8)
    head = (f"M{p3[0]:.1f},{p3[1]:.1f} L{base[0] + nx * 4.5:.1f},{base[1] + ny * 4.5:.1f} "
            f"L{base[0] - nx * 4.5:.1f},{base[1] - ny * 4.5:.1f} Z")
    cls = "fe" + (" fe--dash" if e.get("dash") else "")
    out = [f'<path class="{cls}" d="{d}"/>']
    if e.get("flow"):
        out.append(f'<path class="fe-flow" d="{d}"/>')
    out.append(f'<path class="fe-head{" fe-head--dash" if e.get("dash") else ""}" d="{head}"/>')
    if e.get("label"):
        mx = (p0[0] + 3 * c1[0] + 3 * c2[0] + end[0]) / 8 + e.get("label_dx", 0)
        my = (p0[1] + 3 * c1[1] + 3 * c2[1] + end[1]) / 8 + e.get("label_dy", 0)
        lw = _w(e["label"], 11) * 1.12 + 16
        out.append(f'<g class="fe-lbl"><rect x="{mx - lw / 2:.1f}" y="{my - 10:.1f}" width="{lw:.1f}" height="20" rx="10"/>'
                   f'<text x="{mx:.1f}" y="{my + 3.8:.1f}" text-anchor="middle">{_t(e["label"])}</text></g>')
    return "".join(out)


def _node(n: dict) -> str:
    x, y, w, h, kind = n["x"], n["y"], n["w"], n["h"], n.get("kind", "compute")
    tip = f' data-tip="{_t(n["tip"])}"' if n.get("tip") else ""
    if kind == "metric":
        return (f'<g class="fn fn--metric" transform="translate({x},{y})"{tip}>'
                f'<rect class="fn-box" width="{w}" height="{h}" rx="14"/>'
                f'<text class="fn-value" x="{w / 2}" y="{h / 2 - 2}" text-anchor="middle">{_t(n["label"])}</text>'
                f'<text class="fn-sub" x="{w / 2}" y="{h / 2 + 17}" text-anchor="middle">{_t(n.get("sub", ""))}</text></g>')
    has_sub = bool(n.get("sub"))
    ly = h / 2 + (-3 if has_sub else 5)
    parts = [f'<g class="fn fn--{kind}" transform="translate({x},{y})"{tip}>',
             f'<rect class="fn-box" width="{w}" height="{h}" rx="12"/>']
    tx = 16
    if n.get("icon"):
        bs = 32
        parts.append(f'<rect class="fn-badge" x="12" y="{(h - bs) / 2}" width="{bs}" height="{bs}" rx="9"/>')
        parts.append(icon(n["icon"], 12 + 6, (h - bs) / 2 + 6, 20, "fi fn-ico"))
        tx = 12 + bs + 11
    parts.append(f'<text class="fn-label" x="{tx}" y="{ly:.1f}">{_t(n["label"])}</text>')
    if has_sub:
        parts.append(f'<text class="fn-sub" x="{tx}" y="{ly + 17:.1f}">{_t(n["sub"])}</text>')
    parts.append("</g>")
    # build-time lint: labels that would spill out of their box
    room = w - tx - 10
    for text, px in ((n["label"], 14), (n.get("sub", ""), 12)):
        if text and _w(text, px) > room:
            log("WARN", f"figure node '{n['id']}': '{text}' may overflow ({_w(text, px):.0f}px > {room:.0f}px)")
    return "".join(parts)


def _group(g: dict) -> str:
    return (f'<g class="fg fg--{g.get("kind", "compute")}"><rect class="fg-box" x="{g["x"]}" y="{g["y"]}" '
            f'width="{g["w"]}" height="{g["h"]}" rx="18"/>'
            f'<text class="fg-label" x="{g["x"] + 18}" y="{g["y"] + 24}">{_t(g["label"])}</text></g>')


def diagram(spec: dict) -> str:
    nodes = {n["id"]: {"w": 200, "h": 58, **n} for n in spec["nodes"]}
    body = ["".join(_group(g) for g in spec.get("groups", [])),
            "".join(_edge(nodes, e) for e in spec.get("edges", [])),
            "".join(_node(n) for n in nodes.values())]
    for t in spec.get("texts", []):
        body.append(f'<text class="ft {t.get("cls", "")}" x="{t["x"]}" y="{t["y"]}" '
                    f'text-anchor="{t.get("anchor", "start")}">{_t(t["text"])}</text>')
    return _svg(spec["id"], spec["w"], spec["h"], spec["title"], spec["desc"], "".join(body))


def _svg(fid: str, w: float, h: float, title: str, desc: str, body: str, cls: str = "") -> str:
    return (f'<svg class="figsvg {cls}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="{fid}-t {fid}-d" '
            f'data-fig="{fid}" style="--fig-minw:{max(640, int(w * 0.7))}px">'
            f'<title id="{fid}-t">{_t(title)}</title><desc id="{fid}-d">{_t(desc)}</desc>{body}</svg>')


# ---------------------------------------------------------------- career timeline
STAGE_KIND = {"bronze": "bronze", "silver": "silver", "gold": "gold", "serving": "serving"}


def _ym(s: str | None) -> float:
    if not s:
        t = today_local()
        return t.year + (t.month - 1 + t.day / 31) / 12
    y, m = map(int, s.split("-")[:2])
    return y + (m - 1) / 12


def timeline(experience: list[dict]) -> str:
    y0, y1 = 2017, today_local().year + 1
    W, left, right = 1100, 150, 24
    lanes = [("education", "Education"), ("award", "Recognition"), ("cert", "Certification"),
             ("Accenture", "Accenture"), ("Cliff Systems LLP", "Cliff Systems")]
    lane_h, top = 52, 40
    H = top + lane_h * len(lanes) + 30
    sx = lambda v: left + (v - y0) / (y1 - y0) * (W - left - right)  # noqa: E731

    out = []
    for i, (_, label) in enumerate(lanes):
        y = top + i * lane_h
        out.append(f'<rect class="tl-lane{" tl-lane--alt" if i % 2 else ""}" x="0" y="{y}" width="{W}" height="{lane_h}" rx="0"/>')
        out.append(f'<text class="tl-lane-label" x="16" y="{y + lane_h / 2 + 4}">{_t(label)}</text>')
    for yr in range(y0, y1 + 1):
        x = sx(yr)
        out.append(f'<line class="tl-grid" x1="{x:.1f}" x2="{x:.1f}" y1="{top - 8}" y2="{top + lane_h * len(lanes)}"/>')
        out.append(f'<text class="tl-year" x="{x:.1f}" y="{top - 14}" text-anchor="middle">{yr}</text>')

    lane_of = {}
    for e in experience:
        lane_of[e["id"]] = next(i for i, (k, _) in enumerate(lanes) if k in (e["kind"], e["org"]))
    for e in experience:
        i = lane_of[e["id"]]
        y = top + i * lane_h
        a, b = _ym(e["start"]), _ym(e["end"]) if e["end"] else _ym(None)
        if e["kind"] == "job":
            b = _ym(e["end"]) + 1 / 12 if e["end"] else b
        x0, x1 = sx(a), max(sx(b), sx(a) + 10)
        kind = STAGE_KIND.get(e["stage"], e["kind"]) if e["kind"] == "job" else e["kind"]
        tip = f'{e["label"]} · {e.get("client") or e["org"]} · {e["period"]}'
        href = f'data-href="{e["id"]}"' if e.get("case") else ""
        if e["kind"] == "award":
            cx, cy = (x0 + x1) / 2, y + lane_h / 2
            out.append(f'<g class="tl-item tl--award" data-tip="{_t(tip)}"><path class="tl-bar" d="M{cx},{cy - 11} L{cx + 11},{cy} L{cx},{cy + 11} L{cx - 11},{cy} Z"/>'
                       f'<text class="tl-out" x="{cx + 18}" y="{cy + 4}">{_t(e["short"])}</text></g>')
            continue
        running = e["status"] == "RUNNING"
        bar_h = 26
        by = y + (lane_h - bar_h) / 2
        out.append(f'<g class="tl-item tl--{kind}{" is-running" if running else ""}" data-tip="{_t(tip)}" {href}>'
                   f'<rect class="tl-bar" x="{x0:.1f}" y="{by:.1f}" width="{x1 - x0:.1f}" height="{bar_h}" rx="7"/>')
        text, tw = e["short"], _w(e["short"], 12) * 1.05
        if tw + 16 < x1 - x0:
            out.append(f'<text class="tl-in" x="{x0 + 9:.1f}" y="{by + 17:.1f}">{_t(text)}</text>')
        else:
            out.append(f'<text class="tl-out" x="{x0 - 8:.1f}" y="{by + 17:.1f}" text-anchor="end">{_t(text)}</text>')
        out.append("</g>")

    nx = sx(_ym(None))
    out.append(f'<line class="tl-now" x1="{nx:.1f}" x2="{nx:.1f}" y1="{top - 6}" y2="{top + lane_h * len(lanes) + 6}"/>'
               f'<text class="tl-now-label" x="{nx:.1f}" y="{top + lane_h * len(lanes) + 20}" text-anchor="middle">today</text>')
    return _svg("fig-timeline", W, H, "Career timeline",
                "Education, recognition, certification and roles from 2017 to today, as swimlanes.", "".join(out), "figsvg--timeline")


# ---------------------------------------------------------------- skill families → roles
def skill_flow(profile: dict, experience: list[dict]) -> str:
    jobs = [e for e in sorted(experience, key=lambda e: e["start"], reverse=True) if e["kind"] == "job"]
    fams = [(k, s["label"], set(s["items"])) for k, s in profile["skills"].items()]
    links = []
    for fi, (k, _, items) in enumerate(fams):
        for ji, j in enumerate(jobs):
            v = len(items & set(j["stack"]))
            if v:
                links.append({"f": fi, "j": ji, "v": v})
    if not links:
        return ""
    W, H, top, bottom = 1000, 470, 16, 16
    lx, rx, bw = 230, 720, 14
    pad_l, pad_r = 10, 26
    total = sum(l["v"] for l in links)
    fam_tot = [sum(l["v"] for l in links if l["f"] == i) for i in range(len(fams))]
    job_tot = [sum(l["v"] for l in links if l["j"] == i) for i in range(len(jobs))]
    used_f = [i for i, t in enumerate(fam_tot) if t]
    scale = min((H - top - bottom - pad_l * (len(used_f) - 1)) / total,
                (H - top - bottom - pad_r * (len(jobs) - 1)) / total)
    # vertically centre both columns
    fh = total * scale + pad_l * (len(used_f) - 1)
    jh = total * scale + pad_r * (len(jobs) - 1)
    fy, y = {}, top + (H - top - bottom - fh) / 2
    for i in used_f:
        fy[i] = y
        y += fam_tot[i] * scale + pad_l
    jy, y = {}, top + (H - top - bottom - jh) / 2
    for i in range(len(jobs)):
        jy[i] = y
        y += job_tot[i] * scale + pad_r

    out = ['<g class="sk-ribbons">']
    f_off = {i: 0.0 for i in used_f}
    j_off = {i: 0.0 for i in range(len(jobs))}
    for l in sorted(links, key=lambda l: (l["f"], l["j"])):
        t = l["v"] * scale
        ya0 = fy[l["f"]] + f_off[l["f"]]
        yb0 = jy[l["j"]] + j_off[l["j"]]
        f_off[l["f"]] += t
        j_off[l["j"]] += t
        x0, x1, xm = lx + bw, rx, (lx + bw + rx) / 2
        d = (f"M{x0},{ya0:.1f} C{xm},{ya0:.1f} {xm},{yb0:.1f} {x1},{yb0:.1f} L{x1},{yb0 + t:.1f} "
             f"C{xm},{yb0 + t:.1f} {xm},{ya0 + t:.1f} {x0},{ya0 + t:.1f} Z")
        tip = f'{fams[l["f"]][1]} → {jobs[l["j"]]["label"]}: {l["v"]} skill{"s" if l["v"] != 1 else ""}'
        out.append(f'<path class="sk-ribbon sk-c{l["f"]}" data-f="{l["f"]}" data-j="{l["j"]}" d="{d}" data-tip="{_t(tip)}"/>')
    out.append("</g>")
    for i in used_f:
        h = fam_tot[i] * scale
        out.append(f'<g class="sk-node" data-f="{i}"><rect class="sk-bar sk-c{i}" x="{lx}" y="{fy[i]:.1f}" width="{bw}" height="{h:.1f}" rx="3"/>'
                   f'<text class="sk-label" x="{lx - 12}" y="{fy[i] + h / 2 + 4:.1f}" text-anchor="end">{_t(fams[i][1])}'
                   f'<tspan class="sk-count" dx="8">{fam_tot[i]}</tspan></text></g>')
    for i, j in enumerate(jobs):
        h = job_tot[i] * scale
        out.append(f'<g class="sk-node sk-role" data-j="{i}"><rect class="sk-bar sk-r-{j["stage"]}" x="{rx}" y="{jy[i]:.1f}" width="{bw}" height="{h:.1f}" rx="3"/>'
                   f'<text class="sk-label" x="{rx + bw + 12}" y="{jy[i] + h / 2 - 3:.1f}">{_t(j["label"])}</text>'
                   f'<text class="sk-sub" x="{rx + bw + 12}" y="{jy[i] + h / 2 + 14:.1f}">{_t(j.get("client") or j["org"])} · {job_tot[i]} skills</text></g>')
    return _svg("fig-skillflow", W, H, "Skill families mapped to roles",
                "Ribbons connect each skill family to the roles that used it; thickness is the number of skills.",
                "".join(out), "figsvg--flow")


# ---------------------------------------------------------------- incident loop
def ops_loop(stages: list[tuple[str, str, str]], center_value: str, center_label: str) -> str:
    W, H = 1000, 464
    cx, cy, rx, ry = W / 2, 236, 330, 162
    out = [f'<ellipse class="ol-ring" cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}"/>',
           f'<ellipse class="ol-ring-flow" cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}"/>']
    n = len(stages)
    for i in range(n):  # arrowheads midway between stages, pointing clockwise along the ellipse
        t = math.radians(-90 + (i + 0.5) * 360 / n)
        px, py = cx + rx * math.cos(t), cy + ry * math.sin(t)
        tx, ty = -rx * math.sin(t), ry * math.cos(t)
        norm = math.hypot(tx, ty)
        tx, ty = tx / norm, ty / norm
        nx, ny = -ty, tx
        out.append(f'<path class="ol-head" d="M{px + tx * 8:.1f},{py + ty * 8:.1f} L{px - tx * 5 + nx * 6:.1f},{py - ty * 5 + ny * 6:.1f} '
                   f'L{px - tx * 5 - nx * 6:.1f},{py - ty * 5 - ny * 6:.1f} Z"/>')
    nw, nh = 200, 60
    for i, (label, sub, ic) in enumerate(stages):
        t = math.radians(-90 + i * 360 / n)
        x, y = cx + rx * math.cos(t) - nw / 2, cy + ry * math.sin(t) - nh / 2
        out.append(_node({"id": f"ol{i}", "x": round(x, 1), "y": round(y, 1), "w": nw, "h": nh,
                          "kind": ["source", "ingest", "compute", "govern", "quality"][i % 5],
                          "label": label, "sub": sub, "icon": ic}))
    out.append(f'<text class="ol-value" x="{cx}" y="{cy + 10}" text-anchor="middle">{_t(center_value)}</text>'
               f'<text class="ol-label" x="{cx}" y="{cy + 36}" text-anchor="middle">{_t(center_label)}</text>')
    return _svg("fig-opsloop", W, H, "Incident lifecycle", "Detect, triage, resolve within SLA, record root cause, prevent recurrence.", "".join(out))

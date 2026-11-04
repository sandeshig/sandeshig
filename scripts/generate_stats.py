#!/usr/bin/env python3
"""
Builds the burgundy stat cards in assets/generated/ from public GitHub data.

Data sources (nothing is estimated or invented):
  * https://github.com/users/<user>/contributions   -> public contribution calendar
  * https://api.github.com/users/<user>[/repos]      -> repo / star / follower counts
  * https://api.github.com/repos/<user>/<repo>/languages -> bytes per language

Standard library only. If a data source fails, the existing card is left untouched.
"""
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.request

USER = os.environ.get("PROFILE_USER", "sandeshig")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "generated")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

BURG, WINE, ROSE, PINK, BLUSH, DEEP = "#8F3D56", "#A64D65", "#C7798D", "#E6A6B4", "#FFF5F6", "#351522"
SERIF = "Georgia, 'Times New Roman', serif"
MONO = "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace"
SANS = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
LEVELS = ["#4A2233", "#6E2F44", WINE, ROSE, PINK]  # contribution intensity, low -> high
TODAY = dt.datetime.now(dt.timezone.utc).date()


def get(url, accept=None):
    headers = {"User-Agent": "profile-readme-stats"}
    if accept:
        headers["Accept"] = accept
    if TOKEN and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {TOKEN}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
        return r.read().decode("utf-8")


def api(path):
    return json.loads(get("https://api.github.com" + path, "application/vnd.github+json"))


def esc(s):
    return html.escape(str(s), quote=True)


def card(w, h, title, body, note=""):
    stamp = f"public data · updated {TODAY.isoformat()}" if note == "" else note
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{esc(title)}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{DEEP}"/><stop offset="1" stop-color="#4B1F32"/></linearGradient>
    <linearGradient id="bar" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{WINE}"/><stop offset="1" stop-color="{PINK}"/></linearGradient>
  </defs>
  <rect x="0.75" y="0.75" width="{w-1.5}" height="{h-1.5}" rx="16" fill="url(#bg)" stroke="{ROSE}" stroke-opacity="0.5" stroke-width="1.5"/>
  <text x="32" y="46" font-family="{SERIF}" font-size="24" fill="{BLUSH}">{esc(title)}</text>
  <rect x="32" y="58" width="44" height="2.5" rx="1.25" fill="url(#bar)"/>
  {body}
  <text x="{w-32}" y="{h-14}" text-anchor="end" font-family="{MONO}" font-size="12" fill="{ROSE}">{esc(stamp)}</text>
</svg>
"""


def save(name, svg):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(svg)
    print("wrote", name)


def placeholder(name, title, w=800, h=200):
    path = os.path.join(OUT, name)
    if os.path.exists(path):
        return
    body = (f'<text x="32" y="115" font-family="{SANS}" font-size="18" fill="{PINK}">Waiting for the first run of the '
            f'"Update profile stats" workflow.</text>')
    save(name, card(w, h, title, body, "no data yet"))


# ----------------------------------------------------------------- contribution calendar
def calendar():
    page = get(f"https://github.com/users/{USER}/contributions")
    cells = re.findall(r'<td[^>]*data-date="(\d{4}-\d{2}-\d{2})"[^>]*id="(contribution-day-component-\d+-\d+)"[^>]*data-level="(\d)"', page)
    counts = {}
    for m in re.finditer(r'for="(contribution-day-component-\d+-\d+)"[^>]*>\s*(No|\d[\d,]*) contributions?', page):
        counts[m.group(1)] = 0 if m.group(2) == "No" else int(m.group(2).replace(",", ""))
    days = []
    for date, cid, level in cells:
        d = dt.date.fromisoformat(date)
        if d <= TODAY:
            days.append((d, counts.get(cid, 0), int(level)))
    if not days:
        raise RuntimeError("no calendar cells parsed")
    days.sort()
    return days


def streaks(days):
    by_date = {d: c for d, c, _ in days}
    longest = run = 0
    prev = None
    for d, c, _ in days:
        run = run + 1 if c > 0 and prev is not None and (d - prev).days == 1 and by_date.get(prev, 0) > 0 else (1 if c > 0 else 0)
        longest = max(longest, run)
        prev = d
    cur = 0
    d = TODAY if by_date.get(TODAY, 0) > 0 else TODAY - dt.timedelta(days=1)
    while by_date.get(d, 0) > 0:
        cur += 1
        d -= dt.timedelta(days=1)
    return cur, longest


def streak_card(days):
    total = sum(c for _, c, _ in days)
    cur, longest = streaks(days)
    cols = [(cur, "current streak", "days in a row"), (longest, "longest streak", "within the past year"),
            (total, "contributions", "in the past year")]
    body = ""
    for i, (n, label, sub) in enumerate(cols):
        x = 32 + i * 252
        if i:
            body += f'<line x1="{x-24}" y1="88" x2="{x-24}" y2="152" stroke="{ROSE}" stroke-opacity="0.35"/>'
        body += (f'<text x="{x}" y="124" font-family="{SERIF}" font-size="52" fill="{BLUSH}">{n:,}</text>'
                 f'<text x="{x}" y="148" font-family="{SANS}" font-size="16" font-weight="600" fill="{PINK}">{label}</text>'
                 f'<text x="{x}" y="167" font-family="{MONO}" font-size="12" fill="{ROSE}">{sub}</text>')
    save("streak.svg", card(800, 224, "Contribution streak", body))


def activity_card(days):
    cell, gap, x0, y0 = 10, 3, 60, 96
    first = days[0][0]
    offset = (first.weekday() + 1) % 7  # Sunday-first rows
    body, last_label_x, seen_month = "", -100, None
    ncols = (len(days) + offset - 1) // 7 + 1
    for i, (d, c, lvl) in enumerate(days):
        idx = i + offset
        col, row = idx // 7, idx % 7
        x, y = x0 + col * (cell + gap), y0 + row * (cell + gap)
        body += (f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2.5" fill="{LEVELS[lvl]}">'
                 f'<title>{c} contribution{"s" if c != 1 else ""} on {d.isoformat()}</title></rect>')
        if d.month != seen_month:
            seen_month = d.month
            if x - last_label_x >= 44 and x + 30 <= x0 + ncols * (cell + gap):
                body += f'<text x="{x}" y="{y0-10}" font-family="{MONO}" font-size="12" fill="{ROSE}">{d.strftime("%b")}</text>'
                last_label_x = x
    for r, lab in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        body += f'<text x="32" y="{y0 + r*(cell+gap) + 9}" font-family="{MONO}" font-size="11" fill="{ROSE}">{lab}</text>'
    ly = y0 + 7 * (cell + gap) + 14
    lx = x0
    body += f'<text x="{lx}" y="{ly+9}" font-family="{MONO}" font-size="12" fill="{ROSE}">less</text>'
    for i, colr in enumerate(LEVELS):
        body += f'<rect x="{lx+36+i*(cell+gap)}" y="{ly}" width="{cell}" height="{cell}" rx="2.5" fill="{colr}"/>'
    body += f'<text x="{lx+36+5*(cell+gap)+4}" y="{ly+9}" font-family="{MONO}" font-size="12" fill="{ROSE}">more</text>'
    save("activity.svg", card(800, 258, "Contribution activity", body))


# ----------------------------------------------------------------- repo stats + languages
def stats_cards():
    user = api(f"/users/{USER}")
    repos = api(f"/users/{USER}/repos?per_page=100&type=owner")
    stars = sum(r["stargazers_count"] for r in repos)
    metrics = [(user["public_repos"], "public repositories"), (stars, "stars received"),
               (user["followers"], "followers"), (user["following"], "following")]
    body = ""
    for i, (n, label) in enumerate(metrics):
        x = 32 + i * 190
        body += (f'<text x="{x}" y="128" font-family="{SERIF}" font-size="46" fill="{BLUSH}">{n:,}</text>'
                 f'<text x="{x}" y="154" font-family="{SANS}" font-size="15" fill="{PINK}">{label}</text>')
    save("stats.svg", card(800, 200, "GitHub at a glance", body))

    totals = {}
    for r in repos:
        if r["fork"]:
            continue
        for lang, b in api(f"/repos/{USER}/{r['name']}/languages").items():
            totals[lang] = totals.get(lang, 0) + b
    langs_card(totals)


def langs_card(totals):
    top = sorted(totals.items(), key=lambda kv: -kv[1])[:5]
    shades = [BURG, WINE, ROSE, PINK, "#F3CAD3"]
    if not top:
        body = f'<text x="32" y="120" font-family="{SANS}" font-size="18" fill="{PINK}">No language data detected in public repositories yet.</text>'
        save("languages.svg", card(800, 200, "Most-used languages", body))
        return
    total = sum(b for _, b in top)
    all_total = sum(totals.values())
    body, x = f'<clipPath id="r"><rect x="32" y="82" width="736" height="14" rx="7"/></clipPath><g clip-path="url(#r)">', 32
    bar_w = 736
    for (lang, b), colr in zip(top, shades):
        w = max(4, bar_w * b / total)
        body += f'<rect x="{x:.1f}" y="82" width="{w:.1f}" height="14" fill="{colr}"/>'
        x += w
    body += '</g>'
    body += f'<rect x="32" y="82" width="{bar_w}" height="14" rx="7" fill="none" stroke="{ROSE}" stroke-opacity="0.35"/>'
    for i, ((lang, b), colr) in enumerate(zip(top, shades)):
        lx = 32 + (i % 3) * 250
        ly = 134 + (i // 3) * 30
        body += (f'<circle cx="{lx+6}" cy="{ly-5}" r="6" fill="{colr}"/>'
                 f'<text x="{lx+20}" y="{ly}" font-family="{SANS}" font-size="16" fill="{BLUSH}">{esc(lang)} '
                 f'<tspan fill="{PINK}">{100*b/all_total:.1f}%</tspan></text>')
    save("languages.svg", card(800, 216, "Most-used languages", body, f"by code size, public non-fork repos · updated {TODAY.isoformat()}"))


def main():
    ok = True
    try:
        days = calendar()
        streak_card(days)
        activity_card(days)
    except Exception as e:  # keep previous cards if GitHub markup changes
        ok = False
        print("calendar failed:", e, file=sys.stderr)
    try:
        stats_cards()
    except Exception as e:
        ok = False
        print("api stats failed:", e, file=sys.stderr)
    placeholder("stats.svg", "GitHub at a glance")
    placeholder("languages.svg", "Most-used languages")
    placeholder("streak.svg", "Contribution streak")
    placeholder("activity.svg", "Contribution activity", 800, 258)
    return 0 if ok else 0


if __name__ == "__main__":
    sys.exit(main())

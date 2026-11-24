"""Generates stats.svg and languages.svg (private repos/contributions included).

Env: GH_TOKEN (classic PAT with repo + read:user). Run with --demo to render sample data.
"""
import json, os, sys, urllib.request
from datetime import datetime, timezone
from html import escape

BG, BORDER, TEXT, MUTED, ACCENT, ACCENT2 = "#1a1b27", "#2b2d42", "#e6e6f0", "#9aa0b4", "#8b5cf6", "#38bdf8"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"


def gql(query, variables=None):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": f"bearer {os.environ['GH_TOKEN']}", "User-Agent": "profile-cards"},
    )
    with urllib.request.urlopen(req) as r:
        out = json.load(r)
    if "errors" in out:
        raise SystemExit(json.dumps(out["errors"]))
    return out["data"]


def fetch():
    v = gql("{ viewer { login name createdAt } }")["viewer"]
    created = datetime.fromisoformat(v["createdAt"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)

    years, commits, prs = {}, 0, 0
    for y in range(created.year, now.year + 1):
        c = gql(
            """query($from: DateTime!, $to: DateTime!) { viewer { contributionsCollection(from: $from, to: $to) {
                 contributionCalendar { totalContributions } totalCommitContributions totalPullRequestContributions } } }""",
            {"from": f"{y}-01-01T00:00:00Z", "to": f"{y}-12-31T23:59:59Z"},
        )["viewer"]["contributionsCollection"]
        years[y] = c["contributionCalendar"]["totalContributions"]
        commits += c["totalCommitContributions"]
        prs += c["totalPullRequestContributions"]

    repos, cursor = [], None
    while True:
        page = gql(
            """query($after: String) { viewer { repositories(first: 100, after: $after, ownerAffiliations: OWNER, isFork: false) {
                 pageInfo { hasNextPage endCursor }
                 nodes { isPrivate stargazerCount
                   languages(first: 20, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name color } } } } } } }""",
            {"after": cursor},
        )["viewer"]["repositories"]
        repos += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    langs = {}
    for r in repos:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            langs.setdefault(n, [0, e["node"]["color"] or MUTED])[0] += e["size"]

    return {
        "years": years,
        "commits": commits,
        "prs": prs,
        "repos": len(repos),
        "private": sum(r["isPrivate"] for r in repos),
        "stars": sum(r["stargazerCount"] for r in repos),
        "since": created.year,
        "langs": langs,
    }


def fmt(n):
    return f"{n:,}"


def frame(w, h, title, subtitle, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">
<style>
  text {{ font-family: {FONT}; }}
  .t {{ fill: {TEXT}; font-size: 18px; font-weight: 700; }}
  .s {{ fill: {MUTED}; font-size: 12px; }}
  .v {{ fill: {TEXT}; font-size: 26px; font-weight: 700; }}
  .l {{ fill: {MUTED}; font-size: 12px; letter-spacing: .3px; }}
  .x {{ fill: {MUTED}; font-size: 11px; }}
</style>
<defs>
  <linearGradient id="acc" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{ACCENT}"/><stop offset="1" stop-color="{ACCENT2}"/></linearGradient>
  <linearGradient id="bar" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="{ACCENT}"/><stop offset="1" stop-color="{ACCENT2}"/></linearGradient>
</defs>
<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="14" fill="{BG}" stroke="{BORDER}"/>
<rect x="28" y="56" width="44" height="3" rx="1.5" fill="url(#acc)"/>
<text x="28" y="42" class="t">{escape(title)}</text>
<text x="{w-28}" y="42" class="s" text-anchor="end">{escape(subtitle)}</text>
{body}
</svg>
"""


def stats_svg(d):
    year = max(d["years"])
    tiles = [
        (fmt(sum(d["years"].values())), "Total contributions"),
        (fmt(d["years"][year]), f"Contributions in {year}"),
        (fmt(d["commits"]), "Commits"),
        (fmt(d["repos"]), f"Repositories · {d['private']} private"),
        (fmt(d["prs"]), "Pull requests"),
        (fmt(d["stars"]), "Stars earned"),
    ]
    body, x0, y0, cw, rh = [], 28, 84, 150, 74
    for i, (val, label) in enumerate(tiles):
        x, y = x0 + (i % 3) * cw, y0 + (i // 3) * rh
        body.append(
            f'<g class="f" style="animation-delay:{i*80}ms"><text x="{x}" y="{y+28}" class="v">{val}</text>'
            f'<text x="{x}" y="{y+48}" class="l">{escape(label)}</text></g>'
        )

    # yearly contribution bars
    cx, cy, cw2, ch = 500, 84, 272, 118
    body.append(f'<text x="{cx}" y="{cy-6}" class="l">Contributions per year</text>')
    ys = sorted(d["years"])
    peak = max(d["years"].values()) or 1
    slot = cw2 / len(ys)
    bw = min(26, slot * 0.6)
    base = cy + ch - 4
    for i, y in enumerate(ys):
        v = d["years"][y]
        bh = max(2, (ch - 34) * v / peak)
        bx = cx + i * slot + (slot - bw) / 2
        body.append(
            f'<g class="f" style="animation-delay:{300+i*60}ms">'
            f'<rect x="{bx:.1f}" y="{base-bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="3" fill="url(#bar)"/>'
            f'<text x="{bx+bw/2:.1f}" y="{base-bh-5:.1f}" class="x" text-anchor="middle">{fmt(v)}</text>'
            f'<text x="{bx+bw/2:.1f}" y="{base+15:.1f}" class="x" text-anchor="middle">’{str(y)[2:]}</text></g>'
        )
    return frame(800, 232, "GitHub Stats", "Public + private · updated daily", "\n".join(body))


def langs_svg(d, top=8):
    items = sorted(d["langs"].items(), key=lambda kv: -kv[1][0])
    total = sum(v[0] for _, v in items) or 1
    shown = items[:top]
    other = total - sum(v[0] for _, v in shown)
    body, x, bx, bwid = [], 28, 28, 744
    # stacked bar
    body.append(f'<clipPath id="clip"><rect x="{bx}" y="80" width="{bwid}" height="10" rx="5"/></clipPath><g clip-path="url(#clip)">')
    segs = shown + ([("Other", [other, "#4b5063"])] if other > 0 else [])
    for name, (size, color) in segs:
        w = bwid * size / total
        body.append(f'<rect x="{x:.1f}" y="80" width="{w+0.5:.1f}" height="10" fill="{color}"/>')
        x += w
    body.append("</g>")
    # legend: 4 columns x 2 rows
    for i, (name, (size, color)) in enumerate(shown):
        lx, ly = 28 + (i % 4) * 186, 122 + (i // 4) * 30
        body.append(
            f'<g class="f" style="animation-delay:{i*60}ms"><circle cx="{lx+5}" cy="{ly-4}" r="5" fill="{color}"/>'
            f'<text x="{lx+18}" y="{ly}" style="fill:{TEXT};font-size:13px;font-weight:600">{escape(name)}</text>'
            f'<text x="{lx+168}" y="{ly}" class="s" text-anchor="end">{100*size/total:.1f}%</text></g>'
        )
    h = 122 + ((len(shown) - 1) // 4) * 30 + 28
    return frame(800, h, "Most Used Languages", f"Across {d['repos']} repositories · by code size", "\n".join(body))


def main():
    if "--demo" in sys.argv:
        d = {"years": {2019: 4, 2020: 87, 2021: 119, 2022: 106, 2023: 96, 2024: 4, 2025: 6, 2026: 592},
             "commits": 738, "prs": 12, "repos": 61, "private": 29, "stars": 41, "since": 2019,
             "langs": {"C#": [900, "#178600"], "TypeScript": [300, "#3178c6"], "JavaScript": [250, "#f1e05a"],
                       "SQL": [80, "#e38c00"], "HTML": [60, "#e34c26"], "CSS": [40, "#563d7c"], "PHP": [30, "#4F5D95"],
                       "Shell": [20, "#89e051"], "Dockerfile": [5, "#384d54"]}}
    else:
        d = fetch()
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "."
    open(os.path.join(out, "stats.svg"), "w", encoding="utf-8").write(stats_svg(d))
    open(os.path.join(out, "languages.svg"), "w", encoding="utf-8").write(langs_svg(d))


if __name__ == "__main__":
    main()

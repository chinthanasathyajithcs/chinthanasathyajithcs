"""Render a contribution streak card as SVG from GitHub's GraphQL API.

Usage: GH_TOKEN=... python3 scripts/streak.py <login> <output.svg>
"""
import datetime as dt
import json
import os
import sys
import urllib.request

API_URL = "https://api.github.com/graphql"
COLORS = {
    "bg": "#0D1117",
    "ring": "#00D9FF",
    "label": "#00D9FF",
    "side_label": "#c9d1d9",
    "num": "#c9d1d9",
    "dates": "#6b7280",
}

YEARS_QUERY = "query($l:String!){user(login:$l){contributionsCollection{contributionYears}}}"
CALENDAR_QUERY = """query($l:String!,$from:DateTime!,$to:DateTime!){
  user(login:$l){contributionsCollection(from:$from,to:$to){
    contributionCalendar{weeks{contributionDays{date contributionCount}}}
  }}}"""


def graphql(query, variables, token):
    request = urllib.request.Request(
        API_URL,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    return payload["data"]["user"]


def contribution_counts(login, token):
    """Map ISO date -> contribution count across every year of the account."""
    years = graphql(YEARS_QUERY, {"l": login}, token)["contributionsCollection"]["contributionYears"]
    counts = {}
    for year in years:
        user = graphql(
            CALENDAR_QUERY,
            {"l": login, "from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"},
            token,
        )
        for week in user["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                counts[day["date"]] = day["contributionCount"]
    return counts


def streaks(counts, today):
    """Return (total, current, current_range, longest, longest_range)."""
    days = sorted(dt.date.fromisoformat(d) for d, n in counts.items() if n > 0 and dt.date.fromisoformat(d) <= today)
    total = sum(counts[d.isoformat()] for d in days)
    best = (0, None, None)
    run_start = previous = None
    run_len = 0
    for day in days:
        if previous is not None and (day - previous).days == 1:
            run_len += 1
        else:
            run_start, run_len = day, 1
        if run_len > best[0]:
            best = (run_len, run_start, day)
        previous = day
    current = (0, None, None)
    if previous is not None and (today - previous).days <= 1 and run_len:
        current = (run_len, run_start, previous)
    return total, current, best


def fmt_range(start, end):
    if start is None:
        return "-"
    fmt = lambda d: f"{d:%b} {d.day}"
    return fmt(start) if start == end else f"{fmt(start)} - {fmt(end)}"


def render(total, current, longest, since):
    c = COLORS
    column = lambda x, num, label, sub, accent: (
        f'<text x="{x}" y="62" text-anchor="middle" font-size="28" font-weight="700" fill="{accent}">{num}</text>'
        f'<text x="{x}" y="96" text-anchor="middle" font-size="14" fill="{accent if accent == c["label"] else c["side_label"]}">{label}</text>'
        f'<text x="{x}" y="118" text-anchor="middle" font-size="12" fill="{c["dates"]}">{sub}</text>'
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="495" height="195" viewBox="0 0 495 195" role="img" aria-label="Contribution streak">
<style>text{{font-family:'Segoe UI',Ubuntu,sans-serif}}</style>
<rect width="495" height="195" rx="4.5" fill="{c['bg']}"/>
{column(82, total, 'Total Contributions', f'{since:%b} {since.day}, {since.year} - Present', c['num'])}
<circle cx="247.5" cy="70" r="40" fill="none" stroke="{c['ring']}" stroke-width="5"/>
<ellipse cx="247.5" cy="30" rx="17" ry="15" fill="{c['bg']}"/>
<path d="M247.5 15 C252 22 258.5 26 258.5 34 A11 11 0 0 1 236.5 34 C236.5 29 239.5 26.5 241.5 22.5 C242.5 25.5 244.5 27 246 27 C245 23 245.5 18.5 247.5 15 Z" fill="{c['ring']}"/>
<text x="247.5" y="80" text-anchor="middle" font-size="28" font-weight="700" fill="{c['num']}">{current[0]}</text>
<text x="247.5" y="140" text-anchor="middle" font-size="14" font-weight="700" fill="{c['label']}">Current Streak</text>
<text x="247.5" y="162" text-anchor="middle" font-size="12" fill="{c['dates']}">{fmt_range(current[1], current[2])}</text>
{column(413, longest[0], 'Longest Streak', fmt_range(longest[1], longest[2]), c['num'])}
</svg>
"""


def main(login, output):
    token = os.environ["GH_TOKEN"]
    counts = contribution_counts(login, token)
    if not counts:
        raise RuntimeError(f"no contribution data returned for {login}")
    today = dt.datetime.now(dt.timezone.utc).date()
    total, current, longest = streaks(counts, today)
    since = min(dt.date.fromisoformat(d) for d in counts)
    with open(output, "w", encoding="utf-8") as handle:
        handle.write(render(total, current, longest, since))
    print(f"total={total} current={current[0]} longest={longest[0]}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])

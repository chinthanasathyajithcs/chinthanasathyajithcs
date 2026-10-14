"""Render a neofetch-style profile card (ASCII portrait + info) as SVG.

Usage: GH_TOKEN=... python3 scripts/neofetch.py <login> <output.svg>
Needs Pillow for the ASCII portrait.
"""
import datetime as dt
import os
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image

from streak import contribution_counts, graphql, streaks

PORTRAIT = Path(__file__).parent / "assets" / "portrait.png"

COLORS = {
    "bg": "#161b22",
    "key": "#ffa657",
    "value": "#a5d6ff",
    "title": "#c9d1d9",
    "rule": "#6e7681",
    "dots": "#484f58",
    "art": "#c9d1d9",
}

ART_COLUMNS = 72
ART_ROWS = 36
ART_RAMP = " .:-=+*#%@"
BACKDROP_ALPHA = 128
ART_FONT_SIZE = 8
ART_CHAR_WIDTH = 4.8
ART_LINE_HEIGHT = 9.6
LINE_HEIGHT = 16
INFO_FONT_SIZE = 12
INFO_CHAR_WIDTH = 7.2
INFO_WIDTH_CHARS = 58
PADDING = 24
GAP = 30

PROFILE = (
    ("Focus", "Full-Stack + AI Integration"),
    ("Languages", "Python, TypeScript, Java, C#"),
    ("Stack.Web", "React, Next.js, Flutter, Tailwind CSS"),
    ("Stack.Server", "Node.js, Express, Spring Boot, Socket.io"),
    ("Stack.Data", "MongoDB, Firebase"),
    ("Stack.Cloud", "AWS, GCP, Docker"),
)
CONTACT = (
    ("Email", "chinthanasathyajith.dev@gmail.com"),
    ("LinkedIn", "chinthana-sathyajith"),
)

STATS_QUERY = "query($l:String!){user(login:$l){repositories(ownerAffiliations:OWNER,privacy:PUBLIC){totalCount} followers{totalCount}}}"


def portrait_art():
    """Return the portrait as ASCII rows: transparent backdrop blank, darker tones denser."""
    tones, alpha = Image.open(PORTRAIT).convert("LA").split()
    size = (ART_COLUMNS, ART_ROWS)
    tones, alpha = tones.resize(size, Image.BOX), alpha.resize(size, Image.BOX)
    last = len(ART_RAMP) - 1

    def cell(x, y):
        if alpha.getpixel((x, y)) < BACKDROP_ALPHA:
            return " "
        return ART_RAMP[max(1, (255 - tones.getpixel((x, y))) * last // 255)]

    return ["".join(cell(x, y) for x in range(ART_COLUMNS)) for y in range(ART_ROWS)]


def fetch_stats(login, token):
    user = graphql(STATS_QUERY, {"l": login}, token)
    counts = contribution_counts(login, token)
    total, _, _ = streaks(counts, dt.datetime.now(dt.timezone.utc).date())
    return (
        ("Repos", f"{user['repositories']['totalCount']} public"),
        ("Followers", str(user["followers"]["totalCount"])),
        ("Contributions", f"{total:,}"),
    )


def info_lines(login, stats):
    """Rows of (kind, parts) describing the right-hand column."""
    def rule(title):
        return ("rule", (title, "-" * (INFO_WIDTH_CHARS - len(title) - 1)))

    def pair(key, value):
        dots = max(INFO_WIDTH_CHARS - len(key) - len(value) - 4, 2)
        return ("pair", (key, "." * dots, value))

    rows = [rule(f"{login}@github")]
    rows += [pair(k, v) for k, v in PROFILE]
    rows += [("blank", ()), rule("- Contact")]
    rows += [pair(k, v) for k, v in CONTACT]
    rows += [("blank", ()), rule("- GitHub Stats")]
    rows += [pair(k, v) for k, v in stats]
    return rows


def render_info(rows, x, y0):
    c = COLORS
    out = []
    for index, (kind, parts) in enumerate(rows):
        y = y0 + index * LINE_HEIGHT
        if kind == "rule":
            title, dashes = parts
            out.append(
                f'<text x="{x}" y="{y}" xml:space="preserve">'
                f'<tspan fill="{c["title"]}">{escape(title)} </tspan>'
                f'<tspan fill="{c["rule"]}">{dashes}</tspan></text>'
            )
        elif kind == "pair":
            key, dots, value = parts
            out.append(
                f'<text x="{x}" y="{y}" xml:space="preserve">'
                f'<tspan fill="{c["key"]}">{escape(key)}:</tspan>'
                f'<tspan fill="{c["dots"]}"> {dots} </tspan>'
                f'<tspan fill="{c["value"]}">{escape(value)}</tspan></text>'
            )
    return "\n".join(out)


def render(login, art, stats):
    c = COLORS
    rows = info_lines(login, stats)
    art_height = len(art) * ART_LINE_HEIGHT
    info_height = len(rows) * LINE_HEIGHT
    body_height = max(art_height, info_height)
    info_x = PADDING + ART_COLUMNS * ART_CHAR_WIDTH + GAP
    width = round(info_x + INFO_WIDTH_CHARS * INFO_CHAR_WIDTH + PADDING)
    height = round(PADDING * 2 + body_height)
    info_y0 = PADDING + (body_height - info_height) / 2 + 12
    art_text = "\n".join(
        f'<text x="{PADDING}" y="{PADDING + 8 + i * ART_LINE_HEIGHT:.1f}" xml:space="preserve">{escape(line)}</text>'
        for i, line in enumerate(art)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(login)} profile card">
<style>text{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace}}</style>
<rect width="{width}" height="{height}" rx="6" fill="{c['bg']}"/>
<g font-size="{ART_FONT_SIZE}" fill="{c['art']}">
{art_text}
</g>
<g font-size="{INFO_FONT_SIZE}">
{render_info(rows, info_x, info_y0)}
</g>
</svg>
"""


def main(login, output):
    token = os.environ["GH_TOKEN"]
    svg = render(login, portrait_art(), fetch_stats(login, token))
    with open(output, "w", encoding="utf-8") as handle:
        handle.write(svg)
    print(f"wrote {output}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])

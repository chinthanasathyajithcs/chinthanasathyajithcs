"""Render a neofetch-style profile card (ASCII avatar + info) as SVG.

Usage: GH_TOKEN=... python3 scripts/neofetch.py <login> <output.svg>
Needs Pillow for the ASCII avatar.
"""
import datetime as dt
import io
import os
import sys
import urllib.request
from xml.sax.saxutils import escape

from PIL import Image, ImageOps

from streak import contribution_counts, graphql, streaks

COLORS = {
    "bg": "#0D1117",
    "accent": "#50BF91",
    "value": "#c9d1d9",
    "dots": "#6b7280",
    "art": "#50BF91",
}

ART_COLUMNS = 52
ART_ROWS = 26
ART_GAMMA = 0.7
ART_RAMP = " .:-=+*#%@"
ART_FONT_SIZE = 10
ART_CHAR_WIDTH = 6
LINE_HEIGHT = 16
INFO_FONT_SIZE = 12
INFO_CHAR_WIDTH = 7.2
INFO_WIDTH_CHARS = 58
PADDING = 20
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
    ("GitHub", "chinthanasathyajithcs"),
)

STATS_QUERY = "query($l:String!){user(login:$l){repositories(ownerAffiliations:OWNER,privacy:PUBLIC){totalCount} followers{totalCount}}}"


def avatar_art(login):
    """Return the avatar as ASCII rows, dark pixels blank and bright pixels dense."""
    with urllib.request.urlopen(f"https://github.com/{login}.png?size=200", timeout=30) as response:
        image = Image.open(io.BytesIO(response.read()))
    gray = ImageOps.autocontrast(image.convert("L").resize((ART_COLUMNS, ART_ROWS), Image.LANCZOS))
    gray = gray.point(lambda v: round(255 * (v / 255) ** ART_GAMMA))
    last = len(ART_RAMP) - 1
    return [
        "".join(ART_RAMP[gray.getpixel((x, y)) * last // 255] for x in range(ART_COLUMNS))
        for y in range(ART_ROWS)
    ]


def fetch_stats(login, token):
    user = graphql(STATS_QUERY, {"l": login}, token)
    counts = contribution_counts(login, token)
    today = dt.datetime.now(dt.timezone.utc).date()
    total, current, longest = streaks(counts, today)
    return (
        ("Repos", f"{user['repositories']['totalCount']} public"),
        ("Followers", str(user["followers"]["totalCount"])),
        ("Contributions", f"{total:,}"),
        ("Streak", f"{current[0]} current | {longest[0]} longest"),
    )


def info_lines(login, stats):
    """Rows of (kind, parts) describing the right-hand column."""
    def rule(title):
        return ("rule", (f"{title} " + "-" * INFO_WIDTH_CHARS)[:INFO_WIDTH_CHARS])

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
            out.append(f'<text x="{x}" y="{y}" fill="{c["accent"]}" xml:space="preserve">{escape(parts)}</text>')
        elif kind == "pair":
            key, dots, value = parts
            out.append(
                f'<text x="{x}" y="{y}" xml:space="preserve">'
                f'<tspan fill="{c["accent"]}">{escape(key)}:</tspan>'
                f'<tspan fill="{c["dots"]}"> {dots} </tspan>'
                f'<tspan fill="{c["value"]}">{escape(value)}</tspan></text>'
            )
    return "\n".join(out)


def render(login, art, stats):
    c = COLORS
    rows = info_lines(login, stats)
    info_x = PADDING + ART_COLUMNS * ART_CHAR_WIDTH + GAP
    width = round(info_x + INFO_WIDTH_CHARS * INFO_CHAR_WIDTH + PADDING)
    height = PADDING * 2 + max(len(art) * (ART_FONT_SIZE + 2), len(rows) * LINE_HEIGHT)
    art_text = "\n".join(
        f'<text x="{PADDING}" y="{PADDING + 10 + i * (ART_FONT_SIZE + 2)}" xml:space="preserve">{escape(line)}</text>'
        for i, line in enumerate(art)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(login)} profile card">
<style>text{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace}}</style>
<rect width="{width}" height="{height}" rx="6" fill="{c['bg']}"/>
<g font-size="{ART_FONT_SIZE}" fill="{c['art']}">
{art_text}
</g>
<g font-size="{INFO_FONT_SIZE}">
{render_info(rows, info_x, PADDING + 12)}
</g>
</svg>
"""


def main(login, output):
    token = os.environ["GH_TOKEN"]
    svg = render(login, avatar_art(login), fetch_stats(login, token))
    with open(output, "w", encoding="utf-8") as handle:
        handle.write(svg)
    print(f"wrote {output}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])

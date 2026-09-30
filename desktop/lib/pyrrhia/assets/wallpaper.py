"""Placeholder wallpapers for tribes that don't ship any art yet: the tribe's pattern over a glow
in its colours, with its name. Named placeholder.svg so the settings app can flag them."""
from pathlib import Path
from xml.sax.saxutils import escape

from .. import colors as c
from .. import patterns
from . import palette

WIDTH, HEIGHT = 1920, 1080


def placeholder_svg(tribe):
    p = palette.of(tribe)
    deep = c.darken(p.background, 0.3) if tribe.dark else c.mix(p.background, p.accent, 0.12)
    glow = c.mix(p.surface, p.accent, 0.35)
    w, h, tile = patterns.tile(tribe.pattern, p.accent_alt if tribe.dark else p.accent, opacity=0.35, scale=1.6)
    name = escape(f"{tribe.name}s".upper())
    realm = escape(f"Kingdoms of {tribe.realm}".upper())
    text = p.text
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
<defs>
  <radialGradient id="glow" cx="0.5" cy="0.42" r="0.75">
    <stop offset="0" stop-color="{glow}"/><stop offset="0.55" stop-color="{p.background}"/><stop offset="1" stop-color="{deep}"/>
  </radialGradient>
  <pattern id="motif" patternUnits="userSpaceOnUse" width="{w:g}" height="{h:g}">
    <image width="{w:g}" height="{h:g}" href="{patterns.data_uri(tile)}"/>
  </pattern>
  <radialGradient id="fade" cx="0.5" cy="0.45" r="0.6">
    <stop offset="0" stop-color="#fff" stop-opacity="0.15"/><stop offset="1" stop-color="#fff" stop-opacity="1"/>
  </radialGradient>
  <mask id="edges"><rect width="100%" height="100%" fill="url(#fade)"/></mask>
</defs>
<rect width="100%" height="100%" fill="url(#glow)"/>
<rect width="100%" height="100%" fill="url(#motif)" mask="url(#edges)"/>
<text x="960" y="560" text-anchor="middle" font-family="EB Garamond, serif" font-size="120"
      letter-spacing="18" fill="{text}" fill-opacity="0.9">{name}</text>
<rect x="760" y="600" width="400" height="3" fill="{p.accent}"/>
<text x="960" y="660" text-anchor="middle" font-family="EB Garamond, serif" font-size="36"
      letter-spacing="10" fill="{text}" fill-opacity="0.6">{realm}</text>
</svg>
"""


def write_placeholder(tribe, wallpapers_dir):
    wallpapers_dir = Path(wallpapers_dir)
    wallpapers_dir.mkdir(parents=True, exist_ok=True)
    path = wallpapers_dir / "placeholder.svg"
    path.write_text(placeholder_svg(tribe))
    return path

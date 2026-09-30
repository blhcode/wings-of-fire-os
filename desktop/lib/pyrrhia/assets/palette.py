"""Colours derived from a tribe's five base colours, shared by all generators."""
from dataclasses import dataclass

from .. import colors as c


@dataclass(frozen=True)
class Palette:
    dark: bool
    accent: str
    accent_alt: str
    background: str
    surface: str
    text: str
    on_accent: str
    muted: str
    border: str
    raised: str
    sunken: str
    selection: str
    link: str
    panel: str
    seal: str

    @property
    def accent_text(self):
        """The accent adjusted so it's readable as text on the background."""
        if self.dark:
            return c.lighten(self.accent, 0.15)
        return c.darken(self.accent, 0.2)


def of(tribe):
    col = tribe.colors
    dark = tribe.dark
    bg, surface, text, accent = col["background"], col["surface"], col["text"], col["accent"]
    toward_text = (lambda base, t: c.mix(base, text, t))
    return Palette(
        dark=dark,
        accent=accent,
        accent_alt=col["accent_alt"],
        background=bg,
        surface=surface,
        text=text,
        on_accent=c.readable_on(accent),
        muted=c.mix(text, bg, 0.4),
        border=toward_text(surface, 0.18 if dark else 0.14),
        raised=toward_text(surface, 0.07 if dark else 0.0) if dark else c.darken(surface, 0.03),
        sunken=c.mix(bg, "#000000", 0.2) if dark else c.darken(bg, 0.04),
        selection=c.mix(accent, bg, 0.35 if dark else 0.15),
        link=c.lighten(col["accent_alt"], 0.2) if dark else c.darken(col["accent_alt"], 0.25),
        panel=c.mix(bg, accent, 0.08) if dark else c.mix(surface, accent, 0.1),
        seal=tribe.editor["seal"],
    )

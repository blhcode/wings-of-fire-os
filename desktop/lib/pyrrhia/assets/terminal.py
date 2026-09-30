"""xfce4-terminal colours per tribe. The same values are written as a colour scheme file (selectable
in the terminal's preferences) and applied live through xfconf by the terminal component."""
from pathlib import Path

from .. import colors as c
from . import palette

# Standard ANSI hues, nudged towards each tribe and kept readable on its background.
ANSI = ("#000000", "#e0413a", "#3fbf5a", "#e3b53b", "#3b82e0", "#b35fd6", "#2fbcc4", "#d0d0d0")


def _readable(colour, background, dark):
    for _ in range(12):
        contrast = (max(c.luminance(colour), c.luminance(background)) + 0.05) / \
                   (min(c.luminance(colour), c.luminance(background)) + 0.05)
        if contrast >= 3.2:
            break
        colour = c.lighten(colour, 0.12) if dark else c.darken(colour, 0.12)
    return colour


def colours(tribe):
    """Dict of xfconf property -> value for the tribe."""
    p = palette.of(tribe)
    bg = p.background
    fg = p.text
    base = list(ANSI)
    base[0] = c.mix(bg, "#000000", 0.3) if p.dark else c.mix(fg, "#000000", 0.3)
    base[7] = c.mix(fg, bg, 0.2)
    normal = [base[0]] + [_readable(c.mix(h, p.accent, 0.18), bg, p.dark) for h in base[1:7]] + [base[7]]
    bright = [c.mix(base[0], fg, 0.35)] + [_readable(c.lighten(h, 0.2) if p.dark else c.darken(h, 0.1), bg, p.dark)
                                           for h in normal[1:7]] + [fg]
    overrides = tribe.terminal
    return {
        "color-foreground": overrides.get("foreground", fg),
        "color-background": overrides.get("background", bg),
        "color-cursor": overrides.get("cursor", p.accent),
        "color-cursor-foreground": overrides.get("cursor_foreground", p.on_accent),
        "color-cursor-use-default": False,
        "color-selection": overrides.get("selection", p.on_accent),
        "color-selection-background": overrides.get("selection_background", p.accent),
        "color-selection-use-default": False,
        "color-bold": overrides.get("bold", p.accent_text),
        "color-bold-use-default": False,
        "color-palette": ";".join(overrides.get("palette", normal + bright)),
        "tab-activity-color": p.accent_alt,
    }


def write(tribe, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    col = colours(tribe)
    path.write_text(
        "[Scheme]\n"
        f"Name=Wings of Fire - {tribe.name}\n"
        f"ColorForeground={col['color-foreground']}\n"
        f"ColorBackground={col['color-background']}\n"
        f"ColorCursor={col['color-cursor']}\n"
        f"ColorCursorForeground={col['color-cursor-foreground']}\n"
        "ColorCursorUseDefault=FALSE\n"
        f"ColorSelection={col['color-selection']}\n"
        f"ColorSelectionBackground={col['color-selection-background']}\n"
        "ColorSelectionUseDefault=FALSE\n"
        f"ColorBold={col['color-bold']}\n"
        "ColorBoldUseDefault=FALSE\n"
        f"ColorPalette={col['color-palette']}\n"
        f"TabActivityColor={col['tab-activity-color']}\n")

"""Small colour helpers. Colours are "#rrggbb" strings at the edges and (r, g, b) floats inside."""


def parse(colour):
    colour = colour.lstrip("#")
    if len(colour) != 6:
        raise ValueError(f"expected #rrggbb, got #{colour}")
    return tuple(int(colour[i:i + 2], 16) / 255 for i in (0, 2, 4))


def to_hex(rgb):
    return "#" + "".join(f"{round(max(0, min(1, c)) * 255):02x}" for c in rgb)


def mix(a, b, t):
    """Blend colour a towards b by t (0..1)."""
    a, b = parse(a), parse(b)
    return to_hex(tuple(x + (y - x) * t for x, y in zip(a, b)))


def lighten(colour, amount):
    return mix(colour, "#ffffff", amount)


def darken(colour, amount):
    return mix(colour, "#000000", amount)


def rgba(colour, alpha):
    r, g, b = (round(c * 255) for c in parse(colour))
    return f"rgba({r}, {g}, {b}, {alpha})"


def gdk_rgb(colour):
    """xfce4-terminal / GDK style "rgb(r,g,b)"."""
    r, g, b = (round(c * 255) for c in parse(colour))
    return f"rgb({r},{g},{b})"


def luminance(colour):
    def channel(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in parse(colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def readable_on(background):
    """Black or white, whichever reads better on the background."""
    return "#111111" if luminance(background) > 0.35 else "#ffffff"

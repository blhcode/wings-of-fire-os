"""GtkSourceView style schemes per tribe:

  wof-<id>            the tribe's own colours (used by Mousepad and anything else GtkSourceView based)
  wof-parchment-<id>  dark ink on parchment with tribe-coloured highlights (used by the Scroll editor)
"""
from pathlib import Path
from xml.sax.saxutils import quoteattr

from .. import colors as c
from . import palette

PARCHMENT = "#f3e6c4"
INK = "#3b2a1a"


def _style(name, **attrs):
    parts = " ".join(f"{k.replace('_', '-')}={quoteattr(str(v))}" for k, v in attrs.items() if v is not None)
    return f'  <style name="{name}" {parts}/>'


def _scheme(scheme_id, title, description, bg, fg, p, dark):
    ink = lambda colour, t=0.0: c.mix(colour, fg, t)
    keyword = p.accent_text if dark else c.darken(p.accent, 0.3)
    string = c.mix(p.accent_alt, fg, 0.15) if dark else c.darken(p.accent_alt, 0.45)
    comment = c.mix(fg, bg, 0.45)
    number = c.mix("#e08a3c" if dark else "#9c4a12", p.accent, 0.2)
    styles = [
        _style("text", foreground=fg, background=bg),
        _style("selection", foreground=p.on_accent, background=p.accent),
        _style("selection-unfocused", foreground=fg, background=c.mix(p.accent, bg, 0.6)),
        _style("cursor", foreground=p.accent),
        _style("secondary-cursor", foreground=p.accent_alt),
        _style("current-line", background=c.mix(bg, p.accent, 0.08 if dark else 0.07)),
        _style("current-line-number", foreground=p.accent_text if dark else c.darken(p.accent, 0.25),
               background=c.mix(bg, p.accent, 0.1), bold="true"),
        _style("line-numbers", foreground=c.mix(fg, bg, 0.5), background=c.mix(bg, fg, 0.04)),
        _style("right-margin", foreground=c.mix(fg, bg, 0.7), background=c.mix(bg, fg, 0.03)),
        _style("draw-spaces", foreground=c.mix(fg, bg, 0.7)),
        _style("bracket-match", foreground=p.on_accent, background=c.mix(p.accent_alt, bg, 0.2), bold="true"),
        _style("bracket-mismatch", foreground="#ffffff", background="#c0392b"),
        _style("search-match", foreground=fg, background=c.mix(p.accent_alt, bg, 0.45 if dark else 0.35)),
        _style("def:comment", foreground=comment, italic="true"),
        _style("def:shebang", foreground=comment, bold="true"),
        _style("def:doc-comment-element", foreground=comment, bold="true"),
        _style("def:string", foreground=string),
        _style("def:special-char", foreground=number, bold="true"),
        _style("def:keyword", foreground=keyword, bold="true"),
        _style("def:statement", foreground=keyword, bold="true"),
        _style("def:type", foreground=ink(p.link, 0.1), bold="true"),
        _style("def:builtin", foreground=ink(p.link, 0.1)),
        _style("def:function", foreground=ink(p.link, 0.25)),
        _style("def:identifier", foreground=ink(p.link, 0.4)),
        _style("def:number", foreground=number),
        _style("def:floating-point", foreground=number),
        _style("def:decimal", foreground=number),
        _style("def:base-n-integer", foreground=number),
        _style("def:boolean", foreground=number, bold="true"),
        _style("def:constant", foreground=number),
        _style("def:preprocessor", foreground=c.mix(p.accent_alt, fg, 0.3)),
        _style("def:heading", foreground=keyword, bold="true"),
        _style("def:emphasis", italic="true"),
        _style("def:strong-emphasis", bold="true"),
        _style("def:link-text", foreground=p.link),
        _style("def:underlined", underline="single"),
        _style("def:note", foreground=bg, background=p.accent_alt, bold="true"),
        _style("def:error", foreground="#ffffff", background="#b83227"),
        _style("def:warning", foreground=fg, background=c.mix("#f1c40f", bg, 0.3)),
        _style("def:net-address", foreground=p.link, underline="single"),
        _style("diff:added-line", foreground=c.mix("#27ae60", fg, 0.2)),
        _style("diff:removed-line", foreground=c.mix("#c0392b", fg, 0.2)),
        _style("diff:changed-line", foreground=number),
    ]
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<style-scheme id="{scheme_id}" name={quoteattr(title)} version="1.0">\n'
        '  <author>Wings of Fire OS</author>\n'
        f'  <description>{description}</description>\n'
        + "\n".join(styles) + "\n</style-scheme>\n")


def write(tribe, styles_dir):
    styles_dir = Path(styles_dir)
    styles_dir.mkdir(parents=True, exist_ok=True)
    p = palette.of(tribe)
    (styles_dir / f"wof-{tribe.id}.xml").write_text(_scheme(
        f"wof-{tribe.id}", f"Wings of Fire - {tribe.name}", f"{tribe.name} colours for code and text.",
        p.background, p.text, p, tribe.dark))
    parchment = palette.Palette(**{**p.__dict__, "dark": False,
                                   "accent": c.mix(p.accent, INK, 0.25) if tribe.dark else p.accent,
                                   "link": c.mix(p.accent_alt, INK, 0.55)})
    parchment = palette.Palette(**{**parchment.__dict__, "on_accent": c.readable_on(parchment.accent)})
    (styles_dir / f"wof-parchment-{tribe.id}.xml").write_text(_scheme(
        f"wof-parchment-{tribe.id}", f"Wings of Fire - {tribe.name} Scroll",
        f"Ink on parchment with {tribe.name} highlights.", PARCHMENT, INK, parchment, False))

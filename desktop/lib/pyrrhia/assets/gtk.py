"""GTK 3 theme per tribe: Adwaita (light or dark) with the tribe's colours layered on top, plus the
XFCE panel, notification bubbles and the login screen."""
import textwrap
from pathlib import Path

from .. import colors as c
from .. import patterns
from . import palette

ADWAITA = "resource:///org/gtk/libgtk/theme/Adwaita/gtk-contained{}.css"


def _colour_defs(p):
    names = {
        "wof_accent": p.accent, "wof_accent_alt": p.accent_alt, "wof_bg": p.background,
        "wof_surface": p.surface, "wof_text": p.text, "wof_on_accent": p.on_accent,
        "wof_muted": p.muted, "wof_border": p.border, "wof_raised": p.raised, "wof_sunken": p.sunken,
        "wof_selection": p.selection, "wof_link": p.link, "wof_panel": p.panel,
        # Standard names read by apps and by xfce4-panel plugins.
        "theme_bg_color": p.surface, "theme_fg_color": p.text, "theme_base_color": p.background,
        "theme_text_color": p.text, "theme_selected_bg_color": p.accent,
        "theme_selected_fg_color": p.on_accent, "insensitive_fg_color": p.muted,
        "borders": p.border, "link_color": p.link, "accent_color": p.accent,
    }
    return "\n".join(f"@define-color {k} {v};" for k, v in names.items())


def css(tribe):
    p = palette.of(tribe)
    tile = patterns.data_uri(patterns.svg(tribe.pattern, p.accent, opacity=0.12))
    hover = c.mix(p.raised, p.text, 0.08)
    body = f"""
    @import url("{ADWAITA.format("-dark" if p.dark else "")}");

    {_colour_defs(p)}

    /* Surfaces */
    window.background, .background, dialog .dialog-vbox {{ background-color: @wof_surface; color: @wof_text; }}
    .view, textview text, iconview, treeview.view, list, .content-view, .sidebar, placessidebar list,
    viewport.frame {{ background-color: @wof_bg; color: @wof_text; }}
    .sidebar, placessidebar, placessidebar list {{ background-color: @wof_sunken; }}
    headerbar, .titlebar, toolbar, .primary-toolbar, actionbar, searchbar box {{
        background-image: none; background-color: @wof_panel; color: @wof_text; border-color: @wof_border;
        box-shadow: inset 0 -1px @wof_border;
    }}
    headerbar:backdrop, .titlebar:backdrop {{ background-color: @wof_surface; }}
    menubar {{ background-color: @wof_panel; }}
    menu, .menu, .context-menu, popover, popover.background {{
        background-color: @wof_surface; color: @wof_text; border: 1px solid @wof_border;
    }}
    menuitem:hover, menu menuitem:hover, modelbutton:hover, popover modelbutton:hover {{
        background-color: @wof_accent; color: @wof_on_accent;
    }}
    tooltip, tooltip.background {{ background-color: {c.rgba(p.sunken, 0.96)}; color: @wof_text; border: 1px solid @wof_accent; }}
    separator {{ background-color: @wof_border; }}
    frame > border, .frame {{ border-color: @wof_border; }}
    notebook > header {{ background-color: @wof_panel; border-color: @wof_border; }}
    notebook > header tab:checked {{ box-shadow: inset 0 -3px @wof_accent; }}
    notebook > stack:not(:only-child) {{ background-color: @wof_bg; }}

    /* Controls */
    button {{ background-image: none; background-color: @wof_raised; color: @wof_text; border-color: @wof_border;
              box-shadow: none; text-shadow: none; }}
    button:hover {{ background-color: {hover}; }}
    button:active, button:checked {{ background-color: @wof_selection; color: @wof_text; }}
    button.flat {{ background-color: transparent; border-color: transparent; }}
    button.flat:hover {{ background-color: {c.rgba(p.text, 0.08)}; }}
    button.suggested-action, button.default:focus {{
        background-image: none; background-color: @wof_accent; color: @wof_on_accent; border-color: {c.darken(p.accent, 0.2)};
    }}
    button.suggested-action:hover {{ background-image: none; background-color: {c.lighten(p.accent, 0.1)}; }}
    button.suggested-action:disabled {{ background-image: none; background-color: {c.mix(p.accent, p.surface, 0.5)}; }}
    entry, spinbutton:not(.vertical), combobox entry {{
        background-image: none; background-color: @wof_bg; color: @wof_text; border-color: @wof_border; box-shadow: none;
    }}
    entry:focus, spinbutton:focus {{ border-color: @wof_accent; box-shadow: inset 0 0 0 1px @wof_accent; }}
    entry selection, textview text selection, label selection, .view:selected, .view text:selected,
    treeview.view:selected, iconview:selected, flowbox flowboxchild:selected,
    list row:selected, row:selected, placessidebar row:selected {{
        background-color: @wof_accent; color: @wof_on_accent;
    }}
    list row:hover {{ background-color: {c.rgba(p.accent, 0.15)}; }}
    switch {{ background-color: @wof_sunken; border-color: @wof_border; }}
    switch:checked {{ background-color: @wof_accent; }}
    switch slider {{ background-image: none; background-color: {c.lighten(p.surface, 0.85)}; }}
    check, radio {{ background-image: none; background-color: @wof_bg; border-color: @wof_border; }}
    check:checked, radio:checked, check:indeterminate, radio:indeterminate {{
        background-image: none; background-color: @wof_accent; border-color: {c.darken(p.accent, 0.15)}; color: @wof_on_accent;
    }}
    scale highlight, progressbar progress, levelbar block.filled, levelbar block.high {{
        background-image: none; background-color: @wof_accent; border-color: @wof_accent;
    }}
    scale trough, progressbar trough, levelbar trough {{ background-color: @wof_sunken; border-color: @wof_border; }}
    scale slider {{ background-image: none; background-color: @wof_accent_alt; border-color: {c.darken(p.accent_alt, 0.2)}; }}
    scrollbar slider {{ background-color: {c.rgba(p.text, 0.35)}; }}
    scrollbar slider:hover {{ background-color: @wof_accent; }}
    *:link, link {{ color: @wof_link; }}
    spinner {{ color: @wof_accent; }}
    infobar.info > revealer > box {{ background-color: @wof_selection; color: @wof_text; }}
    stackswitcher button:checked, .linked button:checked {{ background-image: none; background-color: @wof_accent; color: @wof_on_accent; }}

    /* XFCE panel and desktop */
    .xfce4-panel.background, .xfce4-panel {{
        background-color: {c.rgba(p.panel, 0.94)}; background-image: url("{tile}");
        color: @wof_text; border-color: @wof_border;
    }}
    .xfce4-panel button {{ background-color: transparent; border-color: transparent; color: @wof_text; }}
    .xfce4-panel button:hover {{ background-color: {c.rgba(p.accent, 0.25)}; }}
    .xfce4-panel button:checked, .xfce4-panel button:active {{ background-image: none; background-color: @wof_accent; color: @wof_on_accent; }}
    XfdesktopIconView.view {{ background-color: transparent; color: #ffffff; text-shadow: 0 1px 2px #000000; }}
    XfdesktopIconView.view:selected {{ background-color: {c.rgba(p.accent, 0.6)}; }}

    /* Login screen (lightdm-gtk-greeter) */
    #login_window, #restart_dialog, #shutdown_dialog {{
        background-color: {c.rgba(p.surface, 0.9)}; color: @wof_text; border: 2px solid @wof_accent;
        border-radius: 14px; box-shadow: 0 8px 30px {c.rgba("#000000", 0.5)};
    }}
    #panel_window {{ background-color: {c.rgba(p.panel, 0.85)}; color: @wof_text; }}
    #panel_window menubar, #panel_window menubar > menuitem {{ background-color: transparent; color: @wof_text; }}
    #login_window #user_image {{ border: 3px solid @wof_accent; border-radius: 50%; }}
    #login_window #login_button, #login_window #unlock_button {{
        background-image: none; background-color: @wof_accent; color: @wof_on_accent; border-color: {c.darken(p.accent, 0.2)};
    }}
    """
    return textwrap.dedent(body).lstrip()


def notify_css(tribe):
    p = palette.of(tribe)
    return textwrap.dedent(f"""\
    #XfceNotifyWindow {{
        background-color: {c.rgba(p.surface, 0.95)};
        color: {p.text};
        border: 2px solid {p.accent};
        border-radius: 12px;
    }}
    #XfceNotifyWindow:hover {{ border-color: {p.accent_alt}; }}
    #XfceNotifyWindow label#summary {{ font-weight: bold; color: {p.accent_text}; }}
    #XfceNotifyWindow label#body {{ color: {p.text}; }}
    #XfceNotifyWindow button {{ background-image: none; background-color: {p.raised}; color: {p.text}; border-color: {p.border}; }}
    #XfceNotifyWindow button:hover {{ background-color: {p.accent}; color: {p.on_accent}; }}
    #XfceNotifyWindow progressbar progress {{ background-color: {p.accent}; }}
    """)


def write(tribe, theme_dir):
    theme_dir = Path(theme_dir)
    (theme_dir / "gtk-3.0").mkdir(parents=True, exist_ok=True)
    (theme_dir / "gtk-3.0/gtk.css").write_text(css(tribe))
    (theme_dir / "xfce-notify-4.0").mkdir(exist_ok=True)
    (theme_dir / "xfce-notify-4.0/gtk.css").write_text(notify_css(tribe))
    (theme_dir / "index.theme").write_text(textwrap.dedent(f"""\
    [Desktop Entry]
    Type=X-GNOME-Metatheme
    Name={tribe.theme_name}
    Comment=Wings of Fire OS theme for the {tribe.name}s
    Encoding=UTF-8

    [X-GNOME-Metatheme]
    GtkTheme={tribe.theme_name}
    IconTheme={tribe.icon_theme}
    """))

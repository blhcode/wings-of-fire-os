"""wof-tribe: switch and inspect Wings of Fire OS tribes from the terminal."""
import argparse
import sys

from . import components, firefox, state as state_mod, theme, tribes


def _print_results(tribe, results):
    print(f"{tribe.name} applied.")
    for comp, ok, message in results:
        print(f"  {'ok ' if ok else 'ERR'} {comp.label}: {message}")
    return 0 if all(ok for _, ok, _ in results) else 1


def cmd_list(args):
    current = state_mod.load().tribe
    for tribe in tribes.all_tribes().values():
        mark = "*" if tribe.id == current else " "
        walls = ", ".join(p.name for p in tribe.wallpapers()) or "none"
        print(f"{mark} {tribe.id:<11} {tribe.name:<10} {tribe.realm:<8} wallpapers: {walls}")
    return 0


def cmd_current(args):
    state = state_mod.load()
    tribe = tribes.get(state.tribe)
    wall = tribe.wallpaper(state.wallpaper or None)
    print(f"tribe:      {tribe.name} ({tribe.id})")
    print(f"wallpaper:  {wall or 'none'}")
    for comp in components.COMPONENTS:
        print(f"{comp.id + ':':<11} {'on' if state.enabled(comp.id) else 'off'}")
    return 0


def _ids(text):
    ids = [i.strip() for i in text.split(",") if i.strip()]
    unknown = [i for i in ids if i not in components.BY_ID]
    if unknown:
        raise SystemExit(f"unknown component(s): {', '.join(unknown)} (one of {', '.join(components.BY_ID)})")
    return ids


def cmd_apply(args):
    state = theme.choose(args.tribe, args.wallpaper)
    only = _ids(args.only) if args.only else None
    if args.skip:
        skip = _ids(args.skip)
        only = [c for c in (only or components.BY_ID) if c not in skip]
    tribe, results = theme.apply(state, only=only)
    return _print_results(tribe, results)


def cmd_set(args):
    _ids(args.component)
    state = state_mod.load()
    state.components[args.component] = args.value == "on"
    state_mod.save(state)
    if args.component == "firefox" and args.value == "off":
        firefox.remove()
    print(f"{args.component}: {args.value}")
    return 0


def cmd_session_start(args):
    tribe, results = theme.session_start()
    return _print_results(tribe, results)


def cmd_firefox_remove(args):
    firefox.remove()
    print("Wings of Fire OS theming removed from Firefox (restart Firefox to see it).")
    return 0


def cmd_build_assets(args):
    from . import assets
    built = assets.build_all(args.root, tribes_dir=args.tribes_dir)
    print(f"built assets for {len(built)} tribes in {args.root}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="wof-tribe", description="Wings of Fire OS tribe themes")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list tribes").set_defaults(func=cmd_list)
    sub.add_parser("current", help="show the current tribe and components").set_defaults(func=cmd_current)
    p = sub.add_parser("apply", help="switch to a tribe")
    p.add_argument("tribe")
    p.add_argument("--wallpaper", help="wallpaper file name from the tribe's wallpapers")
    p.add_argument("--only", help="comma-separated components to apply")
    p.add_argument("--skip", help="comma-separated components to leave alone")
    p.set_defaults(func=cmd_apply)
    p = sub.add_parser("set", help="turn a component on or off")
    p.add_argument("component")
    p.add_argument("value", choices=("on", "off"))
    p.set_defaults(func=cmd_set)
    sub.add_parser("session-start", help="run at login").set_defaults(func=cmd_session_start)
    sub.add_parser("firefox-remove", help="remove the Firefox theme").set_defaults(func=cmd_firefox_remove)
    p = sub.add_parser("build-assets", help="generate theme assets (used when building the OS)")
    p.add_argument("root", help="directory laid out like /usr/share")
    p.add_argument("--tribes-dir", help="where to write placeholder wallpapers")
    p.set_defaults(func=cmd_build_assets)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except tribes.TribeError as err:
        print(f"wof-tribe: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

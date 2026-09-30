#!/bin/sh
# Runs inside the chroot. Puts Pyrrhia Settings (the one-click tribe switcher) first among the dock's
# launchers, so it's easy to find again after the first-login welcome.
set -eu

PANEL=/etc/xdg/xfce4/panel/default.xml
[ -f "$PANEL" ] || exit 0

python3 - "$PANEL" <<'EOF'
import sys
import xml.etree.ElementTree as ET

path = sys.argv[1]
tree = ET.parse(path)
root = tree.getroot()
plugins = root.find("./property[@name='plugins']")
if any(v.get("value") == "pyrrhia-settings.desktop" for v in plugins.iter("value")):
    sys.exit(0)

dock = root.find("./property[@name='panels']/property[@name='panel-2']/property[@name='plugin-ids']")
ids = [int(p.get("name").split("-")[1]) for p in plugins.findall("property")]
new_id = max(ids) + 1

launcher = ET.SubElement(plugins, "property", name=f"plugin-{new_id}", type="string", value="launcher")
items = ET.SubElement(launcher, "property", name="items", type="array")
ET.SubElement(items, "value", type="string", value="pyrrhia-settings.desktop")

# Before the first existing launcher (after "show desktop" and its separator).
kinds = {int(p.get("name").split("-")[1]): p.get("value") for p in plugins.findall("property")}
values = list(dock)
first = next((i for i, v in enumerate(values) if kinds.get(int(v.get("value"))) == "launcher"), len(values))
dock.insert(first, ET.Element("value", type="int", value=str(new_id)))

ET.indent(tree, "  ")
tree.write(path, encoding="UTF-8", xml_declaration=True)
EOF

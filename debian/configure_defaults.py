"""Prepare container-appropriate XFCE defaults in the image, never user volumes."""
from pathlib import Path
import xml.etree.ElementTree as ET


def clean_panel(xml, available_modules):
    root = ET.fromstring(xml)
    plugins = root.find("./property[@name='plugins']")
    if plugins is None:
        return xml
    retained = set()
    for plugin in list(plugins):
        name = plugin.get('name', '')
        if not name.startswith('plugin-'):
            continue
        module = plugin.get('value')
        # A container has no battery. Other missing modules are dangling image
        # defaults; notifications remain available through xfce4-notifyd.
        if module == 'power-manager-plugin' or module not in available_modules:
            plugins.remove(plugin)
        else:
            retained.add(name.removeprefix('plugin-'))
    for ids in root.findall(".//property[@name='plugin-ids']"):
        for value in list(ids):
            if value.tag == 'value' and value.get('value') not in retained:
                ids.remove(value)
    return ET.tostring(root, encoding='unicode')


def main():
    default = Path('/etc/xdg/xfce4/panel/default.xml')
    seed = Path('/opt/desktop-seed/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml')
    modules = {p.stem for p in Path('/usr/share/xfce4/panel/plugins').glob('*.desktop')}
    if not default.exists() or not modules:
        raise SystemExit('XFCE panel defaults or installed modules are missing')
    default.write_text(clean_panel(default.read_text(), modules))
    seed.parent.mkdir(parents=True, exist_ok=True)
    seed.write_text(clean_panel(seed.read_text() if seed.exists() else default.read_text(), modules))


if __name__ == '__main__':
    main()

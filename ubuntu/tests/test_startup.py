import pathlib
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from configure_defaults import clean_panel
from runtime_checks import has_loopback_listener


class ReadinessTests(unittest.TestCase):
    def test_only_loopback_listen_socket_is_ready(self):
        with tempfile.TemporaryDirectory() as folder:
            table = pathlib.Path(folder) / 'tcp'
            for address, state, expected in [
                ('0100007F:170D', '0A', True),
                ('0100007F:170D', '01', False),
                ('00000000:170D', '0A', False),
                ('0100007F:170E', '0A', False),
            ]:
                table.write_text('sl local_address rem_address st\n0: ' + address + ' 00000000:0000 ' + state + '\n')
                self.assertEqual(has_loopback_listener(5901, table), expected)

    def test_unreadable_or_missing_state_fails_closed(self):
        self.assertFalse(has_loopback_listener(5901, '/nonexistent-railway-desktop/tcp'))
        with tempfile.TemporaryDirectory() as folder:
            table = pathlib.Path(folder) / 'tcp'
            table.write_text('empty\nmalformed row\n')
            self.assertFalse(has_loopback_listener(5901, table))


class DefaultPanelTests(unittest.TestCase):
    def test_missing_refs_and_battery_removed_useful_plugins_and_layout_retained(self):
        original = '''<channel name="xfce4-panel" version="1.0">
          <property name="panels"><property name="panel-1">
            <property name="size" type="uint" value="32"/>
            <property name="plugin-ids" type="array">
              <value type="int" value="1"/><value type="int" value="7"/>
              <value type="int" value="9"/><value type="int" value="10"/>
            </property></property></property>
          <property name="plugins">
            <property name="plugin-1" type="string" value="applicationsmenu"/>
            <property name="plugin-9" type="string" value="power-manager-plugin"/>
            <property name="plugin-10" type="string" value="notification-plugin"/>
          </property></channel>'''
        result = clean_panel(original, {'applicationsmenu', 'power-manager-plugin', 'notification-plugin'})
        root = ET.fromstring(result)
        self.assertEqual([v.get('value') for v in root.findall(".//property[@name='plugin-ids']/value")], ['1', '10'])
        self.assertEqual(root.find(".//property[@name='size']").get('value'), '32')
        self.assertIsNotNone(root.find(".//property[@name='plugin-10']"))
        self.assertEqual(clean_panel(result, {'applicationsmenu', 'notification-plugin'}), result)

    def test_unknown_module_removed_without_changing_other_panel_settings(self):
        original = '<channel><property name="custom" value="keep"/><property name="plugins"><property name="plugin-3" value="missing-module"/></property><property name="plugin-ids"><value value="3"/></property></channel>'
        root = ET.fromstring(clean_panel(original, set()))
        self.assertEqual(root.find("./property[@name='custom']").get('value'), 'keep')
        self.assertEqual(len(root.find("./property[@name='plugin-ids']")), 0)


if __name__ == '__main__':
    unittest.main()

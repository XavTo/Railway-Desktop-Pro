import io
import os
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from configure_defaults import clean_panel
from runtime_checks import has_loopback_listener, monitor_desktop
from startup_resources import MIN_FREE, StartupHandler, memory_limit, resource_problems, wait_for_resources


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


class DesktopRecoveryTests(unittest.TestCase):
    @patch('runtime_checks.signal_process_group')
    def test_clean_logout_restarts_only_the_session(self, terminate):
        old_session = Mock(poll=Mock(return_value=0))
        display = Mock(poll=Mock(return_value=None))
        proxy = Mock(poll=Mock(return_value=None))
        new_session = Mock(poll=Mock(return_value=None))
        children = {'display': display, 'desktop': old_session, 'proxy': proxy}
        stopping = Mock(wait=Mock(side_effect=[False, False, True]))
        restart = Mock(side_effect=lambda: children.update(desktop=new_session))

        self.assertTrue(monitor_desktop(children, stopping, restart))
        restart.assert_called_once()
        self.assertIs(terminate.call_args.args[0], old_session)
        self.assertEqual(children, {'display': display, 'desktop': new_session, 'proxy': proxy})

    @patch('runtime_checks.signal_process_group')
    def test_session_recovery_is_bounded_after_repeated_failures(self, _):
        children = {'desktop': Mock(poll=Mock(return_value=1))}
        stopping = Mock(wait=Mock(return_value=False))
        restart = Mock()

        self.assertFalse(monitor_desktop(children, stopping, restart))
        self.assertEqual(restart.call_count, 3)

    def test_does_not_restart_xfce_when_the_underlying_display_has_failed(self):
        children = {'desktop': Mock(poll=Mock(return_value=0)), 'display': Mock(poll=Mock(return_value=1))}
        restart = Mock()

        self.assertFalse(monitor_desktop(children, Mock(wait=Mock(return_value=False)), restart))
        restart.assert_not_called()


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


class StartupResourcesTests(unittest.TestCase):
    def test_reports_unready_to_healthz_but_serves_the_diagnostic_page(self):
        for path, status in [('/healthz', 503), ('/', 200)]:
            with self.subTest(path=path):
                handler = object.__new__(StartupHandler)
                handler.path = path
                handler.server = Mock(problems=['The volume is full.'])
                handler.send_response = Mock()
                handler.send_header = Mock()
                handler.end_headers = Mock()
                handler.wfile = io.BytesIO()
                handler.do_GET()
                handler.send_response.assert_called_once_with(status)
                self.assertIn(b'waiting-for-resources' if path == '/healthz' else b'The volume is full.',
                              handler.wfile.getvalue())

    def test_container_memory_limit_and_unlimited_case(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            limit = root / 'memory.max'
            limit.write_text('250000000')
            self.assertEqual(memory_limit(root), 250_000_000)
            limit.write_text('max')
            self.assertIsNone(memory_limit(root))

    @patch('startup_resources.memory_limit', return_value=250_000_000)
    @patch('pathlib.Path.read_text', return_value='3 2 0:54 / / rw - ext4 /dev/loop0 rw')
    def test_reports_low_memory_and_missing_railway_volume_together(self, *_):
        problems = resource_problems(pathlib.Path('/config'), {'RAILWAY_ENVIRONMENT_ID': 'test'})
        self.assertEqual(len(problems), 2)
        self.assertIn('250.0 MB', problems[0])
        self.assertIn('/config', problems[1])

    @patch('startup_resources.memory_limit', return_value=499_998_720)
    @patch('os.access', return_value=True)
    def test_small_or_read_only_storage_blocks_but_the_free_memory_limit_is_allowed(self, *_):
        stats = Mock(f_flag=0, f_bavail=0, f_frsize=4096, f_files=100, f_favail=20)
        with patch('os.statvfs', return_value=stats):
            self.assertIn('0 MiB free', resource_problems(pathlib.Path('/config'), {})[0])
            stats.f_bavail = MIN_FREE // stats.f_frsize
            self.assertEqual(resource_problems(pathlib.Path('/config'), {}), [])
            stats.f_flag = os.ST_RDONLY
            self.assertIn('read-only', resource_problems(pathlib.Path('/config'), {})[0])

    @patch('startup_resources.signal.signal')
    @patch('startup_resources.threading.Thread')
    @patch('startup_resources.threading.Event')
    @patch('startup_resources.StartupServer')
    @patch('startup_resources.resource_problems', side_effect=[['storage too small'], []])
    def test_waits_for_resources_and_only_then_initializes_the_desktop(self, _probe, _server, event, *_):
        prepare = Mock()
        event.return_value.wait.return_value = False
        self.assertTrue(wait_for_resources(pathlib.Path('/config'), 3000, prepare))
        event.return_value.wait.assert_called_once_with(15)
        prepare.assert_called_once_with()


    @patch('startup_resources.signal.signal')
    @patch('startup_resources.threading.Thread')
    @patch('startup_resources.threading.Event')
    @patch('startup_resources.StartupServer')
    @patch('startup_resources.time.monotonic', side_effect=[0, 597, 600])
    def test_deadline_rechecks_and_exits_without_initializing_when_still_blocked(self, _clock, _server, event, *_):
        prepare = Mock()
        event.return_value.wait.return_value = False
        with patch('startup_resources.resource_problems', return_value=['storage too small']) as check:
            self.assertFalse(wait_for_resources(pathlib.Path('/config'), 3000, prepare))
        self.assertEqual(check.call_count, 2)
        event.return_value.wait.assert_called_once_with(3)
        prepare.assert_not_called()


if __name__ == '__main__':
    unittest.main()

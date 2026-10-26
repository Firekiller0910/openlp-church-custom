"""OBS connection tests must update the visible status, including later failures."""
from unittest.mock import MagicMock, patch
from threading import Event

import pytest
from PySide6 import QtWidgets

from openlp.core.ui.churchtools import ChurchTools


@pytest.fixture
def tools(settings, qtbot, monkeypatch):
    window = QtWidgets.QMainWindow()
    window.tools_menu = window.menuBar().addMenu('Tools')
    window.status_bar = window.statusBar()
    qtbot.addWidget(window)
    monkeypatch.setattr(ChurchTools, 'listener', lambda self: None)
    instance = ChurchTools(window)
    instance.timer.stop()
    yield instance


def is_green(tools):
    image = tools.obs_button.icon().pixmap(64, 64).toImage()
    color = image.pixelColor(32, 4)
    assert color.alpha() > 0
    return color.green() > color.red()


def test_successful_probe_turns_light_green_with_integration_disabled(tools, qtbot):
    with patch('openlp.plugins.obs_studio.lib.obs_studio_api.ObsStudioAPI') as api:
        tools.test_obs()
        qtbot.waitUntil(lambda: not tools.obs_busy)
    assert is_green(tools)
    assert tools.obs_button.accessibleName() == 'OBS: Reachable'
    assert 'Slide integration is disabled' in tools.obs_button.toolTip()
    assert tools.window.status_bar.currentMessage() == 'Test passed (reachable)'
    api.return_value.disconnect.assert_called_once()
    api.return_value.send_advanced_scene_switcher_message.assert_not_called()


def test_failed_recheck_turns_green_light_red_even_with_stale_listener(tools, qtbot):
    listener = MagicMock(is_active=True, is_connected=True)
    with patch.object(tools, 'listener', return_value=listener), \
            patch('openlp.plugins.obs_studio.lib.obs_studio_api.ObsStudioAPI') as api:
        tools.test_obs()
        qtbot.waitUntil(lambda: not tools.obs_busy)
        assert is_green(tools)
        api.side_effect = ConnectionError('OBS closed')
        tools.test_obs()
        qtbot.waitUntil(lambda: not tools.obs_busy)
    assert not is_green(tools)
    assert 'Test failed' in tools.obs_button.accessibleName()


def test_periodic_check_does_not_replace_operator_status_message(tools, qtbot):
    with patch('openlp.plugins.obs_studio.lib.obs_studio_api.ObsStudioAPI'):
        tools.test_obs()
        qtbot.waitUntil(lambda: not tools.obs_busy)
        tools.window.status_bar.showMessage('Service saved')
        tools.obs_next_check = 0
        tools.refresh_obs()
        qtbot.waitUntil(lambda: not tools.obs_busy)
    assert is_green(tools)
    assert tools.window.status_bar.currentMessage() == 'Service saved'


def test_changed_settings_clear_old_green_status_and_schedule_new_probe(tools, settings, qtbot):
    with patch('openlp.plugins.obs_studio.lib.obs_studio_api.ObsStudioAPI'):
        tools.test_obs()
        qtbot.waitUntil(lambda: not tools.obs_busy)
    settings.setValue('obs_studio/host', 'another-obs-computer')
    with patch.object(tools, 'test_obs') as probe:
        tools.refresh_obs()
    assert not is_green(tools)
    probe.assert_called_once_with(automatic=True)


def test_connected_listener_is_green_before_any_manual_probe(tools):
    with patch.object(tools, 'listener', return_value=MagicMock(is_active=True, is_connected=True)):
        tools.refresh_obs()
    assert is_green(tools)
    assert tools.obs_button.accessibleName() == 'OBS: Connected'


def test_late_success_for_old_settings_cannot_make_new_host_green(tools, settings, qtbot):
    started, finish = Event(), Event()
    settings.setValue('obs_studio/host', 'old-obs')

    def connect(host, port, password):
        if host == 'old-obs':
            started.set()
            finish.wait(3)
            return MagicMock()
        raise ConnectionError('New host is unavailable')

    with patch('openlp.plugins.obs_studio.lib.obs_studio_api.ObsStudioAPI', side_effect=connect) as api:
        try:
            tools.test_obs()
            qtbot.waitUntil(started.is_set)
            settings.setValue('obs_studio/host', 'new-obs')
            tools.refresh_obs()
        finally:
            finish.set()
        qtbot.waitUntil(lambda: api.call_count == 2 and not tools.obs_busy)
    assert not is_green(tools)
    assert 'Test passed' not in tools.window.status_bar.currentMessage()

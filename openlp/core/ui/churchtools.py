"""Service checks, local backups and OBS status for church operators."""
from datetime import datetime
from contextlib import closing
import logging
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import zipfile

from PySide6 import QtCore, QtGui, QtWidgets
from openlp.core.common.applocation import AppLocation
from openlp.core.common.registry import Registry
from openlp.core.state import State

log = logging.getLogger(__name__)


def check_service(entries):
    """Inspect the current in-memory service without modifying it."""
    issues = []
    if not entries:
        return ['The service is empty. Add your songs and other items.']
    for index, entry in enumerate(entries, 1):
        item = entry['service_item']
        title = f'{index}. {item.title or "Untitled item"}'
        if item.is_text():
            pages = [page for page in getattr(item, '_preview_slides', []) if 'hidden' in page and 'verse' in page
                     and not (page.get('verse') == '' and not page.get('hidden'))]
            if pages and all(page.get('hidden', False) for page in pages):
                issues.append(f'{title}: all slides are hidden.')
            if not any(str(slide.get('text', '')).strip() for slide in item.slides):
                issues.append(f'{title}: no text content.')
        else:
            for frame in item.get_frames():
                path = item.get_frame_path(frame=frame)
                if path and not Path(path).is_file():
                    issues.append(f'{title}: missing file: {path}')
        theme = None
        if item.is_text():
            from openlp.core.common import ThemeLevel
            settings = Registry().get('settings')
            manager = Registry().get('theme_manager')
            name = manager.global_theme
            level = settings.value('themes/theme level')
            if level != ThemeLevel.Global:
                name = settings.value('servicemanager/service theme') or name
            if level == ThemeLevel.Song:
                name = item.theme or name
            theme = manager.get_theme_data(name)
        if theme and getattr(theme, 'background_type', '') in ('image', 'video'):
            path = getattr(theme, 'background_filename', '')
            if path and not Path(path).is_file():
                issues.append(f'{title}: missing theme background: {path}')
    return issues


def create_backup(data_path, settings_path, service_path=None, force=False):
    """Archive local data, using SQLite snapshots for databases and atomic completion."""
    data_path = Path(data_path).resolve()
    backup_dir = data_path.parent / 'Backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    if not force and list(backup_dir.glob(f'OpenLP-{now:%Y-%m-%d}-*.zip')):
        return None
    target = backup_dir / f'OpenLP-{now:%Y-%m-%d-%H%M%S-%f}.zip'
    pending = target.with_suffix('.partial')
    try:
        with tempfile.TemporaryDirectory() as scratch, zipfile.ZipFile(
                pending, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in data_path.rglob('*'):
                relative = path.relative_to(data_path)
                if (not path.is_file() or path.is_symlink() or
                        any(part.lower() in ('backups', 'web_cache', 'cache', '__pycache__')
                            for part in relative.parts) or path.name.endswith(('-wal', '-shm', '-journal'))):
                    continue
                destination = 'Data/' + relative.as_posix()
                if path.suffix.lower() in ('.sqlite', '.sqlite3', '.db'):
                    snapshot = Path(scratch) / 'snapshot.sqlite'
                    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=2)) as source:
                        with closing(sqlite3.connect(snapshot)) as output:
                            source.backup(output)
                    archive.write(snapshot, destination)
                    snapshot.unlink()
                else:
                    archive.write(path, destination)
            if settings_path and Path(settings_path).is_file():
                archive.write(settings_path, 'Settings/OpenLP.ini')
            if service_path and Path(service_path).is_file():
                archive.write(service_path, 'Service/' + Path(service_path).name)
            archive.writestr('RESTORE.txt', 'Close OpenLP before restoring. Data contains the library and themes; '
                             'Settings/OpenLP.ini contains settings. Service contains the last saved current service, '
                             'if available. Unsaved service edits and media outside the data folder are not included. '
                             'Keep backups private: settings can contain connection passwords.\n')
        with zipfile.ZipFile(pending) as archive:
            if archive.testzip() is not None:
                raise OSError('Backup verification failed')
        pending.replace(target)
        for old in sorted(backup_dir.glob('OpenLP-*.zip'), reverse=True)[14:]:
            old.unlink()
        return target
    finally:
        pending.unlink(missing_ok=True)


class ChurchTools(QtCore.QObject):
    backup_done = QtCore.Signal(str, bool)
    obs_done = QtCore.Signal(str, bool)

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.backup_busy = False
        self.obs_busy = False
        self.obs_result = ''
        self.obs_reachable = None
        self.obs_monitoring = False
        self.obs_next_check = 0
        self.obs_result_settings = None
        self.obs_testing_settings = None
        self.obs_show_result = True
        self.backup_done.connect(self.on_backup_done)
        self.obs_done.connect(self.on_obs_done)
        for title, callback in [('Ready for Sunday', self.readiness), ('Back up now', lambda: self.backup(True)),
                                ('Open backup folder', self.open_backups), ('Test OBS connection', self.test_obs)]:
            action = QtGui.QAction(title, window)
            action.triggered.connect(callback)
            window.tools_menu.addAction(action)
        self.obs_button = QtWidgets.QToolButton(window)
        self.obs_button.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self.obs_button.setIconSize(QtCore.QSize(24, 24))
        self.obs_button.setAutoRaise(True)
        self._obs_icons = {state: self.obs_icon(color) for state, color in
                           [('connected', '#43d17b'), ('disconnected', '#ff6262')]}
        self.obs_button.setToolTip('Click to test the saved OBS connection settings. No slide or scene is changed.')
        self.obs_button.clicked.connect(self.test_obs)
        window.status_bar.addPermanentWidget(self.obs_button)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh_obs)
        self.timer.start(1000)
        self.refresh_obs()

    @staticmethod
    def obs_icon(color):
        """Draw a scalable three-blade OBS-style connection symbol."""
        pixmap = QtGui.QPixmap(64, 64)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtGui.QPen(QtGui.QColor(color), 3))
        painter.drawEllipse(QtCore.QRectF(4, 4, 56, 56))
        painter.translate(32, 32)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(color))
        blade = QtGui.QPainterPath()
        blade.moveTo(0, -24)
        blade.cubicTo(22, -27, 29, -3, 14, 8)
        blade.cubicTo(19, -7, 7, -14, -3, -7)
        blade.cubicTo(-12, -1, -12, -17, 0, -24)
        for _ in range(3):
            painter.drawPath(blade)
            painter.rotate(120)
        painter.end()
        return QtGui.QIcon(pixmap)

    def listener(self):
        for plugin in State().list_plugins():
            if plugin.name == 'obs_studio':
                return getattr(plugin, 'message_listener', None)
        return None

    @staticmethod
    def obs_settings():
        settings = Registry().get('settings')
        return tuple(settings.value('obs_studio/' + key) for key in ('host', 'port', 'password'))

    def refresh_obs(self):
        listener = self.listener()
        current_settings = self.obs_settings()
        if self.obs_result_settings != current_settings:
            self.obs_reachable = None
            self.obs_result = ''
            self.obs_result_settings = current_settings
            self.obs_next_check = 0
        active = bool(listener and listener.is_active)
        connected = bool(active and listener.is_connected)
        reachable = self.obs_reachable if self.obs_reachable is not None else connected
        if self.obs_busy:
            text = 'Testing…'
        elif self.obs_reachable is True:
            text = 'Connected' if connected else 'Reachable'
        elif self.obs_reachable is False:
            text = self.obs_result
        elif active:
            text = 'Connected' if connected else 'Disconnected'
        else:
            text = 'Disabled'
        self.obs_button.setIcon(self._obs_icons['connected' if reachable else 'disconnected'])
        self.obs_button.setAccessibleName('OBS: ' + text)
        integration = 'Slide integration is enabled.' if active else 'Slide integration is disabled.'
        self.obs_button.setToolTip('OBS: ' + text + '\nGreen: connected or reachable. Red: unavailable or not checked.\n' +
                                  integration + '\nClick to test; connection checks then repeat every 15 seconds. '
                                  'This does not verify the outgoing stream.')
        if self.obs_monitoring and not self.obs_busy and time.monotonic() >= self.obs_next_check:
            self.test_obs(automatic=True)

    def test_obs(self, checked=False, *, automatic=False):
        if self.obs_busy:
            return
        self.obs_testing_settings = self.obs_settings()
        host, port, password = self.obs_testing_settings
        self.obs_monitoring = True
        self.obs_show_result = not automatic
        self.obs_busy = True
        self.refresh_obs()
        def run():
            from openlp.plugins.obs_studio.lib.obs_studio_api import ObsStudioAPI
            client = None
            try:
                client = ObsStudioAPI(host, int(port), password)
                result = 'Test passed (reachable)'
                success = True
            except Exception as error:
                log.warning('OBS connection test failed: %s', error)
                result = 'Test failed — check OBS settings'
                success = False
            finally:
                if client:
                    try:
                        client.disconnect()
                    except Exception:
                        log.debug('OBS test socket cleanup failed', exc_info=True)
            self.obs_done.emit(result, success)
        threading.Thread(target=run, daemon=True, name='OBS connection test').start()

    def on_obs_done(self, result, success):
        self.obs_busy = False
        if self.obs_testing_settings != self.obs_settings():
            self.obs_next_check = 0
            self.refresh_obs()
            return
        self.obs_result = result
        self.obs_reachable = success
        self.obs_result_settings = self.obs_testing_settings
        self.obs_next_check = time.monotonic() + 15
        self.refresh_obs()
        if self.obs_show_result:
            self.window.status_bar.showMessage(result, 15000)

    def readiness(self):
        manager = self.window.service_manager_contents
        issues = check_service(manager.service_items)
        if manager.is_modified():
            issues.append('The service has unsaved changes. Save it before service.')
        listener = self.listener()
        if listener and listener.is_active and not listener.is_connected:
            issues.append('OBS is not connected. Use Tools → Test OBS connection if OBS is needed.')
        dialog = QtWidgets.QDialog(self.window)
        dialog.setWindowTitle('Ready for Sunday')
        dialog.resize(720, 480)
        layout = QtWidgets.QVBoxLayout(dialog)
        text = QtWidgets.QPlainTextEdit(dialog)
        text.setReadOnly(True)
        summary = ('Check these before service:\n\n' + '\n\n'.join(issues)) if issues else 'No issues found in the current service.'
        text.setPlainText(summary + '\n\nAlso test the projector, audio and video playback on your actual equipment. '
                          'This check cannot verify external equipment or streaming output.')
        layout.addWidget(text)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close, dialog)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def open_backups(self):
        folder = AppLocation.get_data_path().parent / 'Backups'
        folder.mkdir(parents=True, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(folder)))

    def backup(self, force=False):
        if self.backup_busy:
            return
        settings = Registry().get('settings')
        settings.sync()
        data = AppLocation.get_data_path()
        settings_path = settings.fileName()
        service = self.window.service_manager_contents.file_name()
        self.backup_busy = True
        self.window.status_bar.showMessage('Saving backup…')
        def run():
            try:
                path = create_backup(data, settings_path, service, force)
                self.backup_done.emit('Backup: saved' if path else 'Backup: up to date', True)
            except Exception:
                log.exception('Automatic backup failed')
                self.backup_done.emit('Backup: failed — check log', False)
        threading.Thread(target=run, daemon=True, name='OpenLP backup').start()

    def on_backup_done(self, message, success):
        self.backup_busy = False
        self.window.status_bar.showMessage(message, 15000)

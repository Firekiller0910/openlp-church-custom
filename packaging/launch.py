"""Portable distribution launcher for OpenLP Custom on Windows and macOS."""
import os
import site
import sys
import sysconfig
import traceback
from pathlib import Path

base = Path(__file__).resolve().parent
os.environ['QT_API'] = 'pyside6'
if sys.platform == 'win32':
    packages = base / 'runtime' / 'deps'
    site.addsitedir(str(packages))
    sysconfig._INSTALL_SCHEMES[sysconfig.get_default_scheme()]['purelib'] = str(packages)
    default_data = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))) / 'OpenLP Custom'
    data = Path(os.environ.get('OPENLP_CUSTOM_TEST_DATA', str(default_data))).resolve()
    for variable, folder in [('APPDATA', 'Roaming'), ('LOCALAPPDATA', 'Local')]:
        location = data / folder
        location.mkdir(parents=True, exist_ok=True)
        os.environ[variable] = str(location)
else:
    packages = base / 'runtime' / 'lib' / 'python3.11' / 'site-packages'
    site.addsitedir(str(packages))
    data = Path.home() / 'Library' / 'Application Support' / 'OpenLP Custom'

# A separate profile can be used for package verification without touching user data.
if os.environ.get('OPENLP_CUSTOM_TEST_DATA'):
    data = Path(os.environ['OPENLP_CUSTOM_TEST_DATA']).resolve()
source = base / 'source'
sys.path.insert(0, str(source))
os.chdir(source)
(data / 'Data').mkdir(parents=True, exist_ok=True)
(data / 'Other').mkdir(parents=True, exist_ok=True)
log = (data / 'Other' / 'startup.log').open('a', encoding='utf-8', buffering=1)
sys.stdout = log
sys.stderr = log
try:
    from PySide6 import QtCore
    from openlp.core.common.settings import Settings
    from openlp.core.server import Server
    from openlp.core.ui.style import UiThemes
    from openlp.core.version import get_version
    from openlp.core.app import main

    Settings.setDefaultFormat(Settings.IniFormat)
    Settings.set_filename(data / 'Data' / 'OpenLP.ini')
    settings = Settings()
    if not settings.contains('core/has run wizard'):
        settings.setValue('settings/version', 4)
        settings.setValue('core/has run wizard', True)
        settings.setValue('core/application version', get_version()['version'])
        settings.setValue('core/show splash', False)
        settings.setValue('core/update check', False)
        settings.setValue('api/update check', False)
        settings.setValue('songs/status', 1)
    if not QtCore.QSettings.value(settings, 'custom/navy appearance applied', False, type=bool):
        settings.setValue('advanced/ui_theme_name', UiThemes.QDarkStyle)
        QtCore.QSettings.setValue(settings, 'custom/navy appearance applied', True)
    settings.sync()

    original_server_init = Server.__init__
    def custom_server_init(self):
        original_server_init(self)
        self.id = 'OpenLP-Custom-Edition'
    Server.__init__ = custom_server_init
    sys.argv = ['OpenLP Custom', '--portable', '--portable-path', str(data), '--no-web-server']
    main()
except Exception:
    traceback.print_exc()
    raise

from pathlib import Path
import zipfile,json,hashlib,subprocess
source=Path('outputs/OpenLP-Test/source-modern')
runtime=Path('outputs/OpenLP-Test/runtime')
root='OpenLP Custom Windows/'
readme='''OPENLP CUSTOM — WINDOWS 10/11 (64-BIT)

1. Extract the entire ZIP to a folder on your PC.
2. Open that folder and double-click OpenLP Custom.exe.
3. Keep runtime, source and launch.py beside the EXE. No separate Python installation is needed.

Includes the dark navy/blue interface, compact eye button, gray hidden slides, skip navigation, remembered per-song choices for future services, Preview-to-Live persistence, and the newer upstream SongSelect source.

This is a separate customized application. Its songs and settings are stored under:
    %LOCALAPPDATA%\\OpenLP Custom
Your current test copy and normal OpenLP installation keep their own data. Export/import songs or services to move material between copies. This package does not synchronize PCs.

First run starts with an empty library. File > Import > CCLI SongSelect opens the upstream SongSelect importer. Other plugins can be enabled in OpenLP's plugin settings.

The EXE launcher is unsigned. The application code and Windows Qt interface were tested locally. This is a portable ZIP, not an MSI installer.
Logs: %LOCALAPPDATA%\\OpenLP Custom\\Other\\startup.log and openlp.log.

OpenLP is GPL-3.0-or-later. Full customized source and its LICENSE are included in source/. Runtime libraries retain their bundled licenses. The C# launcher source is included in packaging/.
'''
with zipfile.ZipFile('outputs/OpenLP-Custom-Windows-x64.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for path in runtime.rglob('*'):
  if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
   relative=path.relative_to(runtime).as_posix()
   if relative=='python311._pth':
    z.writestr(root+'runtime/'+relative,path.read_text().replace('../source-modern','../source'))
   else: z.write(path,root+'runtime/'+relative)
 for path in source.rglob('*'):
  if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc','.rej','.orig'):
   z.write(path,root+'source/'+path.relative_to(source).as_posix())
 z.write('work/distributions/launch.py',root+'launch.py')
 z.write('work/distributions/windows-launcher/OpenLP Custom.exe',root+'OpenLP Custom.exe')
 z.write('work/distributions/windows-launcher/Launcher.cs',root+'packaging/Launcher.cs')
 z.writestr(root+'READ ME.txt',readme)
Path('work/distributions/windows-readme.txt').write_text(readme,encoding='utf-8')
with zipfile.ZipFile('outputs/OpenLP-Custom-Windows-x64.zip') as z:
 assert z.testzip() is None
 assert not any('TestData/' in name for name in z.namelist())
 print('Windows ZIP verified:',Path('outputs/OpenLP-Custom-Windows-x64.zip').stat().st_size,'bytes',flush=True)

from pathlib import Path, PurePosixPath
import zipfile, tarfile, json, hashlib, stat, plistlib, posixpath

work=Path('work/distributions')
source=Path('outputs/OpenLP-Test/source-modern')
output=Path('outputs/OpenLP-Custom-macOS-Apple-Silicon.zip')
app='OpenLP Custom.app/'
resources=app+'Contents/Resources/'
site_packages=resources+'runtime/lib/python3.11/site-packages/'
readme='''OPENLP CUSTOM — APPLE SILICON MAC (M1/M2/M3/M4 OR NEWER)

Requires macOS 13 or later. This ZIP contains a native ARM64 Python runtime and Qt 6.10.3 universal libraries; no separate Python installation is needed.

1. Unzip the download using Finder/Archive Utility on your Mac.
2. Drag OpenLP Custom.app to Applications.
3. Open OpenLP Custom.app.

This is an unsigned, unnotarized custom app assembled on Windows. Its macOS launch has NOT been tested. If macOS blocks it, use System Settings > Privacy & Security > Open Anyway if available for this app. Do not disable Gatekeeper globally. A signed/notarized installer would require a Mac and Apple Developer signing credentials.

The customized source has passed the Windows Qt app tests, including the navy/blue appearance, hidden slide labels, skipped navigation, remembered per-song choices, service additions and Preview-to-Live behavior. The newer upstream SongSelect source is unchanged. Sign-in still needs testing on the Mac.

Your Mac's songs and settings are saved separately under:
    ~/Library/Application Support/OpenLP Custom
Logs are in its Other folder. The app starts with an empty library. Import your exported OpenLP songs/services or use File > Import > CCLI SongSelect. This package does not synchronize computers.

Some optional presentation integrations require their corresponding applications. Optional ICU sorting is not bundled; OpenLP's built-in locale sorting fallback is used.

OpenLP is GPL-3.0-or-later. Full customized source and LICENSE are inside OpenLP Custom.app/Contents/Resources/source. Python and bundled wheels retain their licenses. Runtime/dependency provenance is in Contents/Resources/package-manifest.json.
'''
manifest={
 'platform':'macOS Apple silicon (arm64), macOS 13+',
 'upstream_commit':'19b5f21f167dd4ebf981ccb92a7e1c9edd853c30',
 'python':json.loads((work/'mac-python-asset.json').read_text(encoding='utf-8-sig')),
 'wheels':[], 'mac_launch_verified':False
}
main_script='''#!/bin/sh
set -eu
CONTENTS=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec "$CONTENTS/Resources/runtime/bin/python3" -I "$CONTENTS/Resources/launch.py" "$@"
'''
info={'CFBundleName':'OpenLP Custom','CFBundleDisplayName':'OpenLP Custom',
      'CFBundleIdentifier':'org.openlp.custom','CFBundleExecutable':'OpenLPCustom',
      'CFBundlePackageType':'APPL','CFBundleShortVersionString':'3.1.99',
      'CFBundleVersion':'2026.10.21','LSMinimumSystemVersion':'13.0',
      'CFBundleIconFile':'OpenLP.icns','NSHighResolutionCapable':True,
      'NSRequiresAquaSystemAppearance':False,
      'LSArchitecturePriority':['arm64']}
written=set()
def write_bytes(z,name,data,mode=stat.S_IFREG|0o644):
 assert name not in written,name
 assert not name.startswith('/') and '..' not in PurePosixPath(name).parts,name
 entry=zipfile.ZipInfo(name)
 entry.create_system=3
 entry.external_attr=mode<<16
 entry.compress_type=zipfile.ZIP_DEFLATED
 z.writestr(entry,data,compresslevel=6)
 written.add(name)

def add_file(z,path,name,mode=stat.S_IFREG|0o644):
 write_bytes(z,name,path.read_bytes(),mode)

wheels=sorted((work/'mac-wheels').glob('*.whl'))
assert len(wheels)>25, 'Mac dependency download is incomplete'
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
 write_bytes(z,'READ ME - Mac.txt',readme.encode())
 write_bytes(z,app+'Contents/Info.plist',plistlib.dumps(info))
 write_bytes(z,app+'Contents/MacOS/OpenLPCustom',main_script.encode(),stat.S_IFREG|0o755)
 add_file(z,work/'OpenLP.icns',resources+'OpenLP.icns')
 add_file(z,work/'launch.py',resources+'launch.py')
 for path in source.rglob('*'):
  if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc','.orig','.rej'):
   add_file(z,path,resources+'source/'+path.relative_to(source).as_posix())
 with tarfile.open(work/'mac-python.tar.gz','r:gz') as runtime:
  for entry in runtime:
   if entry.isdir(): continue
   relative=PurePosixPath(entry.name).relative_to('python').as_posix()
   name=resources+'runtime/'+relative
   if entry.issym():
    target=posixpath.normpath(posixpath.join(posixpath.dirname(relative),entry.linkname))
    assert not target.startswith('../') and not entry.linkname.startswith('/'),entry.name
    write_bytes(z,name,entry.linkname.encode(),stat.S_IFLNK|0o777)
   elif entry.isfile() or entry.islnk():
    write_bytes(z,name,runtime.extractfile(entry).read(),stat.S_IFREG|(entry.mode&0o777))
 for wheel in wheels:
  manifest['wheels'].append({'name':wheel.name,'sha256':hashlib.sha256(wheel.read_bytes()).hexdigest()})
  with zipfile.ZipFile(wheel) as package:
   for entry in package.infolist():
    if entry.is_dir(): continue
    rel=entry.filename
    if '.data/' in rel:
     prefix,rel=rel.split('.data/',1)
     category,rel=rel.split('/',1)
     if category not in ('purelib','platlib'): continue
    name=site_packages+rel
    mode=entry.external_attr>>16
    if not stat.S_IFMT(mode): mode=stat.S_IFREG|(mode&0o777 or 0o644)
    if name in written:
     # Wheels must not overwrite Python runtime files or each other's modules.
     if z.read(name) == package.read(entry):
      continue
     raise RuntimeError('Conflicting packaged file: '+name)
    write_bytes(z,name,package.read(entry),mode)
 write_bytes(z,resources+'package-manifest.json',json.dumps(manifest,indent=2).encode())
 print('Mac bundle assembled; validating archive...',flush=True)
with zipfile.ZipFile(output) as z:
 assert z.testzip() is None
 launcher=z.getinfo(app+'Contents/MacOS/OpenLPCustom')
 assert (launcher.external_attr>>16)&0o111
 assert stat.S_ISLNK(z.getinfo(resources+'runtime/bin/python3').external_attr>>16)
 assert z.read(resources+'runtime/bin/python3')==b'python3.11'
 assert z.read(resources+'source/openlp/core/lib/songvisibility.py')==(source/'openlp/core/lib/songvisibility.py').read_bytes()
 assert plistlib.loads(z.read(app+'Contents/Info.plist'))['LSMinimumSystemVersion']=='13.0'
 expected=site_packages+'PySide6/Qt/lib/QtWebEngineCore.framework/Versions/A/Helpers/QtWebEngineProcess.app/Contents/MacOS/QtWebEngineProcess'
 helpers=[item for item in z.infolist() if item.filename.endswith('/MacOS/QtWebEngineProcess')]
 assert helpers,'QtWebEngine helper missing'
 assert all((item.external_attr>>16)&0o111 for item in helpers),'QtWebEngine helper not executable'
 print('Mac archive verified:',output.stat().st_size,'bytes; native launch still needs a Mac.',flush=True)
(work/'mac-readme.txt').write_text(readme,encoding='utf-8')

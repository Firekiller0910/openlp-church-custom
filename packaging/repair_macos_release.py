"""Repair the existing ARM64 Mac release without external build staging files.

Download the published ZIP and py-applescript wheels for CPython 3.11/macOS
ARM64 (including dependencies), then pass their paths to this script.
Native launch and automation must still be verified on a Mac.
"""
import argparse
import hashlib
import json
import plistlib
import shutil
import stat
import zipfile
from pathlib import Path
from urllib.request import urlopen


PREFIX = 'OpenLP Custom.app/Contents/'
RESOURCES = PREFIX + 'Resources/'
PACKAGES = RESOURCES + 'runtime/lib/python3.11/site-packages/'
REQUIRED = {'py-applescript', 'pyobjc-core', 'pyobjc-framework-cocoa',
            'pyobjc-framework-applescriptkit', 'pyobjc-framework-applescriptobjc'}


def repair(original, wheel_dir, output):
    if original.resolve() == output.resolve():
        raise ValueError('The original archive must be preserved')
    additions = {}
    wheel_records = []
    found = set()
    for wheel in sorted(wheel_dir.glob('*.whl')):
        project, version = wheel.name.split('-')[:2]
        project = project.replace('_', '-').lower()
        if project not in REQUIRED:
            raise ValueError(f'Unexpected dependency: {wheel.name}')
        with urlopen(f'https://pypi.org/pypi/{project}/{version}/json', timeout=30) as response:
            release = json.load(response)
        digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
        expected = next(item['digests']['sha256'] for item in release['urls']
                        if item['filename'] == wheel.name)
        if digest != expected:
            raise ValueError(f'Wheel checksum mismatch: {wheel.name}')
        found.add(project)
        wheel_records.append({'name': wheel.name, 'sha256': digest})
        with zipfile.ZipFile(wheel) as archive:
            if archive.testzip() is not None:
                raise ValueError(f'Corrupt wheel: {wheel.name}')
            for entry in archive.infolist():
                if entry.is_dir():
                    continue
                relative = Path(entry.filename)
                if (relative.is_absolute() or '..' in relative.parts or
                        any(part.endswith('.data') for part in relative.parts)):
                    raise ValueError(f'Unsupported wheel path: {entry.filename}')
                additions[PACKAGES + entry.filename] = archive.read(entry)
    if found != REQUIRED:
        raise ValueError(f'Missing automation dependencies: {REQUIRED - found}')
    with zipfile.ZipFile(original) as source:
        manifest = json.loads(source.read(RESOURCES + 'package-manifest.json'))
        # Keep the already bundled native bridge/Cocoa versions consistent.
        old_versions = {item['name'].split('-')[0]: item['name'].split('-')[1]
                        for item in manifest['wheels']}
        for item in wheel_records:
            name, version = item['name'].split('-')[:2]
            if name in old_versions and old_versions[name] != version:
                raise ValueError(f'Wheel version must match existing runtime: {name}')
        launcher = source.read(RESOURCES + 'launch.py')
        if b"'--no-web-server'" not in launcher:
            raise ValueError('Expected disabled-server launcher was not found')
        additions[RESOURCES + 'launch.py'] = launcher.replace(b", '--no-web-server'", b'')
        info = plistlib.loads(source.read(PREFIX + 'Info.plist'))
        info['NSAppleEventsUsageDescription'] = 'OpenLP controls Keynote and PowerPoint to present your slides.'
        info['CFBundleVersion'] = '2026.10.25'
        additions[PREFIX + 'Info.plist'] = plistlib.dumps(info)
        replacement_projects = {item['name'].split('-')[0] for item in wheel_records}
        manifest['wheels'] = [item for item in manifest['wheels']
                             if item['name'].split('-')[0] not in replacement_projects] + wheel_records
        manifest['repair'] = 'Enable remote servers and bundle Keynote AppleScript support'
        with original.open('rb') as original_file:
            manifest['original_archive_sha256'] = hashlib.file_digest(original_file, 'sha256').hexdigest()
        manifest['mac_launch_verified'] = False
        additions[RESOURCES + 'package-manifest.json'] = json.dumps(manifest, indent=2).encode()
        readme = source.read('READ ME - Mac.txt').decode()
        readme += ('\nREMOTE / KEYNOTE REPAIR\nRemote HTTP and WebSocket servers are enabled. '
                   'In Remote Interface settings, install the remote client if not installed, '
                   'then use the displayed URL on the same network. Allow local-network firewall access.\n'
                   'Keynote automation dependencies are bundled. Open Keynote once, restart OpenLP, '
                   'and enable Keynote under Presentations. Allow macOS Automation for Keynote/System Events '
                   'and Accessibility when requested. Keynote 10.1 or newer is required.\n'
                   'Quit OpenLP and replace the application in Applications. Your existing songs/settings '
                   'remain in Application Support. This repaired bundle still needs native Mac testing.\n')
        additions['READ ME - Mac.txt'] = readme.encode()
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as target:
            for entry in source.infolist():
                if entry.filename in additions:
                    target.writestr(entry, additions.pop(entry.filename))
                else:
                    with source.open(entry) as reader, target.open(entry, 'w') as writer:
                        shutil.copyfileobj(reader, writer, 1024 * 1024)
            for name, content in additions.items():
                entry = zipfile.ZipInfo(name)
                entry.create_system = 3
                entry.external_attr = (stat.S_IFREG | 0o644) << 16
                entry.compress_type = zipfile.ZIP_DEFLATED
                target.writestr(entry, content)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert b'--no-web-server' not in archive.read(RESOURCES + 'launch.py')
        for module in ('applescript/__init__.py', 'AppleScriptKit/__init__.py',
                       'AppleScriptObjC/__init__.py', 'objc/__init__.py', 'Foundation/__init__.py'):
            assert PACKAGES + module in archive.namelist(), module
        assert plistlib.loads(archive.read(PREFIX + 'Info.plist'))['NSAppleEventsUsageDescription']
        assert stat.S_ISLNK(archive.getinfo(RESOURCES + 'runtime/bin/python3').external_attr >> 16)
        assert archive.getinfo(PREFIX + 'MacOS/OpenLPCustom').external_attr >> 16 & 0o111
    print(f'Archive verified: {output}; native Mac launch remains unverified.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original', type=Path)
    parser.add_argument('wheel_dir', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    repair(args.original, args.wheel_dir, args.output)

"""Wrap a verified Apple silicon app ZIP in a flat macOS Installer package.

Requires cpio, gzip, xar and mkbom (bomutils on Linux, Apple tools on macOS).
The package installs only /Applications/OpenLP Custom.app, with no scripts.
"""
import argparse
import gzip
import hashlib
import os
import plistlib
import shutil
import stat
import struct
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


APP = 'OpenLP Custom.app'
IDENTIFIER = 'org.openlp.custom.installer'


def xml_file(path, root):
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)


def verify_bom(bom, root):
    """Read the BOM tree independently and compare all installed paths/metadata."""
    data = bom.read_bytes()
    magic, version, _, index, _, variables, _ = struct.unpack_from('>8s6I', data)
    if magic != b'BOMStore' or version != 1:
        raise ValueError('Invalid BOM header')
    count = struct.unpack_from('>I', data, index)[0]
    blocks = [struct.unpack_from('>II', data, index + 4 + i * 8) for i in range(count)]

    def block(number):
        offset, size = blocks[number]
        if offset + size > len(data):
            raise ValueError('BOM block exceeds file')
        return data[offset:offset + size]

    position = variables + 4
    tree = None
    for _ in range(struct.unpack_from('>I', data, variables)[0]):
        number, length = struct.unpack_from('>IB', data, position)
        name = data[position + 5:position + 5 + length]
        position += 5 + length
        if name == b'Paths':
            tree = block(number)
    if tree is None:
        raise ValueError('BOM has no Paths tree')
    _, _, child, _, expected_count = struct.unpack_from('>4s4I', tree)
    node = block(child)
    while struct.unpack_from('>H', node)[0] == 0:
        node = block(struct.unpack_from('>I', node, 12)[0])
    names = {}
    delivered = set()
    visited = set()
    while True:
        leaf, count, forward, _ = struct.unpack_from('>HHII', node)
        if leaf != 1:
            raise ValueError('Invalid BOM leaf')
        for i in range(count):
            entry, file = struct.unpack_from('>II', node, 12 + i * 8)
            identity, info = struct.unpack_from('>II', block(entry))
            file = block(file)
            parent = struct.unpack_from('>I', file)[0]
            name = os.fsdecode(file[4:].rstrip(b'\0'))
            path = names[parent] / name if parent else root / name
            if identity in names or not path.is_relative_to(root):
                raise ValueError('Invalid BOM path identity')
            names[identity] = path
            details = block(info)
            mode, uid, gid = struct.unpack_from('>HII', details, 4)
            if uid != 0 or gid != 80 or mode != path.lstat().st_mode:
                raise ValueError(f'BOM metadata mismatch: {path}')
            if path.is_symlink():
                length = struct.unpack_from('>I', details, 27)[0]
                target = details[31:31 + length].rstrip(b'\0')
                if os.fsdecode(target) != os.readlink(path):
                    raise ValueError(f'BOM symlink mismatch: {path}')
            delivered.add(path)
        if not forward:
            break
        if forward in visited:
            raise ValueError('BOM leaf cycle')
        visited.add(forward)
        node = block(forward)
    if len(delivered) != expected_count or delivered != {root, *root.rglob('*')}:
        raise ValueError('BOM does not describe the complete payload')
    print(f'BOM verified: {len(delivered)} installed paths', flush=True)


def build(args):
    if args.work.exists():
        raise ValueError('Use a new work directory to preserve previous outputs')
    root = args.work / 'root'
    flat = args.work / 'flat'
    component = flat / 'OpenLPCustom.pkg'
    resources = flat / 'Resources'
    component.mkdir(parents=True)
    resources.mkdir()
    (root / 'Applications').mkdir(parents=True)
    with zipfile.ZipFile(args.archive) as archive:
        links = []
        for entry in archive.infolist():
            if not entry.filename.startswith(APP + '/'):
                continue
            relative = Path(entry.filename)
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Unsafe archive path')
            destination = root / 'Applications' / relative
            mode = entry.external_attr >> 16
            if stat.S_ISLNK(mode):
                links.append((destination, archive.read(entry).decode()))
            elif entry.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as reader, destination.open('wb') as writer:
                    shutil.copyfileobj(reader, writer, 1024 * 1024)
                destination.chmod(mode & 0o777 or 0o644)
        for destination, target in links:
            if not (destination.parent / target).resolve().is_relative_to(root.resolve()):
                raise ValueError('Symlink escapes installation payload')
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.symlink_to(target)
        readme = archive.read('READ ME - Mac.txt').decode()
    info = plistlib.loads((root / 'Applications' / APP / 'Contents/Info.plist').read_bytes())
    paths = [root] + sorted(root.rglob('*'))
    size = sum(p.lstat().st_size for p in paths if p.is_file() and not p.is_symlink())
    kb = (size + 1023) // 1024
    listing = args.work / 'payload-files'
    listing.write_bytes(b'\0'.join(os.fsencode('./' + str(p.relative_to(root))) for p in paths) + b'\0')
    print('Compressing installer payload...', flush=True)
    with listing.open('rb') as names, (component / 'Payload').open('wb') as output:
        cpio = subprocess.Popen([args.cpio, '--null', '-o', '--format=odc', '--owner=0:80', '--quiet'],
                                cwd=root, stdin=names, stdout=subprocess.PIPE)
        try:
            subprocess.run([args.compressor, '-n', '-6'], stdin=cpio.stdout, stdout=output, check=True)
        finally:
            cpio.stdout.close()
        if cpio.wait() != 0:
            raise RuntimeError('cpio failed')
    subprocess.run([args.mkbom, '-u', '0', '-g', '80', str(root), str(component / 'Bom')], check=True)
    verify_bom(component / 'Bom', root)
    package = ET.Element('pkg-info', {'format-version': '2', 'identifier': IDENTIFIER,
                                   'version': info['CFBundleVersion'], 'install-location': '/', 'auth': 'root'})
    ET.SubElement(package, 'payload', {'installKBytes': str(kb), 'numberOfFiles': str(len(paths))})
    bundles = ET.SubElement(package, 'bundle-version')
    ET.SubElement(bundles, 'bundle', {'id': info['CFBundleIdentifier'],
                  'CFBundleIdentifier': info['CFBundleIdentifier'], 'CFBundleVersion': info['CFBundleVersion'],
                  'CFBundleShortVersionString': info['CFBundleShortVersionString'],
                  'path': './Applications/' + APP})
    xml_file(component / 'PackageInfo', package)
    distribution = ET.Element('installer-gui-script', {'minSpecVersion': '2'})
    ET.SubElement(distribution, 'title').text = 'OpenLP Custom'
    ET.SubElement(distribution, 'options', {'customize': 'never', 'hostArchitectures': 'arm64'})
    ET.SubElement(distribution, 'domains', {'enable_anywhere': 'false', 'enable_currentUserHome': 'false',
                                         'enable_localSystem': 'true'})
    volume = ET.SubElement(distribution, 'volume-check')
    ET.SubElement(ET.SubElement(volume, 'allowed-os-versions'), 'os-version', {'min': '13.0'})
    ET.SubElement(distribution, 'readme', {'file': 'ReadMe.txt', 'mime-type': 'text/plain'})
    outline = ET.SubElement(distribution, 'choices-outline')
    ET.SubElement(outline, 'line', {'choice': 'openlp'})
    choice = ET.SubElement(distribution, 'choice', {'id': 'openlp', 'title': 'OpenLP Custom', 'visible': 'false'})
    ET.SubElement(choice, 'pkg-ref', {'id': IDENTIFIER})
    reference = ET.SubElement(distribution, 'pkg-ref', {'id': IDENTIFIER, 'version': info['CFBundleVersion'],
                                                     'installKBytes': str(kb), 'auth': 'Root'})
    reference.text = '#OpenLPCustom.pkg'
    xml_file(flat / 'Distribution', distribution)
    (resources / 'ReadMe.txt').write_text(
        'Quit OpenLP before installing. This installer places OpenLP Custom.app in /Applications.\n'
        'Your songs and settings in Application Support are preserved.\n'
        'Requires an Apple silicon Mac running macOS 13 or newer.\n'
        'This installer is unsigned and unnotarized; native installation still needs Mac testing.\n\n' + readme)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([args.xar, '--compression', 'none', '-cf', str(args.output.resolve()),
                    'Distribution', 'Resources', 'OpenLPCustom.pkg'], cwd=flat, check=True)
    # Decode the actual payload independently and verify every delivered file.
    print('Verifying every payload file and symlink...', flush=True)
    actual = set()
    with gzip.open(component / 'Payload', 'rb') as payload:
        while True:
            header = payload.read(76)
            if len(header) != 76 or header[:6] != b'070707':
                raise ValueError('Invalid odc payload header')
            name_size = int(header[59:65], 8)
            file_size = int(header[65:76], 8)
            mode = int(header[18:24], 8)
            uid, gid = int(header[24:30], 8), int(header[30:36], 8)
            name = os.fsdecode(payload.read(name_size)[:-1])
            if name == 'TRAILER!!!':
                break
            path = root / name
            if uid != 0 or gid != 80 or not path.is_relative_to(root):
                raise ValueError('Invalid payload ownership or path')
            digest = hashlib.sha256()
            remaining = file_size
            while remaining:
                data = payload.read(min(remaining, 1024 * 1024))
                if not data:
                    raise ValueError('Truncated payload')
                digest.update(data)
                remaining -= len(data)
            if stat.S_ISLNK(mode):
                expected = hashlib.sha256(os.fsencode(os.readlink(path))).digest()
            elif stat.S_ISREG(mode):
                with path.open('rb') as original:
                    expected = hashlib.file_digest(original, 'sha256').digest()
            else:
                expected = hashlib.sha256(b'').digest()
            if digest.digest() != expected or stat.S_IMODE(mode) != stat.S_IMODE(path.lstat().st_mode):
                raise ValueError(f'Payload differs from staged app: {name}')
            actual.add(path)
    if actual != set(paths):
        raise ValueError('Payload is missing staged files')
    print(f'Installer built and payload verified: {args.output}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('work', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--mkbom', default='mkbom')
    parser.add_argument('--cpio', default='cpio')
    parser.add_argument('--compressor', default='gzip', help='gzip-compatible compressor, e.g. pigz')
    parser.add_argument('--xar', default='xar')
    build(parser.parse_args())

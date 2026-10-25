"""Download checksum-pinned native Mac runtime inputs for package_macos.py."""
import concurrent.futures
import hashlib
import json
import shutil
import urllib.request
from pathlib import Path


def download(url, expected, destination):
    if destination.exists():
        with destination.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() == expected:
                return
    temporary = destination.with_suffix(destination.suffix + '.partial')
    digest = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=120) as response, temporary.open('wb') as output:
        while chunk := response.read(1024 * 1024):
            digest.update(chunk)
            output.write(chunk)
    if digest.hexdigest() != expected:
        temporary.unlink()
        raise ValueError(f'Checksum mismatch for {destination.name}')
    temporary.replace(destination)


def prepare():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'packaging/macos-runtime-manifest.json').read_text())
    work = root / 'work/distributions'
    wheels = work / 'mac-wheels'
    wheels.mkdir(parents=True, exist_ok=True)
    runtime = manifest['python']
    download(runtime['browser_download_url'], runtime['digest'].removeprefix('sha256:'), work / 'mac-python.tar.gz')
    (work / 'mac-python-asset.json').write_text(json.dumps(runtime, indent=2))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(download, item['url'], item['sha256'], wheels / item['name'])
                   for item in manifest['wheels']]
        for future in futures:
            future.result()
    shutil.copy2(root / 'packaging/OpenLP.icns', work / 'OpenLP.icns')
    shutil.copy2(root / 'packaging/launch.py', work / 'launch.py')
    print(f'Verified native runtime and {len(manifest["wheels"])} wheels', flush=True)


if __name__ == '__main__':
    prepare()

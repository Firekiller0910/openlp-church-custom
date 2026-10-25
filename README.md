# OpenLP Church Custom

A customized OpenLP with a navy interface, remembered hidden song slides, the upstream SongSelect login fix, responsive background OBS messaging, a red/green OBS indicator, and a Ready for Sunday check. Automatic backups are disabled; manual backups remain under Tools.

## Install on another computer

**[Download for Windows](https://github.com/Firekiller0910/openlp-church-custom/releases/latest/download/OpenLP-Custom-Windows-Setup.exe)** · **[Download for Apple silicon Mac](https://github.com/Firekiller0910/openlp-church-custom/releases/latest/download/OpenLP-Custom-macOS-Apple-Silicon.zip)** · **[All releases and instructions](https://github.com/Firekiller0910/openlp-church-custom/releases)**

Sign into your GitHub account to access this private repository and its downloads. Choose the package for your computer:

- **OpenLP-Custom-Windows-Setup.exe**: normal Windows installer. Run it and follow setup.
- **OpenLP-Custom-macOS-Apple-Silicon.zip**: unzip on an Apple silicon Mac and move the app to Applications. Requires macOS 13+. This unsigned Mac package still needs testing on a Mac.

The packages include Python and Qt. Windows packages have been launch-tested; installers are unsigned. Computer-specific settings, songs, services, OBS passwords and CCLI sessions are not included. Transfer your own songs/services separately.

## Source

The repository contains the customized application source. Runtime bundles and large installers belong in GitHub Releases, not Git commits. The files under packaging are the build scripts used in the original Windows workspace; they reference its runtime and output staging paths and require those inputs to reproduce a package.

Based on OpenLP upstream commit `19b5f21f167dd4ebf981ccb92a7e1c9edd853c30` ("Fix Settings and SongSelect Issues"). SongSelect source is preserved from that commit. OpenLP and these modifications remain GPL-3.0-or-later; see LICENSE and copyright.txt. Bundled dependency licenses are included with the release packages.

## Operator tools

- Use the eye button to hide/unhide song pages. Choices persist for future services.
- The OBS icon is green for a connected active integration and red otherwise. Click to test saved connection settings. This does not verify the outgoing stream.
- Tools → Ready for Sunday checks service content, media, backgrounds, and unsaved edits.
- Tools → Back up now creates a manual local backup. No automatic backups run.

## Remote interface and Keynote

The launcher enables the HTTP and WebSocket servers. In Settings → Configure OpenLP → Remote Interface, check both server statuses and install/update the remote client if it is not installed. Connect your phone or tablet to the same network and use the remote URL shown there. Allow OpenLP through the Mac firewall for your local network.

Keynote control requires macOS, Keynote 10.1 or later, and `py-applescript` in the Python runtime used by OpenLP. Source installations include this Mac-only dependency. When assembling the portable Mac app, include a `py-applescript` wheel and its dependencies matching the bundled Python 3.11 ARM64 runtime in `work/distributions/mac-wheels`; prepare platform-specific wheels on a Mac. The packager checks for the automation wheel before building. Its existing external runtime and staging inputs are still required.

On your Mac, open Keynote once, then restart OpenLP and enable Keynote under Settings → Configure OpenLP → Presentations. Accept the macOS request allowing OpenLP to control Keynote. Under System Settings → Privacy & Security, allow Automation for Keynote and System Events, and Accessibility when prompted for slide-window control.

These source changes require rebuilding and reinstalling the custom app; they do not update an already downloaded release. Keynote automation must be tested on macOS.

### Repair an existing Mac release

`packaging/repair_macos_release.py` can update the published Apple silicon ZIP without the original Windows staging directories. Download the original release ZIP, then download `py-applescript` and its dependencies for its bundled CPython 3.11 ARM64 runtime (keep the existing PyObjC version, currently 12.2.2):

```sh
python3 -m pip download --dest mac-wheels --platform macosx_13_0_arm64 --python-version 3.11 --implementation cp --abi cp311 --only-binary=:all: py-applescript pyobjc-core==12.2.2 pyobjc-framework-Cocoa==12.2.2 pyobjc-framework-AppleScriptKit==12.2.2 pyobjc-framework-AppleScriptObjC==12.2.2
python3 packaging/repair_macos_release.py original.zip mac-wheels OpenLP-Custom-macOS-Apple-Silicon-Fixed.zip
```

The repair verifies wheel hashes against PyPI, preserves the existing runtime and source, enables both remote servers, bundles all five automation dependencies, and adds the macOS automation usage description. It validates ZIP integrity, modules, launcher permissions, and the Python symlink. It does not sign/notarize the app or establish native Mac compatibility. Quit OpenLP before replacing the app in Applications; the existing Application Support profile stays in place. If Remote Interface says the web client is not installed, use its Install/Update button before opening the remote URL.

### Native Mac installer

To make a `.pkg` that installs the repaired app into `/Applications`, use:

```sh
python3 packaging/build_macos_installer.py OpenLP-Custom-macOS-Apple-Silicon-Fixed.zip build/mac-installer OpenLP-Custom-macOS-Apple-Silicon-Installer.pkg
```

The work directory must be new. This requires `cpio`, `gzip`, `xar`, and `mkbom` on PATH; explicit tool paths can be passed with `--cpio`, `--xar`, and `--mkbom`. On Linux, `mkbom` can be built from `hogliux/bomutils` (validated here at commit `c247002e2f49878bab32dd0fcf805810ae0992cb`). Before building bomutils on Linux, apply `packaging/bomutils-hidden-files.patch` with `git apply /path/to/openlp-church-custom/packaging/bomutils-hidden-files.patch` from its checkout, then run `make -j2`. This includes hidden files in the BOM and corrects its listing tool. The builder independently validates the entire BOM against the app. The build uses the flat Installer package format, a bill of materials, and a gzip-compressed odc payload. It verifies every payload file and symlink against the staged app. The Installer targets the system Applications folder on Apple silicon Macs running macOS 13 or newer. It has no installation scripts and does not include user songs, settings, or credentials.

Quit OpenLP, open the `.pkg`, and follow macOS Installer. Open OpenLP Custom from Applications afterward. This build is unsigned and unnotarized; macOS may require approval under Privacy & Security. Native installation and Keynote automation still require testing on a Mac. Signing/notarization requires a Mac and Apple Developer signing credentials.

### GitHub release builds

The `Build and publish Mac installer` GitHub Actions workflow rebuilds the Mac downloads after packaging changes on `main`, or through Run workflow. It downloads the native Python runtime and all dependency wheels from the checksum-pinned `packaging/macos-runtime-manifest.json`, then validates the app ZIP, installer payload, and complete BOM before uploading the installer and ZIP to `v0.1.0-custom`. It uses GitHub's built-in workflow token with repository contents write permission; no personal token is stored in the repository. The unsigned Mac installer and Keynote integration still require native Mac testing.

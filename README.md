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

Build script for gtui

Requirements:
  pip install pyinstaller

Windows:
  pyinstaller --onefile --name gtui.exe gtui.py

Linux:
  pyinstaller --onefile --name gtui gtui.py

AppImage:
  python-appimage build app --python-version 3.14 gtui.py

Debian:
  dpkg-deb --build deb gtui_1.0-1_all.deb

Arch Linux:
  makepkg -f

tar.zst:
  git archive --format=tar HEAD | zstd -o gtui.tar.zst

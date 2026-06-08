"""Create jans.app bundle in ~/Applications."""
import os
import shutil
import stat
from pathlib import Path

VENV    = Path.home() / "research/jans/.venv-menu"
REPO    = Path.home() / "research/jans"
APP_DIR = Path.home() / "Applications/jans.app"


def main():
    # Clean previous build
    if APP_DIR.exists():
        shutil.rmtree(APP_DIR)

    contents  = APP_DIR / "Contents"
    macos_dir = contents / "MacOS"
    resources = contents / "Resources"
    macos_dir.mkdir(parents=True)
    resources.mkdir(parents=True)

    # Info.plist
    (contents / "Info.plist").write_text(f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>             <string>jans</string>
    <key>CFBundleDisplayName</key>      <string>jans</string>
    <key>CFBundleIdentifier</key>       <string>com.jandro.jans</string>
    <key>CFBundleVersion</key>          <string>1.0</string>
    <key>CFBundleExecutable</key>       <string>jans</string>
    <key>CFBundleIconFile</key>         <string>jans</string>
    <key>CFBundlePackageType</key>      <string>APPL</string>
    <key>LSUIElement</key>              <false/>
    <key>NSHighResolutionCapable</key>  <true/>
    <key>LSMinimumSystemVersion</key>   <string>12.0</string>
</dict>
</plist>
""")

    # Launcher script
    launcher = macos_dir / "jans"
    launcher.write_text(f"""\
#!/bin/bash
exec "{VENV}/bin/python3" "{REPO}/jans/gui.py" "$@"
""")
    launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    # Icon
    icns_src = REPO / "jans.icns"
    if icns_src.exists():
        shutil.copy(icns_src, resources / "jans.icns")
        print(f"Icon copied.")
    else:
        print("WARNING: jans.icns not found, run make_icon.py first.")

    print(f"Created {APP_DIR}")
    print("To add to Dock: drag ~/Applications/jans.app onto the Dock.")


if __name__ == "__main__":
    main()

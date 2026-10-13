#!/bin/bash
# Build SportsPred.app (universal: Apple silicon + Intel) into mac/build/.
#   ./mac/build-app.sh            build the app
#   ./mac/build-app.sh --zip      also make mac/build/SportsPred.zip to share
set -euo pipefail
cd "$(dirname "$0")"
APP="build/SportsPred.app"

echo "Compiling…"
swift build -c release --arch arm64 --arch x86_64 >/dev/null
BIN="$(swift build -c release --arch arm64 --arch x86_64 --show-bin-path)/SportsPred"

echo "Assembling $APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/SportsPred"
cp Info.plist "$APP/Contents/Info.plist"

# app icon from AppIcon.svg
ICONSET="$(mktemp -d)/AppIcon.iconset"
mkdir -p "$ICONSET"
for size in 16 32 128 256 512; do
  sips -s format png -z $size $size AppIcon.svg --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
  sips -s format png -z $((size * 2)) $((size * 2)) AppIcon.svg --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns"

# ad-hoc signature so macOS will run it locally (not notarised)
codesign --force --deep --sign - "$APP" >/dev/null 2>&1

if [[ "${1:-}" == "--zip" ]]; then
  (cd build && rm -f SportsPred.zip && ditto -c -k --keepParent SportsPred.app SportsPred.zip)
  echo "Zipped: mac/build/SportsPred.zip"
fi
echo "Done: mac/$APP"

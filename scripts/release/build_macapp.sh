#!/usr/bin/env bash
# scripts/release/build_macapp.sh — wrap the SwiftPM-built TinyGPTApp binary into
# a proper .app bundle so it launches like any other Mac app (via Finder,
# Spotlight, `open posttrainllm.app`, dock pinning, etc.).
#
# SwiftPM only emits a raw Mach-O executable — perfectly runnable from
# the command line but not LaunchServices-friendly. This script copies
# the binary + its resource bundles + the MLX metallib into the right
# Contents/{MacOS,Resources} layout and writes an Info.plist that
# CFBundle/LaunchServices need.
#
# Usage:
#   ./scripts/release/build_macapp.sh                       # release build → ./build/posttrainllm.app
#   ./scripts/release/build_macapp.sh --debug               # debug build instead
#   ./scripts/release/build_macapp.sh --out /path/to/Apps   # custom output dir
#
# After running:
#   open ./build/posttrainllm.app                        # standard Mac launch
#   cp -r ./build/posttrainllm.app /Applications/        # install
#
# The default bundle is ad-hoc signed for local use. Set
# POSTTRAINLLM_SIGNING_IDENTITY to a complete Developer ID Application
# identity to produce a hardened, timestamped direct-distribution candidate.

set -euo pipefail

CONFIG="release"
OUT_DIR="$(pwd)/build"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --debug)   CONFIG="debug"; shift ;;
        --release) CONFIG="release"; shift ;;
        --out)     OUT_DIR="$2"; shift 2 ;;
        -h|--help)
            cat <<'HELP'
Usage: ./scripts/release/build_macapp.sh [--debug|--release] [--out DIRECTORY]

Environment:
  POSTTRAINLLM_SIGNING_IDENTITY  Developer ID Application identity; default is ad-hoc
  POSTTRAINLLM_BUNDLE_ID         Bundle identifier; default com.sassmaker.posttrainllm
  POSTTRAINLLM_VERSION           Semantic version; default 0.1.0
  POSTTRAINLLM_BUILD_NUMBER      Numeric bundle build; default 1
  POSTTRAINLLM_BUILD_JOBS        Serial Swift build by default; set a positive integer
HELP
            exit 0
            ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PKG="$REPO_ROOT/native-mac"
FINAL_APP="$OUT_DIR/posttrainllm.app"
BUNDLE_ID="${POSTTRAINLLM_BUNDLE_ID:-com.sassmaker.posttrainllm}"
SHORT_VERSION="${POSTTRAINLLM_VERSION:-0.1.0}"
BUILD_VERSION="${POSTTRAINLLM_BUILD_NUMBER:-1}"
SIGNING_IDENTITY="${POSTTRAINLLM_SIGNING_IDENTITY:--}"
BUILD_JOBS="${POSTTRAINLLM_BUILD_JOBS:-1}"

[[ "$BUILD_JOBS" =~ ^[1-9][0-9]*$ ]] || {
    echo "POSTTRAINLLM_BUILD_JOBS must be a positive integer" >&2
    exit 64
}

echo "== build (swift build -j $BUILD_JOBS -c $CONFIG --product TinyGPTApp)"
( cd "$PKG" && swift build -j "$BUILD_JOBS" -c "$CONFIG" --product TinyGPTApp )
BUILD_DIR="$(cd "$PKG" && swift build -c "$CONFIG" --show-bin-path)"

if [[ ! -x "$BUILD_DIR/TinyGPTApp" ]]; then
    echo "build did not produce $BUILD_DIR/TinyGPTApp" >&2
    exit 1
fi

STAGE_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/posttrainllm-package.XXXXXX")"
APP="$STAGE_ROOT/posttrainllm.app"
echo "== assemble bundle → $FINAL_APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cp "$BUILD_DIR/TinyGPTApp" "$APP/Contents/MacOS/posttrainllm"
chmod +x "$APP/Contents/MacOS/posttrainllm"

# Also build + bundle the CLI binary. The Interp tab shells out to it
# for SAE / MEMIT / patch training so the app doesn't have to duplicate
# the CLI's training paths in-process.
( cd "$PKG" && swift build -j "$BUILD_JOBS" -c "$CONFIG" --product posttrainllm )
if [[ -x "$BUILD_DIR/posttrainllm" ]]; then
    cp "$BUILD_DIR/posttrainllm" "$APP/Contents/MacOS/posttrainllm-cli"
    chmod +x "$APP/Contents/MacOS/posttrainllm-cli"
fi

# MLX needs its compiled Metal shader library at runtime. SwiftPM drops
# it next to the binary; the .app needs it in Resources so the binary's
# search path (which Foundation rewrites to the bundle when launched as
# an .app) finds it.
if [[ -f "$BUILD_DIR/mlx.metallib" ]]; then
    cp "$BUILD_DIR/mlx.metallib" "$APP/Contents/Resources/default.metallib"
    cp "$BUILD_DIR/mlx.metallib" "$APP/Contents/MacOS/mlx.metallib"
fi

# Resource bundles SwiftPM produces for swift-transformers + swift-crypto.
# Copy any *.bundle next to the binary into Resources/ so dynamic loader
# code finds them.
for b in "$BUILD_DIR"/*.bundle; do
    [[ -e "$b" ]] || continue
    cp -R "$b" "$APP/Contents/Resources/"
done

# App icon. Regenerated from browser/public/favicon.svg via
# scripts/release/make_icon.sh if missing.
ICON_SRC="$PKG/Resources/posttrainllm.icns"
if [[ ! -f "$ICON_SRC" ]]; then
    echo "== generating icon (scripts/release/make_icon.sh)"
    "$REPO_ROOT/scripts/release/make_icon.sh"
fi
if [[ -f "$ICON_SRC" ]]; then
    cp "$ICON_SRC" "$APP/Contents/Resources/posttrainllm.icns"
fi

# Info.plist — the minimum LaunchServices wants.
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>posttrainllm</string>
    <key>CFBundleDisplayName</key>
    <string>posttrainllm</string>
    <key>CFBundleIdentifier</key>
    <string>com.tinygpt.app</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>CFBundleShortVersionString</key>
    <string>0.1</string>
    <key>CFBundleExecutable</key>
    <string>posttrainllm</string>
    <key>CFBundleIconFile</key>
    <string>posttrainllm</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>14.0</string>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.developer-tools</string>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSSupportsAutomaticGraphicsSwitching</key>
    <true/>
    <key>NSHumanReadableCopyright</key>
    <string>posttrainllm — native macOS</string>
</dict>
</plist>
PLIST
plutil -replace CFBundleIdentifier -string "$BUNDLE_ID" "$APP/Contents/Info.plist"
plutil -replace CFBundleVersion -string "$BUILD_VERSION" "$APP/Contents/Info.plist"
plutil -replace CFBundleShortVersionString -string "$SHORT_VERSION" "$APP/Contents/Info.plist"

# PkgInfo — legacy but some macOS code paths still check for it.
echo -n "APPL????" > "$APP/Contents/PkgInfo"

echo "== codesign"
# Make every file in the bundle writable so codesign can write its
# extended-attribute signatures. SwiftPM hands the metallib over as
# read-only which trips codesign --force.
chmod -R u+w "$APP"
# Strip any inherited signatures on payload binaries before re-signing
# the whole bundle. Cleanest path.
codesign --remove-signature "$APP/Contents/MacOS/posttrainllm" 2>/dev/null || true
if [[ -x "$APP/Contents/MacOS/posttrainllm-cli" ]]; then
    codesign --remove-signature "$APP/Contents/MacOS/posttrainllm-cli" 2>/dev/null || true
fi
if [[ "$SIGNING_IDENTITY" == "-" ]]; then
    codesign --force --deep --options runtime --sign - "$APP" 2>&1 | sed 's/^/  /'
else
    codesign --force --deep --options runtime --timestamp --sign "$SIGNING_IDENTITY" "$APP" 2>&1 | sed 's/^/  /'
fi
codesign --verify --deep --strict --verbose=2 "$APP"

mkdir -p "$OUT_DIR"
if [[ -e "$FINAL_APP" ]]; then
    PREVIOUS_DIR="$OUT_DIR/previous-builds"
    PREVIOUS_NAME="posttrainllm-$(date +%Y%m%d-%H%M%S)-$$.app"
    mkdir -p "$PREVIOUS_DIR"
    mv "$FINAL_APP" "$PREVIOUS_DIR/$PREVIOUS_NAME"
fi
mv "$APP" "$FINAL_APP"
rmdir "$STAGE_ROOT"
APP="$FINAL_APP"

echo ""
echo "✓ wrote $APP"
echo "  size: $(du -sh "$APP" | cut -f1)"
echo ""
echo "launch with:  open \"$APP\""
echo "install with: cp -r \"$APP\" /Applications/"

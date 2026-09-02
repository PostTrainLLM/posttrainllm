#!/usr/bin/env bash
# Create the direct-distribution DMG, submit that exact container to Apple's
# notary service, staple its ticket, and verify both the DMG and nested app.
#
# Usage:
#   POSTTRAINLLM_NOTARY_PROFILE=posttrainllm-notary \
#     ./scripts/release/notarize-macapp.sh [app-path] [dmg-path]
#
# The app must already carry a timestamped Developer ID Application signature
# and hardened runtime. The script writes a JSON notary receipt beside the DMG
# and prints its SHA-256 after all trust gates pass. It never publishes a release.

set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    cat <<'HELP'
Usage: ./scripts/release/notarize-macapp.sh [APP_PATH] [DMG_PATH]

Requires POSTTRAINLLM_NOTARY_PROFILE to name an existing, validated notarytool
Keychain profile. Packages and notarizes the exact DMG, staples its ticket,
runs Gatekeeper against both DMG and app, saves the JSON receipt, and prints
the SHA-256. This command does not publish a GitHub release.
HELP
    exit 0
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_PATH="${1:-$REPO_ROOT/build/posttrainllm.app}"
NOTARY_PROFILE="${POSTTRAINLLM_NOTARY_PROFILE:-}"

[[ -d "$APP_PATH" ]] || { echo "missing app bundle: $APP_PATH" >&2; exit 1; }
[[ -n "$NOTARY_PROFILE" ]] || {
    echo "POSTTRAINLLM_NOTARY_PROFILE must name an existing notarytool Keychain profile" >&2
    exit 64
}

SIGNATURE_DETAILS="$(codesign -dv --verbose=4 "$APP_PATH" 2>&1)"
SIGNATURE_AUTHORITY="$(printf '%s\n' "$SIGNATURE_DETAILS" | sed -n 's/^Authority=//p' | head -1)"
[[ "$SIGNATURE_AUTHORITY" == Developer\ ID\ Application:* ]] || {
    echo "app is not signed with Developer ID Application: $APP_PATH" >&2
    exit 1
}

if [[ "$SIGNATURE_DETAILS" != *"flags="*"runtime"* ]]; then
    echo "app signature does not enable the hardened runtime: $APP_PATH" >&2
    exit 1
fi

VERSION="$(plutil -extract CFBundleShortVersionString raw "$APP_PATH/Contents/Info.plist")"
DMG_PATH="${2:-$(dirname "$APP_PATH")/posttrainllm-$VERSION-macOS.dmg}"
RECEIPT_PATH="${DMG_PATH%.dmg}.notary.json"

mkdir -p "$(dirname "$DMG_PATH")"
for existing in "$DMG_PATH" "$RECEIPT_PATH"; do
    if [[ -e "$existing" ]]; then
        PREVIOUS_DIR="$(dirname "$DMG_PATH")/previous-builds"
        mkdir -p "$PREVIOUS_DIR"
        mv "$existing" "$PREVIOUS_DIR/$(basename "$existing").$(date +%Y%m%d-%H%M%S)-$$"
    fi
done

echo "== package DMG → $DMG_PATH"
hdiutil create -quiet -format UDZO -volname "PostTrainLLM $VERSION" \
    -srcfolder "$APP_PATH" "$DMG_PATH"
codesign --force --timestamp --sign "$SIGNATURE_AUTHORITY" "$DMG_PATH"
codesign --verify --verbose=2 "$DMG_PATH"

echo "== submit exact DMG to Apple notary service"
xcrun notarytool submit "$DMG_PATH" \
    --keychain-profile "$NOTARY_PROFILE" \
    --wait \
    --output-format json > "$RECEIPT_PATH"
cat "$RECEIPT_PATH"

NOTARY_STATUS="$(plutil -extract status raw -o - "$RECEIPT_PATH")"
[[ "$NOTARY_STATUS" == "Accepted" ]] || {
    echo "notary service did not accept the DMG (status: $NOTARY_STATUS)" >&2
    exit 1
}

echo "== staple and validate"
xcrun stapler staple "$DMG_PATH"
xcrun stapler validate "$DMG_PATH"
spctl --assess --type open --context context:primary-signature --verbose=2 "$DMG_PATH"

MOUNT_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/posttrainllm-release-mount.XXXXXX")"
MOUNTED=false
cleanup_mount() {
    if [[ "$MOUNTED" == true ]]; then
        hdiutil detach -quiet "$MOUNT_ROOT" || true
    fi
    rmdir "$MOUNT_ROOT" 2>/dev/null || true
}
trap cleanup_mount EXIT
hdiutil attach -quiet -nobrowse -readonly -mountpoint "$MOUNT_ROOT" "$DMG_PATH"
MOUNTED=true
spctl --assess --type execute --verbose=2 "$MOUNT_ROOT/posttrainllm.app"
hdiutil detach -quiet "$MOUNT_ROOT"
MOUNTED=false
rmdir "$MOUNT_ROOT"
trap - EXIT

SHA256="$(shasum -a 256 "$DMG_PATH" | awk '{print $1}')"
echo ""
echo "✓ notarized direct-distribution artifact"
echo "  dmg: $DMG_PATH"
echo "  receipt: $RECEIPT_PATH"
echo "  sha256: $SHA256"

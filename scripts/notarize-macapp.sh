#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_PATH="${1:-$REPO_ROOT/build/posttrainllm.app}"
NOTARY_PROFILE="${POSTTRAINLLM_NOTARY_PROFILE:-}"

[[ -d "$APP_PATH" ]] || { echo "missing app bundle: $APP_PATH" >&2; exit 1; }
[[ -n "$NOTARY_PROFILE" ]] || {
    echo "POSTTRAINLLM_NOTARY_PROFILE must name an existing notarytool Keychain profile" >&2
    exit 64
}

SIGNATURE_AUTHORITY="$(codesign -dv --verbose=4 "$APP_PATH" 2>&1 | sed -n 's/^Authority=//p' | head -1)"
[[ "$SIGNATURE_AUTHORITY" == Developer\ ID\ Application:* ]] || {
    echo "app is not signed with Developer ID Application: $APP_PATH" >&2
    exit 1
}

SUBMISSION_ZIP="$(mktemp "${TMPDIR:-/tmp}/posttrainllm-notary.XXXXXX.zip")"
ditto -c -k --keepParent "$APP_PATH" "$SUBMISSION_ZIP"
xcrun notarytool submit "$SUBMISSION_ZIP" --keychain-profile "$NOTARY_PROFILE" --wait
xcrun stapler staple "$APP_PATH"
xcrun stapler validate "$APP_PATH"
spctl --assess --type execute --verbose=2 "$APP_PATH"
echo "$APP_PATH"

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Expected SHA-256 checksums for downloaded model artifacts
KOKORO_ONNX_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
KOKORO_ONNX_SHA256="7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5"

KOKORO_VOICES_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"
KOKORO_VOICES_SHA256="bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d"

VOSK_MODEL_NAME="vosk-model-small-es-0.42"
VOSK_ZIP_URL="https://alphacephei.com/vosk/models/${VOSK_MODEL_NAME}.zip"
VOSK_FINAL_MDL_SHA256="ff9508e4db01d2e2375da3887973f94ef8057ee85411f4cb10a5c174ce7a4425"
VOSK_README_SHA256="94132a6f5334701d8c0b4d25ef6890f74972909d8824c6c5974c41bca0542d88"

VERIFY_ONLY=false
if [[ "${1:-}" == "--verify-only" ]]; then
    VERIFY_ONLY=true
fi

compute_sha256() {
    local file_path="$1"
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$file_path" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$file_path" | awk '{print $1}'
    else
        echo "❌ Neither sha256sum nor shasum is installed." >&2
        exit 1
    fi
}

verify_sha256() {
    local file_path="$1"
    local expected="$2"
    if [[ ! -f "$file_path" ]]; then
        echo "❌ Missing file for checksum verification: $file_path" >&2
        return 1
    fi
    local actual
    actual="$(compute_sha256 "$file_path")"
    if [[ "$actual" != "$expected" ]]; then
        echo "❌ SHA-256 mismatch for $file_path" >&2
        echo "   expected: $expected" >&2
        echo "   actual:   $actual" >&2
        return 1
    fi
    echo "✓ Verified SHA-256 for $(basename "$file_path")"
}

ensure_binary_model() {
    local dest="$1"
    local url="$2"
    local expected_sha="$3"
    local tmp_file="${dest}.tmp"

    if [[ -f "$dest" ]]; then
        verify_sha256 "$dest" "$expected_sha"
        return 0
    fi

    if [[ "$VERIFY_ONLY" == true ]]; then
        echo "❌ Model missing in --verify-only mode: $dest" >&2
        return 1
    fi

    echo "Downloading $(basename "$dest") from $url..."
    rm -f "$tmp_file"
    curl --proto '=https' --tlsv1.2 -fsSL -o "$tmp_file" "$url"
    if ! verify_sha256 "$tmp_file" "$expected_sha"; then
        rm -f "$tmp_file"
        return 1
    fi
    mv "$tmp_file" "$dest"
}

echo "Verifying / downloading AI models required for Atenea Voice System..."

echo "-----------------------------------"
echo "1. Kokoro ONNX Text-To-Speech models"
VOICES_DIR="$ROOT_DIR/backend/voices"
mkdir -p "$VOICES_DIR"
ensure_binary_model "$VOICES_DIR/kokoro-v1.0.onnx" "$KOKORO_ONNX_URL" "$KOKORO_ONNX_SHA256"
ensure_binary_model "$VOICES_DIR/voices-v1.0.bin" "$KOKORO_VOICES_URL" "$KOKORO_VOICES_SHA256"

echo "-----------------------------------"
echo "2. Vosk Wake Word model ($VOSK_MODEL_NAME)"
VOSK_PARENT="$ROOT_DIR/backend/src/infrastructure/models/vosk"
VOSK_DIR="$VOSK_PARENT/$VOSK_MODEL_NAME"
mkdir -p "$VOSK_PARENT"

if [[ -d "$VOSK_DIR" ]]; then
    verify_sha256 "$VOSK_DIR/am/final.mdl" "$VOSK_FINAL_MDL_SHA256"
    verify_sha256 "$VOSK_DIR/README" "$VOSK_README_SHA256"
else
    if [[ "$VERIFY_ONLY" == true ]]; then
        echo "❌ Vosk model missing in --verify-only mode: $VOSK_DIR" >&2
        exit 1
    fi
    TMP_DIR="$(mktemp -d)"
    trap 'rm -rf "$TMP_DIR"' EXIT
    echo "Downloading ${VOSK_MODEL_NAME}.zip..."
    curl --proto '=https' --tlsv1.2 -fsSL -o "$TMP_DIR/${VOSK_MODEL_NAME}.zip" "$VOSK_ZIP_URL"
    unzip -q "$TMP_DIR/${VOSK_MODEL_NAME}.zip" -d "$TMP_DIR"
    verify_sha256 "$TMP_DIR/$VOSK_MODEL_NAME/am/final.mdl" "$VOSK_FINAL_MDL_SHA256"
    verify_sha256 "$TMP_DIR/$VOSK_MODEL_NAME/README" "$VOSK_README_SHA256"
    mv "$TMP_DIR/$VOSK_MODEL_NAME" "$VOSK_DIR"
    rm -rf "$TMP_DIR"
    trap - EXIT
fi

echo "-----------------------------------"
echo "All models verified and ready!"

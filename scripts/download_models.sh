#!/bin/bash
set -e

echo "Downloading AI models required for Atenea Voice System..."

# 1. Download Kokoro ONNX models
echo "-----------------------------------"
echo "Downloading Kokoro ONNX Text-To-Speech models..."
mkdir -p backend/voices
cd backend/voices

if [ ! -f "kokoro-v1.0.onnx" ]; then
    echo "Downloading kokoro-v1.0.onnx (approx 310MB)..."
    curl -L -o kokoro-v1.0.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
else
    echo "kokoro-v1.0.onnx already exists. Skipping."
fi

if [ ! -f "voices-v1.0.bin" ]; then
    echo "Downloading voices-v1.0.bin (approx 28MB)..."
    curl -L -o voices-v1.0.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
else
    echo "voices-v1.0.bin already exists. Skipping."
fi

cd ../..

# 2. Download Vosk Wake Word model
echo "-----------------------------------"
echo "Downloading Vosk Wake Word Model (vosk-model-small-es-0.42)..."
mkdir -p backend/src/infrastructure/models/vosk
cd backend/src/infrastructure/models/vosk

if [ ! -d "vosk-model-small-es-0.42" ]; then
    echo "Downloading vosk-model-small-es-0.42.zip (approx 40MB)..."
    curl -L -o vosk-model-small-es-0.42.zip https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip
    echo "Unzipping..."
    unzip -q vosk-model-small-es-0.42.zip
    rm vosk-model-small-es-0.42.zip
else
    echo "Vosk model already exists. Skipping."
fi

echo "-----------------------------------"
echo "All models downloaded successfully!"

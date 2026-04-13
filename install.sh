#!/usr/bin/env bash
set -e

echo "Setting up Orion CLI..."
echo ""

# 1. Check for required system tools
for cmd in curl git; do
    if ! command -v "$cmd" &> /dev/null; then
        echo "[ERROR] '$cmd' is required but not found. Please install it via your package manager."
        exit 1
    fi
done

# 2. Install 'uv' if it's not already installed
if ! command -v uv &> /dev/null; then
    echo "[INFO] 'uv' package manager not found. Installing it under the hood..."
    
    # Run the installer quietly, but allow standard error (stderr) to show if a network failure occurs
    curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null
    
    # Export paths explicitly for this session so we can use it immediately
    export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
    
    if ! command -v uv &> /dev/null; then
        echo "[ERROR] Failed to install 'uv'. Please install it manually from https://docs.astral.sh/uv/"
        exit 1
    fi
    echo "[INFO] 'uv' installed successfully."
fi

# 3. Add local bin to path temporarily for the script runtime
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"

# 4. Install Orion
echo "Fetching and building latest Orion binary (this takes a few seconds)..."

# uv handles Python versioning, venv isolation, and binary linking automatically
uv tool install --force git+https://github.com/Om-Jadon/cli-assistant.git

echo ""
echo "Orion is successfully installed!"
echo ""

# 5. Smart PATH check for the user's environment
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo "[WARNING] Almost done! Ensure your local binaries are in your PATH:"
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo "    (We recommend adding this line to your ~/.bashrc or ~/.zshrc)"
    echo ""
fi

echo "Run 'orion' from your terminal to get started."

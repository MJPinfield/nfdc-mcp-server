#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  NFDC Planning MCP Server – one-time installer for macOS
#  Works on a completely fresh Mac with nothing pre-installed.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO="MJPinfield/nfdc-mcp-server"
INSTALL_DIR="$HOME/nfdc-mcp-server"
CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
UV_BIN="$HOME/.local/bin/uv"

# ── Helpers ───────────────────────────────────────────────────────────────────

print_banner() {
  echo ""
  echo "╔══════════════════════════════════════════════════════╗"
  echo "║   New Forest Planning – Claude Tool Installer        ║"
  echo "╚══════════════════════════════════════════════════════╝"
  echo ""
}

step() { echo ""; echo "▶ $1"; }
ok()   { echo "  ✓ $1"; }
info() { echo "  · $1"; }

die() {
  echo ""
  echo "  ✗ ERROR: $1"
  echo ""
  echo "  Something went wrong during installation."
  echo "  Please send this message to Max and he can help."
  echo ""
  exit 1
}

# ── 1. Xcode Command Line Tools (provides curl, git, etc.) ───────────────────
step "Checking system tools..."

if ! xcode-select -p &>/dev/null; then
  info "Installing Xcode Command Line Tools (this may take several minutes)..."
  info "A popup window may appear – click 'Install' if it does."
  xcode-select --install 2>/dev/null || true

  # Wait for installation to complete
  until xcode-select -p &>/dev/null; do
    sleep 5
  done
  ok "Xcode Command Line Tools installed"
else
  ok "Xcode Command Line Tools already present"
fi

# ── 2. uv (Python + package manager in one) ──────────────────────────────────
step "Checking uv (Python manager)..."

export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv &>/dev/null; then
  info "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh \
    || die "Could not install uv. Please check your internet connection."
  export PATH="$HOME/.local/bin:$PATH"
  ok "uv installed"
else
  ok "uv already installed"
fi

# Sanity check
uv --version &>/dev/null || die "uv installed but not working correctly."

# ── 3. Download the server files ─────────────────────────────────────────────
step "Downloading the planning server..."

# Base URL for raw file downloads
RAW="https://raw.githubusercontent.com/$REPO/main"

# Files to download: destination_path relative to INSTALL_DIR : source path in repo
FILES=(
  "main.py"
  "pyproject.toml"
  "nfdc/__init__.py"
  "nfdc/constants.py"
  "nfdc/http.py"
  "nfdc/parsers.py"
  "nfdc/tools/__init__.py"
  "nfdc/tools/search.py"
  "nfdc/tools/details.py"
  "nfdc/tools/comments.py"
  "nfdc/tools/documents.py"
)

for file in "${FILES[@]}"; do
  dest="$INSTALL_DIR/$file"
  mkdir -p "$(dirname "$dest")"
  curl -LsSf "$RAW/$file" -o "$dest" \
    || die "Could not download $file. Please check your internet connection."
done

ok "Server downloaded to $INSTALL_DIR"

# ── 4. Install Python dependencies ───────────────────────────────────────────
step "Installing Python dependencies (this may take a minute)..."

"$UV_BIN" sync --project "$INSTALL_DIR" --quiet \
  || die "Could not install Python dependencies."

ok "Dependencies installed"

# ── 5. Check Claude Desktop is installed ─────────────────────────────────────
step "Checking Claude Desktop..."

CLAUDE_APP="/Applications/Claude.app"
if [ ! -d "$CLAUDE_APP" ]; then
  echo ""
  echo "  ✗ Claude Desktop does not appear to be installed."
  echo ""
  echo "  Please download and install it from:"
  echo "    https://claude.ai/download"
  echo ""
  echo "  Once installed, run this script again."
  exit 1
fi

ok "Claude Desktop found"

# ── 6. Configure Claude Desktop ──────────────────────────────────────────────
step "Configuring Claude Desktop..."

mkdir -p "$HOME/Library/Application Support/Claude"

# Write a small Python script to merge the config safely
"$UV_BIN" run --project "$INSTALL_DIR" python - <<PYEOF
import json, pathlib, sys

config_path = pathlib.Path("""$CLAUDE_CONFIG""")
install_dir = """$INSTALL_DIR"""
uv_bin      = """$UV_BIN"""

new_entry = {
    "command": uv_bin,
    "args": [
        "run",
        "--project", install_dir,
        "python", f"{install_dir}/main.py"
    ],
    "env": {}
}

if config_path.exists():
    try:
        config = json.loads(config_path.read_text())
    except json.JSONDecodeError:
        config = {}
else:
    config = {}

config.setdefault("mcpServers", {})["NFDC Planning"] = new_entry
config_path.write_text(json.dumps(config, indent=2))
print("  ✓ Claude Desktop configured")
PYEOF

# ── 7. Done ───────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  All done!                                           ║"
echo "║                                                      ║"
echo "║  Next step:                                          ║"
echo "║    Quit Claude Desktop completely and reopen it.     ║"
echo "║    (Right-click the Dock icon → Quit)                ║"
echo "║                                                      ║"
echo "║  Then try asking Claude:                             ║"
echo "║    \"Look up planning application 25/10114\"           ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

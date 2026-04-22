#!/bin/bash
set -e

# ─────────────────────────────────────────────────────────────
#  NFDC Planning MCP Server – one-time installer for macOS
# ─────────────────────────────────────────────────────────────

INSTALL_DIR="$HOME/nfdc-mcp-server"
CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
UV_BIN="$HOME/.local/bin/uv"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   New Forest Planning – Claude Tool Installer        ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── 1. Install uv if missing ──────────────────────────────────
if ! command -v uv &>/dev/null && [ ! -f "$UV_BIN" ]; then
  echo "▶ Installing uv (Python package manager)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  echo "  ✓ uv installed"
else
  export PATH="$HOME/.local/bin:$PATH"
  echo "  ✓ uv already installed"
fi

# ── 2. Download the server files ─────────────────────────────
echo ""
echo "▶ Downloading the planning server..."

mkdir -p "$INSTALL_DIR"

curl -LsSf \
  "https://raw.githubusercontent.com/MJPinfield/nfdc-mcp-server/main/main.py" \
  -o "$INSTALL_DIR/main.py"

curl -LsSf \
  "https://raw.githubusercontent.com/MJPinfield/nfdc-mcp-server/main/pyproject.toml" \
  -o "$INSTALL_DIR/pyproject.toml"

echo "  ✓ Server downloaded to $INSTALL_DIR"

# ── 3. Install Python dependencies ───────────────────────────
echo ""
echo "▶ Installing dependencies (this may take a minute)..."
cd "$INSTALL_DIR"
"$UV_BIN" sync --quiet
echo "  ✓ Dependencies installed"

# ── 4. Configure Claude Desktop ──────────────────────────────
echo ""
echo "▶ Configuring Claude Desktop..."

CLAUDE_DIR="$HOME/Library/Application Support/Claude"
mkdir -p "$CLAUDE_DIR"

# Build the new server entry
NEW_ENTRY=$(cat <<EOF
{
  "command": "$UV_BIN",
  "args": [
    "run",
    "--project",
    "$INSTALL_DIR",
    "python",
    "$INSTALL_DIR/main.py"
  ],
  "env": {}
}
EOF
)

if [ -f "$CONFIG" ]; then
  # Config exists – check if our server is already there
  if grep -q "NFDC Planning" "$CONFIG"; then
    echo "  ✓ Claude Desktop already configured (skipping)"
  else
    # Use Python (available via uv) to safely merge the JSON
    "$UV_BIN" run --with pip python - <<PYEOF
import json, sys

config_path = """$CONFIG"""
new_entry = json.loads("""$NEW_ENTRY""")

with open(config_path) as f:
    config = json.load(f)

config.setdefault("mcpServers", {})["NFDC Planning"] = new_entry

with open(config_path, "w") as f:
    json.dump(config, f, indent=2)

print("  ✓ Added NFDC Planning to Claude Desktop config")
PYEOF
  fi
else
  # No config yet – create a fresh one
  cat > "$CONFIG" <<EOF
{
  "mcpServers": {
    "NFDC Planning": $NEW_ENTRY
  }
}
EOF
  echo "  ✓ Created Claude Desktop config"
fi

# ── 5. Done ───────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  Installation complete!                              ║"
echo "║                                                      ║"
echo "║  Next step:                                          ║"
echo "║    Quit Claude Desktop and open it again.            ║"
echo "║                                                      ║"
echo "║  Then ask Claude something like:                     ║"
echo "║    \"Look up planning application 25/10114\"           ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

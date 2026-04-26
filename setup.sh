#!/bin/bash
# ─────────────────────────────────────────────────────────
# Shadow Scribe — Setup Script (run once)
# Creates vault structure + .env + INDEX_MATRIX + alias
# ─────────────────────────────────────────────────────────

set -e

VAULT_DIR="$HOME/Documents/agent_vault"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "════════════════════════════════════════════════════════════"
echo "🛡️  SHADOW SCRIBE — Initial Setup"
echo "════════════════════════════════════════════════════════════"
echo ""

# ── Step 1: Create Vault Structure ────────────────────────
echo "📂 Creating vault at: $VAULT_DIR"
mkdir -p "$VAULT_DIR/sessions"
mkdir -p "$VAULT_DIR/raw_logs"
mkdir -p "$VAULT_DIR/artifacts"
mkdir -p "$VAULT_DIR/projects"
mkdir -p "$VAULT_DIR/digests"
mkdir -p "$VAULT_DIR/trash"
echo "   ✅ Vault structure ready"

# ── Step 2: Create 00_INDEX_MATRIX.md ────────────────────
INDEX_FILE="$VAULT_DIR/00_INDEX_MATRIX.md"
if [ ! -f "$INDEX_FILE" ]; then
    cat > "$INDEX_FILE" << 'EOF'
# 🗄️ Master Index — Shadow Scribe Vault

> Each row = 1 session. Auto-updated by `watchdog scribe`.

| Date | Project | Workspace | TL;DR | Session | Plan | Tags |
|------|---------|-----------|-------|---------|------|------|
EOF
    echo "   ✅ 00_INDEX_MATRIX.md created"
else
    echo "   ℹ️  00_INDEX_MATRIX.md already exists — skipping"
fi

# ── Step 3: Create .env ──────────────────────────────────
ENV_FILE="$VAULT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo ""
    read -p "🔑 Enter your Gemini API Key (get one at https://aistudio.google.com/): " API_KEY
    if [ -n "$API_KEY" ]; then
        cat > "$ENV_FILE" << EOF
# Shadow Scribe — Environment Variables
# Watchdog auto-reads this file, no export needed.
GEMINI_API_KEY=$API_KEY
EOF
        echo "   ✅ .env created at $ENV_FILE"
    else
        cat > "$ENV_FILE" << 'EOF'
# Shadow Scribe — Environment Variables
# Watchdog auto-reads this file, no export needed.
GEMINI_API_KEY=YOUR_KEY_HERE
EOF
        echo "   ⚠️  .env created but no API Key provided. Edit later: $ENV_FILE"
    fi
else
    echo "   ℹ️  .env already exists — skipping"
fi

# ── Step 4: Copy GUIDE.md into vault ─────────────────────
GUIDE_SRC="$SCRIPT_DIR/GUIDE.md"
GUIDE_DEST="$VAULT_DIR/GUIDE.md"
if [ -f "$GUIDE_SRC" ]; then
    cp "$GUIDE_SRC" "$GUIDE_DEST"
    echo "   ✅ GUIDE.md copied into vault"
else
    echo "   ⚠️  GUIDE.md not found in repo"
fi

# ── Step 5: Add watchdog alias to shell ──────────────────
SHELL_RC=""
if [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

if [ -n "$SHELL_RC" ]; then
    if ! grep -q "watchdog()" "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        cat >> "$SHELL_RC" << EOF
# ─── Shadow Scribe Watchdog ───────────────────────────
function watchdog() {
    python3 "$SCRIPT_DIR/watchdog_scribe.py" "\$@"
}
# ──────────────────────────────────────────────────────
EOF
        echo "   ✅ watchdog alias added to $SHELL_RC"
        echo "   ℹ️  Run 'source $SHELL_RC' to activate"
    else
        echo "   ℹ️  watchdog alias already exists — skipping"
    fi
else
    echo "   ⚠️  Could not find .zshrc or .bashrc"
    echo "      Add manually: function watchdog() { python3 $SCRIPT_DIR/watchdog_scribe.py \"\$@\"; }"
fi

# ── Done ─────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════"
echo "✅ Setup complete!"
echo ""
echo "📖 Next steps:"
echo "   1. source $SHELL_RC         (activate alias)"
echo "   2. watchdog --help           (verify)"
echo "   3. Send GUIDE.md to Agent:   'Read ~/Documents/agent_vault/GUIDE.md'"
echo ""
echo "📚 Documentation:"
echo "   • README.md  — Architecture & features"
echo "   • GUIDE.md   — Operations manual for AI Agents"
echo "════════════════════════════════════════════════════════════"

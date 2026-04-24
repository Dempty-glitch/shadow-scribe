#!/bin/bash
# ─────────────────────────────────────────────────────────
# Shadow Scribe — Setup Script (chạy 1 lần duy nhất)
# Tạo vault structure + .env + INDEX_MATRIX + alias
# ─────────────────────────────────────────────────────────

set -e

VAULT_DIR="$HOME/Documents/agent_vault"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "════════════════════════════════════════════════════════════"
echo "🛡️  SHADOW SCRIBE — Initial Setup"
echo "════════════════════════════════════════════════════════════"
echo ""

# ── Step 1: Tạo Vault Structure ──────────────────────────
echo "📂 Tạo vault tại: $VAULT_DIR"
mkdir -p "$VAULT_DIR/sessions"
mkdir -p "$VAULT_DIR/raw_logs"
mkdir -p "$VAULT_DIR/artifacts"
mkdir -p "$VAULT_DIR/projects"
mkdir -p "$VAULT_DIR/digests"
mkdir -p "$VAULT_DIR/trash"
echo "   ✅ Vault structure đã sẵn sàng"

# ── Step 2: Tạo 00_INDEX_MATRIX.md ──────────────────────
INDEX_FILE="$VAULT_DIR/00_INDEX_MATRIX.md"
if [ ! -f "$INDEX_FILE" ]; then
    cat > "$INDEX_FILE" << 'EOF'
# 🗄️ Master Index — Shadow Scribe Vault

> Mỗi dòng = 1 phiên làm việc. Tự động cập nhật bởi `watchdog scribe`.

| Ngày | Project | Workspace | TL;DR | Session | Plan | Tags |
|------|---------|-----------|-------|---------|------|------|
EOF
    echo "   ✅ 00_INDEX_MATRIX.md đã tạo"
else
    echo "   ℹ️  00_INDEX_MATRIX.md đã tồn tại — bỏ qua"
fi

# ── Step 3: Tạo .env ────────────────────────────────────
ENV_FILE="$VAULT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo ""
    read -p "🔑 Nhập Gemini API Key (lấy tại https://aistudio.google.com/): " API_KEY
    if [ -n "$API_KEY" ]; then
        cat > "$ENV_FILE" << EOF
# Shadow Scribe — Environment Variables
# Watchdog sẽ tự đọc file này, không cần export.
GEMINI_API_KEY=$API_KEY
EOF
        echo "   ✅ .env đã tạo tại $ENV_FILE"
    else
        cat > "$ENV_FILE" << 'EOF'
# Shadow Scribe — Environment Variables
# Watchdog sẽ tự đọc file này, không cần export.
GEMINI_API_KEY=YOUR_KEY_HERE
EOF
        echo "   ⚠️  .env đã tạo nhưng chưa có API Key. Chỉnh sửa sau: $ENV_FILE"
    fi
else
    echo "   ℹ️  .env đã tồn tại — bỏ qua"
fi

# ── Step 4: Copy GUIDE.md vào vault ─────────────────────
GUIDE_SRC="$SCRIPT_DIR/GUIDE.md"
GUIDE_DEST="$VAULT_DIR/GUIDE.md"
if [ -f "$GUIDE_SRC" ]; then
    cp "$GUIDE_SRC" "$GUIDE_DEST"
    echo "   ✅ GUIDE.md đã copy vào vault"
else
    echo "   ⚠️  Không tìm thấy GUIDE.md trong repo"
fi

# ── Step 5: Thêm watchdog alias vào shell ───────────────
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
        echo "   ✅ watchdog alias đã thêm vào $SHELL_RC"
        echo "   ℹ️  Chạy 'source $SHELL_RC' để kích hoạt"
    else
        echo "   ℹ️  watchdog alias đã tồn tại — bỏ qua"
    fi
else
    echo "   ⚠️  Không tìm thấy .zshrc hoặc .bashrc"
    echo "      Thêm thủ công: function watchdog() { python3 $SCRIPT_DIR/watchdog_scribe.py \"\$@\"; }"
fi

# ── Done ─────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════"
echo "✅ Setup hoàn tất!"
echo ""
echo "📖 Bước tiếp theo:"
echo "   1. source $SHELL_RC         (kích hoạt alias)"
echo "   2. watchdog --help           (kiểm tra)"
echo "   3. Gửi GUIDE.md cho Agent:   'Đọc ~/Documents/agent_vault/GUIDE.md'"
echo ""
echo "📚 Tài liệu:"
echo "   • README.md  — Hiểu kiến trúc & tính năng"
echo "   • GUIDE.md   — Sổ tay vận hành cho AI Agent"
echo "════════════════════════════════════════════════════════════"

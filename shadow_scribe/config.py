"""shadow_scribe.config — Paths, env loader, Gemini settings."""

import os
from pathlib import Path

# ─── Vault paths ──────────────────────────────────────────────────────────────

VAULT_DIR = Path.home() / "Documents" / "agent_vault"
RAW_LOGS_DIR = VAULT_DIR / "raw_logs"
SESSIONS_DIR = VAULT_DIR / "sessions"
INDEX_FILE = VAULT_DIR / "00_INDEX_MATRIX.md"
TRASH_DIR = VAULT_DIR / "trash"
ENV_FILE = VAULT_DIR / ".env"


# ─── Env loader ───────────────────────────────────────────────────────────────

def _load_env_file(env_path: Path) -> None:
    """Đọc file .env đơn giản (KEY=VALUE), inject vào os.environ nếu chưa có."""
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")  # Bỏ quotes nếu có
        if key and key not in os.environ:  # Không ghi đè env var đã có
            os.environ[key] = value


def load_env() -> None:
    """Public entry point — gọi explicit từ entry point, không side-effect khi import."""
    _load_env_file(ENV_FILE)


# ─── Gemini settings (populated after load_env() is called) ───────────────────

def get_gemini_api_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "")


def get_gemini_model() -> str:
    # ADR-005: Enforce gemini-2.5-flash, bypass leaked GEMINI_MODEL from system/IDE
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    if model == "gemini-3.1-pro":
        return "gemini-2.5-flash"
    return "gemini-2.5-flash"


# ─── Version ──────────────────────────────────────────────────────────────────

VERSION = "1.3.0"

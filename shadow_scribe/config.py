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
    """Read simple .env file (KEY=VALUE), inject into os.environ if not already set."""
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
        value = value.strip().strip('"').strip("'")  # Strip quotes if present
        if key and key not in os.environ:  # Don't overwrite existing env vars
            os.environ[key] = value


def load_env() -> None:
    """Public entry point — called explicitly from entry point, no side-effects on import."""
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


def get_lang() -> str:
    """Read SHADOW_SCRIBE_LANG env var. Returns 'vi' (default) or 'en'.

    Invalid values silently fall back to 'vi' with a warning.
    """
    lang = os.environ.get("SHADOW_SCRIBE_LANG", "vi").lower()
    if lang not in ("vi", "en"):
        print(f"⚠️  Invalid SHADOW_SCRIBE_LANG='{lang}'. Falling back to 'vi'.")
        return "vi"
    return lang


# ─── Version ──────────────────────────────────────────────────────────────────

VERSION = "1.3.0"

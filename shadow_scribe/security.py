"""shadow_scribe.security — Secrets redaction, prompt injection defense, diff filtering."""

import re

# ─── Secrets redaction ────────────────────────────────────────────────────────

_SECRET_PATTERNS = [
    # Key-Value patterns: KEY=value, KEY: value, KEY = "value"
    (r'(?i)(API[_-]?KEY|SECRET[_-]?KEY|PASSWORD|PASSWD|TOKEN|ACCESS[_-]?KEY|PRIVATE[_-]?KEY|AUTH)\s*[:=]\s*["\']?([^\s"\']{8,})["\']?',
     r'\1=*****[REDACTED]*****'),
    # Common prefixes: ghp_, sk-, AIza, AKIA, etc.
    (r'\b(ghp_[A-Za-z0-9]{36})',        '*****[REDACTED_GH]*****'),
    (r'\b(sk-[A-Za-z0-9]{32,})',         '*****[REDACTED_SK]*****'),
    (r'\b(AIza[A-Za-z0-9_-]{35})',       '*****[REDACTED_GAPI]*****'),
    (r'\b(AKIA[A-Z0-9]{16})',            '*****[REDACTED_AWS]*****'),
    # PEM private keys
    (r'-----BEGIN[A-Z ]*PRIVATE KEY-----[\s\S]*?-----END[A-Z ]*PRIVATE KEY-----',
     '*****[REDACTED_PEM]*****'),
]


def _redact_secrets(text: str) -> str:
    """Mask secrets/credentials trước khi gửi lên API."""
    redacted = text
    count = 0
    for pattern, replacement in _SECRET_PATTERNS:
        redacted, n = re.subn(pattern, replacement, redacted)
        count += n
    if count:
        print(f"🔒 Đã redact {count} secret(s) trước khi gửi API")
    return redacted


# ─── Prompt injection defense ─────────────────────────────────────────────────

_PROMPT_TAGS = ["SESSION_BRIEF", "GIT_DIFF", "PLAN", "SESSION_LOGS", "INDEX_MATRIX", "QUERY"]


def _sanitize_tags(text: str) -> str:
    """Escape XML-like tags trong content để chống prompt injection."""
    sanitized = text
    for tag in _PROMPT_TAGS:
        sanitized = sanitized.replace(f"<{tag}>", f"＜{tag}＞")
        sanitized = sanitized.replace(f"</{tag}>", f"＜/{tag}＞")
    return sanitized


# ─── Diff noise filter ────────────────────────────────────────────────────────

_DIFF_NOISE_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "Cargo.lock", "Gemfile.lock", "poetry.lock",
    ".DS_Store", "Thumbs.db",
}


def _filter_diff(diff_text: str) -> str:
    """Loại bỏ diff chunks từ các file noise (lockfiles, binary, etc.)."""
    if not diff_text or diff_text == "(Không có dữ liệu)":
        return diff_text

    filtered_chunks = []
    current_chunk: list[str] = []
    skip = False

    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            if current_chunk and not skip:
                filtered_chunks.extend(current_chunk)
            parts = line.split(" b/", 1)
            current_file = parts[1] if len(parts) > 1 else ""
            basename = current_file.rsplit("/", 1)[-1] if current_file else ""
            skip = basename in _DIFF_NOISE_FILES
            current_chunk = [line]
        else:
            current_chunk.append(line)

    if current_chunk and not skip:
        filtered_chunks.extend(current_chunk)

    result = "\n".join(filtered_chunks)
    removed = len(diff_text) - len(result)
    if removed > 100:
        print(f"🧹 Đã lọc {removed:,} chars noise từ git diff")
    return result

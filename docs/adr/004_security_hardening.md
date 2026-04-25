# ADR-004: Security Hardening Strategy — Application-Layer Defense

| Field | Value |
|-------|-------|
| **Ngày tạo** | 24/04/2026 |
| **Project** | shadow-scribe |
| **Status** | 🟢 ACCEPTED |
| **Session liên quan** | [→](../../sessions/2026-04/24_04_26_1.md) |
| **Artifacts** | [Audit Report](../../artifacts/2026-04/shadow_scribe_audit_24_04_26.md) |

## Context (Bài toán)
Shadow Scribe gửi **toàn bộ git diff + session brief** lên Gemini API để phân tích. Nếu trong diff có API keys, passwords, PEM keys, hoặc PII — tất cả bay lên Google. Đồng thời, `00_INDEX_MATRIX.md` được đọc-sửa-ghi bởi nhiều agent tiềm năng mà không có cơ chế chống race condition. HTTP calls không có timeout hay retry — 1 lỗi mạng = crash.

**Mâu thuẫn cốt lõi:** Muốn gửi diff đầy đủ (để Gemini phân tích chính xác) nhưng phải che giấu data nhạy cảm (để không lộ secrets).

---

## 📍 Quyết định (The Chosen Path)

> **Đã chọn: Defense-in-Depth tại Application Layer**

Bảo vệ ở 4 lớp, tất cả trong `watchdog_scribe.py`, zero dependency thêm:

| Lớp | Vấn đề | Giải pháp | Hàm |
|-----|--------|-----------|-----|
| 1 — Redaction | Secrets trong diff | Regex mask trước khi gửi API | `_redact_secrets()` |
| 2 — Sanitization | Prompt injection qua XML tags | Escape `<TAG>` → `＜TAG＞` | `_sanitize_tags()` |
| 3 — Atomicity | Race condition ghi Index | `fcntl.flock` + `tempfile` + `os.replace` | `_atomic_write_index()` |
| 4 — Resilience | HTTP hang/crash | 120s timeout + exponential backoff 3x | `_http_post_with_retry()` |

**Lý do chọn application-layer:**
- **Zero dependency** — chỉ dùng stdlib (`re`, `fcntl`, `tempfile`, `time`), không thêm package nào
- **Portable** — chạy trên bất kỳ macOS/Linux nào có Python 3.9+
- **Transparent** — user thấy `🔒 Đã redact 2 secret(s)` trực tiếp trên terminal
- **Tối ưu cho single-user** — flock đủ mạnh cho 2-3 agent song song, không cần database

**Trade-off chấp nhận:**
- Regex redaction **không hoàn hảo** — custom secret formats có thể lọt. Bù bằng cách: user nên dùng `.gitignore` đúng + không hardcode secrets
- `fcntl.flock` **chỉ hoạt động trên Unix** — Windows cần `msvcrt.locking()`. Chấp nhận vì user chỉ dùng macOS
- Fullwidth character escape (`＜` thay `<`) **thay đổi visual** của content — chấp nhận vì content đã qua Gemini sẽ không được hiển thị raw

---

## 🚫 Các con đường đã loại bỏ (Rejected Paths)

### ❌ Cách 1 — Chỉ dựa vào .gitignore
- **Loại từ vòng:** Phân tích
- **Lý do:** `.gitignore` chặn file khỏi git, nhưng không chặn secrets hardcoded trong code đã tracked. Ví dụ: `config.py` có `API_KEY = "AIza..."` — file được tracked hợp lệ nhưng chứa secret. .gitignore không giúp gì.

### ❌ Cách 2 — Encrypted transport (mã hóa diff trước khi gửi)
- **Loại từ vòng:** Lý thuyết
- **Lý do:** Gemini cần đọc plaintext để phân tích. Mã hóa → Gemini không đọc được → vô nghĩa. Vấn đề không phải ai đọc (Google), mà là data nào được gửi.

### ❌ Cách 3 — API proxy/middleware (chạy local server filter trước khi forward)
- **Loại từ vòng:** Lý thuyết
- **Lý do:** Vi phạm nguyên tắc zero-dependency. Thêm proxy = thêm process, thêm port, thêm config. Overkill cho CLI script.

### ❌ Cách 4 — SQLite WAL cho Index (thay fcntl.flock)
- **Loại từ vòng:** Phân tích
- **Lý do:** Index là file Markdown — agent đọc trực tiếp bằng mắt và grep. Chuyển sang SQLite = agent cần tool để đọc, mất tính "Human-readable Relational Database". Trade-off không xứng đáng cho 1 file < 100 dòng.

### ❌ Cách 5 — Pre-commit git hook (chặn commit nếu có secrets)
- **Loại từ vòng:** Defer (Phase 5 roadmap)
- **Lý do:** Hook chặn ở git layer — tốt nhưng không bảo vệ `watchdog audit` (đọc diff unstaged). Application-layer redaction bảo vệ tại điểm cuối cùng trước khi data rời máy.

---

## 📊 Ma trận so sánh

| Tiêu chí | .gitignore ❌ | Encrypted ❌ | Proxy ❌ | SQLite ❌ | **App-layer ✅** |
|----------|-------------|------------|---------|---------|-----------------|
| Chặn hardcoded secrets | ❌ | N/A | ✅ | N/A | **✅** |
| Zero dependency | ✅ | ❌ (crypto lib) | ❌ (server) | ❌ (sqlite3) | **✅ (stdlib)** |
| Agent đọc Index bằng grep | ✅ | ✅ | ✅ | ❌ | **✅** |
| Chống race condition | ❌ | ❌ | ❌ | ✅ | **✅ (flock)** |
| HTTP resilience | ❌ | ❌ | ✅ | ❌ | **✅ (retry)** |
| Portable (Mac/Linux) | ✅ | ✅ | 🟡 | ✅ | **✅** |
| Windows compat | ✅ | ✅ | 🟡 | ✅ | **❌ (fcntl)** |

---

## 🔮 Đường tiềm năng chưa test (Future Paths)

### ⏳ Pre-commit Hook + Redaction combo
- **Khi nào:** Phase 5 (nếu team multi-user)
- **Ý tưởng:** Hook scan staged files bằng cùng `_SECRET_PATTERNS`, block commit nếu tìm thấy. Kết hợp với app-layer = defense at 2 checkpoints.

### ⏳ Custom secret pattern config
- **Khi nào:** Nếu user có secret formats đặc thù (VD: internal API tokens)
- **Ý tưởng:** Cho phép `~/.watchdog_redact_patterns` chứa regex bổ sung. Merge vào `_SECRET_PATTERNS` khi load.

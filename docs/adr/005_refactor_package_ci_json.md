# ADR-005: Refactor Monolith → Package + CI + JSON Parser (v1.2.2)

| Field | Value |
|-------|-------|
| **Ngày tạo** | 25/04/2026 |
| **Project** | shadow-scribe |
| **Status** | 🟢 ACCEPTED |
| **Session liên quan** | [→](../../sessions/2026-04/25_04_26.md) |
| **Plan liên quan** | [v1.2.2_refactor.md](../plans/v1.2.2_refactor.md) |

> **Next status flip:** ACCEPTED khi user sign-off → IMPLEMENTED khi v1.2.2 merged vào main.

---

## Context (Bài toán)

Shadow Scribe v1.2.1 đã ship thành công Phase 3.4 Security Hardening. Tuy nhiên một đánh giá độc lập (Claude Sonnet) chấm **6/10 Code Quality** và **5/10 Testing** — hai điểm thấp nhất trong 10 tiêu chí. Root cause:

- `watchdog_scribe.py` đã phình lên **901 dòng** — 3 commands + 2 prompts + 6 helpers + config + main trong 1 file
- **0 unit tests** cho security helpers (`_redact_secrets`, `_sanitize_tags`, `_atomic_write_index`)
- **0 CI/CD** — `test_audit_quality.py` chỉ chạy thủ công khi nhớ
- **Parser giòn** — split bằng string `===INDEX===`, Gemini lệch 1 ký tự = crash không recover

Nếu tiếp tục thêm feature (Phase 4 Telegram, Phase 6 RAG) lên monolith này, tech debt sẽ nhân đôi và không ai muốn đụng vào nữa.

**Trigger thực tế:** Claude Sonnet chấm 6/10 Code Quality, 5/10 Testing → muốn B+ → A- trước khi mở Phase 4.

---

## 📍 Quyết định (The Chosen Path)

> **Đã chọn: 3 việc đồng thời trong 1 version bump (v1.2.2 PATCH)**

### 1. Split monolith → `shadow_scribe/` package (8 modules)

```
shadow_scribe/
├── config.py      — paths, env loader
├── prompts.py     — 3 prompt strings
├── security.py    — redact, sanitize, filter_diff
├── io_utils.py    — atomic_write, read_file, parse_session_date
├── gemini.py      — http retry, call_gemini, parse_output
├── cmd_scribe.py  — cmd_scribe()
├── cmd_audit.py   — cmd_audit()
└── cmd_digest.py  — cmd_digest()
```

`watchdog_scribe.py` trở thành thin entry point ≤ 50 dòng.

**Lý do:** Test isolation thật sự đòi hỏi mỗi module có thể import độc lập. Test `security.py` không được kéo theo HTTP client, không cần mock Gemini.

### 2. CI: GitHub Actions matrix 3.9 + 3.12, ruff, mypy non-strict

```yaml
matrix: python-version: ['3.9', '3.12']
steps: ruff check → mypy --ignore-missing-imports → pytest → test_audit_quality.py --mock
```

**Lý do:** Oldest supported (3.9) + newest (3.12) đủ bắt compatibility drift mà không thừa. `mypy non-strict` là gate-keeper cho tương lai — chưa catch gì ngay vì 0 type hints, nhưng có cọc để tighten dần ở v1.2.3+.

### 3. JSON parser 3-layer thay `===INDEX===`

```
Layer 1: json.loads(raw)                    — response_mime_type đã ép
Layer 2: strip code fence → json.loads()    — Gemini đôi khi vẫn wrap
Layer 3: split("===INDEX===")               — fallback backward compat
```

Dùng `response_mime_type: "application/json"` trong API call để ép Gemini trả JSON thuần.

**Lý do:** String separator là single point of failure. 3-layer không bao giờ crash — worst case trả `("", "")` và ghi warning.

---

## 🚫 Các con đường đã loại bỏ (Rejected Paths)

### ❌ Tên package `watchdog/`
- **Lý do:** `watchdog` là PyPI package phổ biến (~13M downloads/tháng, file-system events). Import collision nếu user cài thêm trong cùng env.
- **Fix:** `shadow_scribe/`

### ❌ Split chỉ thành 2-3 file lớn
- **Lý do:** `security.py` + `gemini.py` là 2 concern hoàn toàn khác nhau. Gom vào `helpers.py` thì test vẫn phải mock HTTP khi test regex — không phải test isolation thật sự.

### ❌ mypy `--strict`
- **Lý do:** Project hiện tại 0 type hints → `--strict` sinh hàng trăm errors ngay lập tức → CI đỏ vĩnh viễn → nobody fixes → CI bị bỏ qua. Non-strict là compromise thực tế.

### ❌ Bump v1.3.0
- **Lý do:** SemVer: MINOR khi có user-visible feature mới. Refactor + CI + parser đổi nội bộ = PATCH. v1.3.0 nên dành cho Phase 4 Telegram.

### ❌ JSON parser không có fallback
- **Lý do:** Gemini đôi khi wrap JSON trong code fence dù đã dặn không làm vậy. Không có fallback = crash production. 3-layer là belt-and-suspenders.

### ❌ Wildcard import `from shadow_scribe.config import *`
- **Lý do:** Namespace pollution + side-effect khi import + lint warning vĩnh viễn. Explicit import từng symbol.

---

## ⚠️ Trade-offs chấp nhận

| Trade-off | Mức độ | Lý do chấp nhận |
|-----------|--------|-----------------|
| mypy chưa catch gì (0 type hints) | 🟢 LOW | Gate-keeper, không phải bug catcher ngay. Type hints ship dần v1.2.3+ |
| 14-16h work, không thêm feature nào | 🟡 MED | Debt repayment — đầu tư vào foundation trước Phase 4/6 |
| 10 commits granular — nếu skip verify có silent regression | 🟡 MED | Giảm thiểu bằng quy tắc: mỗi step verify trước khi commit tiếp |
| `response_mime_type` cần Gemini 1.5-flash+ | 🟢 LOW | Project dùng `gemini-2.5-flash` → OK. Layer 2/3 vẫn bắt nếu model cũ |
| Import paths thay đổi trong `setup.sh` | 🟢 LOW | Chỉ alias trong `setup.sh` — không có external consumer |

---

## 📊 Success Metrics

> Baseline từ Claude Sonnet audit 25/04/2026. Đo lại sau khi v1.2.2 ship.

| Tiêu chí | Before (v1.2.1) | Target (v1.2.2) |
|----------|----------------|----------------|
| Code Quality | 5.5/10 | 8.0/10 |
| Testing/CI | 5.0/10 | 7.5/10 |
| Architecture | 6.5/10 | 8.0/10 |
| Maintainability | 6.0/10 | 7.5/10 |
| **Tổng weighted** | **6.9/10 (B+)** | **≥8.0/10 (A-)** |
| Test coverage critical paths | 0% | ≥75% |
| Max dòng/file | 901 | ≤250 |
| CI green | ❌ | ✅ (3.9 + 3.12) |

---

## 🔄 Rollback Plan

- **Tag trước khi bắt đầu:** `git tag v1.2.1-stable` tại commit cuối v1.2.1
- **Rollback từng bước:** Mỗi step là 1 commit riêng → `git revert <commit>` bất kỳ lúc nào
- **Rollback toàn bộ:** `git checkout v1.2.1-stable` + update alias trong `setup.sh`
- **Không nhánh long-running:** `main` là source of truth, không tạo branch `refactor/v1.2.2`

---

## 🔮 Consequences (Hệ quả)

### Tích cực
- **Test isolation thật sự** — `security.py` test không cần mock HTTP
- **CI xanh** — regression được bắt tự động, không cần nhớ chạy tay
- **Foundation cho Phase 4/6** — Telegram bot import `shadow_scribe.cmd_audit` trực tiếp
- **PyPI-ready** — `shadow_scribe/` package structure cho phép publish nếu muốn sau này
- **Parser an toàn hơn** — 3-layer fallback resilient. (Quyết định bổ sung: Nếu cả 3 layer fail (garbage output), script sẽ `sys.exit(1)` thay vì trả về `("", "")` như plan ban đầu, để tránh silent data corruption).

### Tiêu cực / Rủi ro
- **14-16h không có feature mới** — cost phải trả để clean up debt trước Phase 4

---

## 📊 Ma trận so sánh

| Tiêu chí | Monolith 1 file ❌ | 2-3 file lớn ❌ | **8 modules ✅** |
|----------|-------------------|----------------|-----------------|
| Test isolation | ❌ | 🟡 | **✅** |
| Import collision risk | N/A | N/A | **✅ (`shadow_scribe/`)** |
| Rollback granular | ❌ | 🟡 | **✅ (1 commit/module)** |
| Dòng/file | 901 | ~300-400 | **≤250** |
| Foundation Phase 4/6 | ❌ | 🟡 | **✅** |

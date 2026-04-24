# ADR-003: Digest Architecture — Subcommand vs Flag vs Separate Script

| Field | Value |
|-------|-------|
| **Ngày tạo** | 14/04/2026 |
| **Project** | shadow-scribe |
| **Status** | 🟢 ACCEPTED |
| **Session liên quan** | [→](../../sessions/2026-04/14_04_26_2.md) |

## Context (Bài toán)

Sau khi `audit` (Phase 3.1) ổn định, nảy sinh nhu cầu "nhìn lại toàn bộ quá trình làm việc theo project" — không phải 1 session mà N sessions. Câu hỏi cốt lõi:

> *"Làm sao tổng hợp nhiều session logs thành 1 bản digest ngắn gọn, mà không cần biết bao nhiêu sessions tồn tại, không cần đọc thủ công?"*

Ràng buộc:
- Sessions của các project khác nhau trộn lẫn trong cùng `sessions/YYYY-MM/` — cần filter
- Một project chỉ active vài tuần đầu, sau đó im lặng — cần filter theo thời gian
- Gemini Flash có 1M context nhưng không phải vô hạn — cần truncate an toàn
- Output phải vừa xem được ngay (terminal) vừa lưu lại được (file)

---

## 📍 Quyết định (The Chosen Path)

> **Đã chọn: Cách 3 — Subcommand độc lập `watchdog digest` với project filter**

**Lý do chọn:**
- Tuân thủ SRP — mỗi subcommand làm đúng 1 việc, không confusion với `scribe`/`audit`
- `--project NAME` filter theo `**Project:**` header trong session log — không cần folder riêng per-project
- `--last N` filter theo filename date `DD_MM_YY.md` — không cần metadata file riêng
- Dual output (terminal + file) phục vụ 2 use case: xem nhanh vs lưu archive
- Truncate tự động tại 900K chars để fit Gemini 1M context — không crash silently

**Trade-off chấp nhận:**
- Phải maintain thêm 1 subcommand và 1 system prompt (`DIGEST_PROMPT`) riêng
- Filter `--project` phụ thuộc vào format header session log đúng chuẩn — nếu Anti viết sai format thì miss sessions

---

## 🚫 Các con đường đã loại bỏ (Rejected Paths)

### ❌ Cách 1 — Flag `--digest` trong `scribe` (ví dụ: `watchdog scribe --digest`)

- **Loại từ vòng:** Lý thuyết (ngay khi phân tích)
- **Lý do:** Vi phạm SRP — `scribe` là Destructive, ghép `digest` (Read-only) vào cùng subcommand gây nhầm lẫn UX. User không biết `scribe --digest` có ghi file hay không. Cùng pattern lỗi đã reject ở ADR-002.

### ❌ Cách 2 — Script riêng `digest_scribe.py`

- **Loại từ vòng:** Lý thuyết
- **Lý do:** Duplicate code (Gemini HTTP call, config constants, helper functions). Làm workspace phức tạp hơn không cần thiết. Khi đổi Gemini model phải sửa 2 file. `watchdog_scribe.py` đã là single entry point — giữ nguyên pattern.

---

## 🔮 Đường tiềm năng chưa test (Future Paths)

### ⏳ Cách 4 — Digest qua Telegram bot
- **Lý thuyết:** `/digest shadow-scribe 7` từ điện thoại → bot chạy `watchdog digest` → reply kết quả
- **Khi nào nên thử:** Phase 4 (Telegram integration)
- **Rủi ro dự đoán:** Cần reach máy local từ Telegram — SSH tunnel hay webhook phức tạp

### ⏳ Cách 5 — Cron auto-report hàng tuần
- **Lý thuyết:** `0 9 * * 1 watchdog digest --project shadow-scribe --last 7` chạy mỗi thứ Hai
- **Khi nào nên thử:** Phase 6, sau khi Telegram ổn định
- **Rủi ro dự đoán:** Cần máy luôn bật + key set sẵn trong cron env

---

## 📊 Ma trận so sánh

| Tiêu chí | Cách 1 ❌ `--digest` flag | Cách 2 ❌ Script riêng | **Cách 3 ✅ Subcommand** | Cách 4 ⏳ Telegram | Cách 5 ⏳ Cron |
|----------|--------------------------|----------------------|-------------------------|--------------------|----------------|
| SRP? | ❌ mixed | ✅ | **✅** | ✅ | ✅ |
| DRY (no dup code)? | ✅ | ❌ | **✅** | ✅ | ✅ |
| UX rõ ràng? | ❌ | ✅ | **✅** | ✅ | Auto |
| Project filter? | ❌ | tùy | **✅ `--project`** | ✅ | ✅ |
| Time filter? | ❌ | tùy | **✅ `--last N`** | ✅ | ✅ (hardcoded) |
| Dual output? | tùy | tùy | **✅** | ❌ chỉ Telegram | ❌ chỉ file |
| Đã test? | ❌ | ❌ | **✅ Build + syntax OK** | ❌ | ❌ |

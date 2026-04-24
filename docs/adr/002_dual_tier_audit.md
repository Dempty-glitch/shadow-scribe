# ADR-002: Dual-Tier Audit Architecture

| Field | Value |
|-------|-------|
| **Ngày tạo** | 14/04/2026 |
| **Project** | shadow-prominence |
| **Status** | 🟢 ACCEPTED |
| **Session liên quan** | [→](../../sessions/2026-04/14_04_26.md) |

## Context (Bài toán)

Sau khi `watchdog scribe` chạy thành công (Phase 3.1), nảy sinh nhu cầu "soi lỗi giữa giờ" mà không muốn kích hoạt toàn bộ pipeline ghi file. Câu hỏi cốt lõi:

> *"Làm sao để kiểm tra goal drift ngay khi đang code, mà không làm hỏng index hay tạo log nửa vời?"*

Ràng buộc:
- `scribe` là lệnh **Destructive** (ghi file + xóa rác) — không thể dùng để "xem nhanh"
- Cần một lệnh **Read-only, idempotent** — chạy bao nhiêu lần cũng an toàn
- Git diff phải lấy từ **thư mục project** (CWD), không phải từ Vault

---

## 📍 Quyết định (The Chosen Path)

> **Đã chọn: Cách 3 — Tách nghiệp vụ hoàn toàn: `scribe` (Destructive) + `audit` (Read-only)**

**Lý do chọn:**
- Tuân thủ nguyên tắc **Single Responsibility Principle (SRP)** — mỗi lệnh làm đúng 1 việc
- `audit` là **idempotent** hoàn toàn — gọi 10 lần cho kết quả như nhau, không phá gì
- Prompt riêng cho `audit` (ngắn, nhiệt độ 0.1) → nhanh hơn, ít hallucinate hơn `scribe`
- Auto-scan `implementation_plan.md` theo `mtime` → tự động kích hoạt Hard Audit khi có Plan

**Trade-off chấp nhận:**
- Phải maintain 2 subcommand và 2 system prompt riêng biệt trong cùng 1 script
- User cần nhớ: `audit` (giữa giờ) vs `scribe` (cuối ngày)

---

## 🚫 Các con đường đã loại bỏ (Rejected Paths)

### ❌ Cách 1 — "Silent Assassin": Giữ nguyên `scribe`, ẩn bớt output Terminal

- **Loại từ vòng:** Lý thuyết (ngay khi phân tích)
- **Lý do:** Vi phạm SRP — vẫn là lệnh Destructive dù có "giấu" output. Một lần gõ nhầm giữa giờ → tạo log nửa vời + xóa brief + chèn dòng thừa vào Index. Nguy hiểm hơn không làm gì
- **Bằng chứng:** Phân tích use case: "Xong module, chưa muốn nghỉ, chỉ hỏi có lệch Plan không" → `scribe` sẽ yêu cầu `@dump` trước → tạo file 1-way → không reversible

### ❌ Cách 2 — Thêm flag `--check` vào `scribe` (Ví dụ: `scribe --check`)

- **Loại từ vòng:** Lý thuyết
- **Lý do:** Chung subcommand nhưng rẽ nhánh logic → gây nhầm lẫn UX. User không biết `scribe --check` có ghi file không. "Giảm độ dài văn bản" ≠ "Tách biệt nghiệp vụ"

---

## 🔮 Đường tiềm năng chưa test (Future Paths)

### ⏳ Cách 4 — `audit` gọi qua Telegram bot

- **Lý thuyết:** User nhắn `/audit` từ điện thoại khi đang coding, bot tự `git diff` remote repo và trả về kết quả
- **Khi nào nên thử:** Phase 3.3 (Telegram integration)
- **Rủi ro dự đoán:** Cần SSH/API vào máy local hoặc CI/CD hook — phức tạp hơn nhiều

### ⏳ Cách 5 — `audit` chạy tự động khi `git commit`

- **Lý thuyết:** Git pre-commit hook → chạy audit → block commit nếu 🔴 GOAL DRIFT
- **Khi nào nên thử:** Khi workflow đã ổn định
- **Rủi ro dự đoán:** Gọi API Gemini mỗi commit → chậm + tốn tiền nếu commit nhiều

---

## 📊 Ma trận so sánh

| Tiêu chí | Cách 1 ❌ Silent Assassin | Cách 2 ❌ `--check` flag | **Cách 3 ✅ Tách lệnh** | Cách 4 ⏳ Telegram | Cách 5 ⏳ Git hook |
|----------|--------------------------|--------------------------|-------------------------|--------------------|-------------------|
| Read-only? | ❌ (vẫn ghi file) | ⚠️ (tùy flag) | **✅ hoàn toàn** | ✅ | ✅ |
| Idempotent? | ❌ | ⚠️ | **✅** | ✅ | ✅ |
| Cần @dump? | ✅ (phụ thuộc) | ✅ (phụ thuộc) | **❌ độc lập** | ❌ | ❌ |
| UX rõ ràng? | ❌ dễ nhầm | ❌ dễ nhầm | **✅ tường minh** | ✅ | ✅ |
| Đã test? | ❌ | ❌ | **✅** | ❌ | ❌ |

---

## 🐛 Bug phát hiện trong quá trình implement

**Bug: UUID sort thay vì mtime sort**

Khi auto-scan `implementation_plan.md` trong `.gemini/antigravity/brain/`, code dùng `sorted(dirs, reverse=True)` sắp xếp UUID theo alphabet. UUID không có thứ tự thời gian → chọn nhầm Plan của conversation cũ (Airwallex).

**Fix:** `sorted(dirs, key=lambda p: p.stat().st_mtime, reverse=True)`

**Test thực tế:** Lần đầu audit trả về `🔴 GOAL DRIFT — liên quan Airwallex`. Sau fix → `✅ On-track`.

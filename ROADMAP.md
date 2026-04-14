# 🗺️ Shadow Scribe — ROADMAP

> Tài liệu này theo dõi **các phase đã hoàn thành** và **kế hoạch tương lai** của hệ thống.  
> Project Index chi tiết hơn (timeline session + ADR): [`agent_vault/projects/shadow-scribe/PROJECT_INDEX.md`](../agent_vault/projects/shadow-scribe/PROJECT_INDEX.md)

---

## ✅ Đã hoàn thành

### Phase 1 — `@dump` Protocol *(14/04/2026)*
**Mục tiêu:** Thiết lập cơ chế "Anti chỉ làm việc nhẹ nhất có thể".

- Anti (IDE Agent) viết `session_brief.md` ~15 dòng vào `raw_logs/`
- Gom artifacts tạm → `~/Documents/agent_vault/artifacts/YYYY-MM/`
- Chụp `git diff` → `raw_logs/git_diff.txt`
- **Nguyên tắc cốt lõi:** Gemini Flash làm heavy lifting, Anti dùng context window cho code

**ADR liên quan:** [ADR-001 — Watchdog Architecture](../agent_vault/projects/shadow-scribe/adr/001_watchdog_architecture.md)

---

### Phase 2 — `watchdog scribe` *(14/04/2026)*
**Mục tiêu:** Tự động hóa việc viết Session Log từ brief + git diff.

- Gemini Flash đọc `session_brief.md` + `git_diff.txt` → tổng hợp Full Session Log
- Ghi file `sessions/YYYY-MM/DD_MM_YY.md`
- Chèn 1 dòng vào `00_INDEX_MATRIX.md` (không phá format bảng)
- Dọn sạch `raw_logs/` sau khi xong
- `--mock` flag để dry-run không ghi file

---

### Phase 3.1 — `watchdog audit` *(14/04/2026)*
**Mục tiêu:** Cho phép "soi lỗi giữa giờ" mà không kích hoạt pipeline ghi file.

- Read-only, idempotent — chạy bao nhiêu lần cũng an toàn
- **Hard Audit:** Có `implementation_plan.md` → đối chiếu git diff vs plan → phát hiện Goal Drift
- **Soft Audit:** Không có plan → chỉ review git diff
- Auto-scan plan theo `mtime` (fix bug UUID sort → tránh load nhầm plan cũ)
- Lấy `git diff` từ CWD (thư mục project), không phải vault

**Bug đã fix:** UUID sort → mtime sort  
**ADR liên quan:** [ADR-002 — Dual-Tier Audit](../agent_vault/projects/shadow-scribe/adr/002_dual_tier_audit.md)

---

### Phase 3.2 — `watchdog digest` *(14/04/2026)*
**Mục tiêu:** Tổng hợp nhiều sessions thành 1 bản digest theo project filter.

- Scan toàn bộ `sessions/YYYY-MM/*.md` trong vault
- Filter theo `--project` (parse `**Project:**` từ session header)
- Filter theo `--last N` ngày (parse date từ filename `DD_MM_YY.md`)
- Truncate tự động nếu vượt 900K chars (fit Gemini 1M context)
- Dual output: in terminal + ghi file `digests/{project}_{date}.md`
- Không ghi đè file cũ cùng ngày (tự thêm counter)

---

## 🔜 Kế hoạch

### Phase 4 — Telegram Integration *(Planned)*
**Mục tiêu:** Chạy audit & digest từ xa qua Telegram bot.

**Scope dự kiến:**
- `/audit` từ điện thoại → bot SSH vào máy → chạy `watchdog audit` → trả kết quả
- `/digest shadow-scribe` → tổng hợp và reply trực tiếp trên Telegram
- Notification tự động nếu audit phát hiện 🔴 GOAL DRIFT

**Vấn đề cần giải quyết trước:**
- Bot cần reach máy local (SSH tunnel? ngrok? hay webhook?)
- Bảo mật: không expose API key qua Telegram

**Tham khảo:** [ADR-002, Cách 4 — Telegram bot](../agent_vault/projects/shadow-scribe/adr/002_dual_tier_audit.md)

---

### Phase 5 — Kỷ luật Tư duy với Sequential Thinking (Planned)
**Mục tiêu:** Chống lại sự vội vã và "ảo giác" của LLM trước khi gõ code bằng cơ chế Internal Monologue (Tư duy chậm - System 2).

**Scope dự kiến:**
- Tích hợp server `sequentialthinking` của MCP làm "Hệ điều hành Tư duy" bắt buộc cho Anti.
- Ép Anti phải làm chủ bài toán: Tự chia nhỏ yêu cầu, tạo rẽ nhánh (branching) để cân nhắc các Option, và tự phản biện/sửa sai (Self-Correction) *trước khi* thực thi lệnh sửa file.
- Watchdog sẽ capture lại toàn bộ "Dấu vết tư duy" (thought nodes) này để đẩy thẳng vào Session Log, cấu thành những tài liệu ADR chi tiết phản ánh đúng bản chất kỹ thuật nhất.

**Tham khảo:** [`modelcontextprotocol/sequentialthinking`](https://github.com/modelcontextprotocol/servers/blob/main/src/sequentialthinking/README.md)

---

### Phase 6 — Tự trị Ký ức với Graph-RAG & Progressive Disclosure (Planned)
**Mục tiêu:** Biến Vault tĩnh thành một "Bộ não Động" (Autonomous Brain), cho phép Anti tự động truy vết bối cảnh (Auto Cold-start) theo định hướng của User mà không cần nhồi Vector DB cồng kềnh.

**Scope dự kiến:**
- Áp dụng triết lý "Tiết lộ lũy tiến" (Progressive Disclosure) và "Cổng Đọc quyết định" (File-read Decision Gate) học theo thiết kế của `claude-mem`.
- Thiết lập một MCP Tool siêu nhẹ cấp quyền cho Anti query thẳng vào `00_INDEX_MATRIX.md` giống như một giao điểm Root.
- Workflow Tự trị: User ra lệnh vibe chung ("Làm tính năng Z giống hồi bữa"). Anti tự động gọi lệnh đọc Index -> Xác định project liên quan -> Men theo đường link Markdown để gọi Tool đọc `PROJECT_INDEX.md` -> Đi dọc timeline để lôi `ADR-004.md` ra làm context.
- User ủy quyền mảng "Lục lọi tài liệu" hoàn toàn cho năng lực liên kết logic của Agent.

**Tham khảo:** [`thedotmack/claude-mem`](https://github.com/thedotmack/claude-mem)

---

## 📊 Status Overview

| Phase | Mô tả | Status | Version |
|-------|-------|--------|---------|
| 1 | `@dump` Protocol | ✅ Done | 1.0.0 |
| 2 | `watchdog scribe` | ✅ Done | 1.0.0 |
| 3.1 | `watchdog audit` (Hard + Soft) | ✅ Done | 1.0.1 |
| 3.2 | `watchdog digest` (project-filtered) | ✅ Done | 1.1.0 |
| 4 | Telegram Integration | ⚪ Planned | — |
| 5 | Sequential Thinking (Internal Monologue) | 🔮 Future | — |
| 6 | Autonomous Graph-RAG Vault | 🔮 Future | — |

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

### Phase 5 — Git Pre-commit Hook *(Đường tiềm năng)*
**Mục tiêu:** Tự động audit trước mỗi `git commit`.

```bash
# .git/hooks/pre-commit
watchdog audit || exit 1   # Block commit nếu 🔴 GOAL DRIFT
```

**Trade-off:** Gọi Gemini API mỗi commit → chậm + tốn tiền nếu commit nhiều lần.  
**Khi nào thử:** Khi workflow đã ổn định và cần guardrail mạnh hơn.

---

### Phase 6 — `watchdog --digest` Weekly/Monthly Auto-report *(Đường tiềm năng)*
**Mục tiêu:** Chạy digest định kỳ bằng cron job.

```bash
# Cron: mỗi thứ Hai 9h sáng
0 9 * * 1 watchdog digest --project shadow-scribe --last 7
```

---

## 📊 Status Overview

| Phase | Mô tả | Status | Version |
|-------|-------|--------|---------|
| 1 | `@dump` Protocol | ✅ Done | 1.0.0 |
| 2 | `watchdog scribe` | ✅ Done | 1.0.0 |
| 3.1 | `watchdog audit` (Hard + Soft) | ✅ Done | 1.0.1 |
| 3.2 | `watchdog digest` (project-filtered) | ✅ Done | 1.1.0 |
| 4 | Telegram Integration | ⚪ Planned | — |
| 5 | Git Pre-commit Hook | 🔮 Future | — |
| 6 | Cron Auto-report | 🔮 Future | — |

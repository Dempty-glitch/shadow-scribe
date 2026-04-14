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

### Phase 5 — Kỷ luật Tư duy: Ăn Protocol, Không Ăn Server (Planned)
**Mục tiêu:** Chống lại sự vội vã và "ảo giác" của LLM trước khi gõ code bằng cơ chế Internal Monologue (Tư duy chậm — System 2, Daniel Kahneman).

**Insight kiến trúc (từ phân tích source code `sequentialthinking`):**  
Server MCP Sequential Thinking thực chất chỉ là ~200 dòng TypeScript làm `array.push()`. Không có AI, không có logic — giá trị thật nằm ở **PROTOCOL** (JSON Schema buộc agent khai báo trước khi làm). Vì vậy: **ăn protocol, không ăn server**.

```
Sequential Thinking MCP = Vỏ rỗng (server) + Hạt vàng (protocol)
                               ↓                     ↓
                          KHÔNG ĂN               ĂN CÁI NÀY
```

**Scope triển khai — 3 Tầng tiến hóa:**

**Tầng 1: Prompt-Only (Zero code, triển khai ngay)**
- Nhúng "Thinking Protocol" vào System Prompt / `.cursorrules`.
- Buộc Agent phải viết section `## Thought Trace` trong `session_brief.md` TRƯỚC KHI code.
- Gồm 4 bước bắt buộc: Decompose → Branch → Self-Correct → Commit.
- `watchdog scribe` tự nhiên capture thought trace vì nó nằm trong session_brief.
- Enforcement: `watchdog audit` sẽ catch nếu agent skip thinking.

**Tầng 2: Watchdog Verify (~10 dòng Python)**
- Thêm check vào `watchdog scribe`: nếu `session_brief.md` thiếu `## Thought Trace` → in cảnh báo vào log.
- Biến Watchdog thành **gác cổng tư duy** — audit trail tự động ghi nhận thiếu kỷ luật.

**Tầng 3: Native MCP Tool (Khi Shadow Scribe thành MCP)**
- Thêm tool `think` như tool nội bộ của Shadow Scribe MCP Server.
- Nhận JSON giống schema Sequential Thinking → append vào `thought_trace.jsonl` trong vault.
- `watchdog scribe` đọc file này khi tạo session log.
- ~30 dòng Python, tích hợp nguyên bản, không cần Node.js hay server riêng.

**Tham khảo gốc:** [`modelcontextprotocol/sequentialthinking`](https://github.com/modelcontextprotocol/servers/blob/main/src/sequentialthinking/README.md) — *Protocol adopted, server discarded.*

---

### Phase 6 — Autonomous Vault Query với Progressive Disclosure (Planned)
**Mục tiêu:** Đạt được khả năng RAG 3-Layer giống claude-mem **nhưng giữ vững nguyên tắc Zero-Dependency**. Không cần SQLite, ChromaDB, Bun, hay bất kỳ Vector DB cồng kềnh nào. Shadow Scribe đã có sẵn "Relational Markdown Database" — chỉ cần thêm thao tác truy vấn vào nó.

**Insight kiến trúc cốt lõi (từ Deep-Dive claude-mem):**  
Chúng ta đã vô tình xây sẵn bộ xương 3-Layer mà claude-mem mất 1,662 commits mới có:

| Layer | claude-mem         | Shadow Scribe (đã có!)         |
|-------|--------------------|-------------------------------|
| 1 — Index   | SQLite FTS5        | `00_INDEX_MATRIX.md` |
| 2 — Timeline | `timeline` API    | `PROJECT_INDEX.md`   |
| 3 — Details  | `get_observations` | `sessions/*.md` + `adr/*.md` |

**Scope triển khai:**

**a) `watchdog query` — Layer 1 Tool (Core)**
- Thêm subcommand `watchdog query <từ_khóa>` vào `watchdog_scribe.py`.
- Thực chất là grep nhanh chuỗi keyword vào `00_INDEX_MATRIX.md`.
- Trả về các dòng index khớp + đường link Markdown tới Layer 2/3.
- Agent đọc output ngắn này (Layer 1) → tự quyết định có follow link không.
- **Zero new dependency** — dùng Python stdlib `re` / `str.find()` thuần túy.

```bash
watchdog query "thanh toán stripe"
# → [shadow-scribe] 2026-04-14: feat: Stripe PaymentIntent + webhook | ADR-004 | sessions/04-2026/14_04_26.md
# → [z-zero]        2026-03-15: fix: idempotency key collision           | sessions/03-2026/15_03_26.md
```

**b) Auto Context Injection — System Prompt (`.cursorrules`)**
- Giải quyết Cold-start bằng cách ép Agent phải gọi `watchdog query` trước khi bắt đầu task cũ.
- Ví dụ rule trong `.cursorrules` hoặc `CLAUDE.md`:
  ```
  Khi user nhắc đến task/dự án cũ → LUÔN gọi `watchdog query <từ khóa>` trước.
  Đọc Layer 1 output → Follow link nếu thấy relevant → Load context từ Layer 3.
  KHÔNG làm gì cho đến khi có context.
  ```
- **Zero new dependency** — chỉ là Prompt Engineering.

**c) Icon Classification trong Session Log (Optional Enhancement)**
- Sửa `SYSTEM_PROMPT` trong `watchdog_scribe.py`: thêm hướng dẫn phân loại mỗi key finding bằng icon vocabulary từ claude-mem.
- Kết quả: `00_INDEX_MATRIX.md` sẽ có thêm cột `Type` với ký hiệu 🔴🟤⚖️ — Agent scan nhanh hơn.

**Tham khảo:** [`thedotmack/claude-mem`](https://github.com/thedotmack/claude-mem) — [Deep Dive Analysis](../../.gemini/antigravity/brain/3a8addd1-320f-4da8-bca7-57a941487327/claude_mem_analysis.md)

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
| 6 | Autonomous Vault Query (Zero-Dep RAG) | 🔮 Future | — |


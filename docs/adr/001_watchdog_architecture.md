# ADR-001: Watchdog Architecture

| Field | Value |
|-------|-------|
| **Ngày tạo** | 14/04/2026 |
| **Project** | shadow-prominence |
| **Status** | 🟢 ACCEPTED |
| **Session liên quan** | [→](../../sessions/2026-04/14_04_26.md) |

## Context (Bài toán)
Anti (IDE Agent) hoạt động khép kín — không lưu chat transcript ra disk. Cần thiết kế watchdog để giám sát và ghi nhớ lịch sử phiên làm việc mà không can thiệp vào luồng code chính.

---

## 📍 Quyết định (The Chosen Path)

> **Đã chọn: Cách 4 — File System là Message Broker**

**Mô tả:** Anti chỉ dump `session_brief.md` + gom artifacts. Python script + Gemini Flash đọc data và viết full session log. File System là kênh giao tiếp giữa 2 agent.

**Lý do chọn:**
- Zero coupling — Anti và Watchdog không biết nhau tồn tại
- Gemini Flash 1M context, rất rẻ (~$0.001/session) làm heavy lifting
- Durable — vault tồn tại độc lập, Anti có bị xóa cài lại vault vẫn nguyên

**Trade-off chấp nhận:** Watchdog thiếu "How" data (không có chat transcript) — bù bằng `session_brief.md` chi tiết hơn 3 dòng (10-15 dòng)

---

## 🚫 Các con đường đã loại bỏ (Rejected Paths)

### ❌ Cách 1 — Anti tự viết full Session Log
- **Loại từ vòng:** Lý thuyết
- **Lý do:** Tốn Claude Opus tokens đắt tiền (~$0.38/session thay vì $0.001). Anti dùng context window quý để viết log thay vì code.

### ❌ Cách 2 — claude-mem plugin (hooks + SQLite + Bun worker)
- **Loại từ vòng:** Lý thuyết
- **Lý do:** Chỉ dành cho Claude Code CLI. Antigravity không có hook system tương thích. Tốn thêm Claude API calls cho mỗi observation. Cần cài Bun runtime.

### ❌ Cách 3 — MCP Server (Anti gọi Watchdog real-time)
- **Loại từ vòng:** Lý thuyết (không test thực tế)
- **Lý do:** Yêu cầu Anti và Watchdog giao tiếp 2 chiều real-time. Overkill cho nhu cầu post-session review. User không cần real-time feedback trong V1.

---

## 🔮 Đường tiềm năng chưa test (Future Paths)

### ⏳ Cách 5 — Real-time Audit (Phase 2 roadmap)
- **Lý thuyết:** Watchdog chạy daemon, cứ 15 phút audit `git diff` vs `implementation_plan.md`, ping Telegram nếu lệch plan
- **Khi nào nên thử:** Khi Phase 1+2+3 đã ổn định và user muốn thêm real-time guardrail
- **Rủi ro dự đoán:** Nhiều false positive alerts nếu Gemini Flash không hiểu đủ context

### ⏳ Cách 6 — Antigravity Native Integration
- **Lý thuyết:** Nếu Antigravity sau này expose hook API (như Claude Code), có thể dùng pattern giống claude-mem
- **Khi nào nên thử:** Khi platform support
- **Rủi ro dự đoán:** Phụ thuộc vào platform roadmap, ngoài tầm kiểm soát

---

## 📊 Ma trận so sánh

| Tiêu chí | Cách 1: Anti tự làm ❌ | Cách 2: claude-mem ❌ | Cách 3: MCP real-time ❌ | **Cách 4: File System ✅** | Cách 5: Real-time ⏳ |
|----------|----------------------|---------------------|------------------------|--------------------------|---------------------|
| Chi phí token | Cao ($0.38) | Cao (Claude API) | TB | **Rất thấp ($0.001)** | TB |
| Complexity | Thấp | Cao | Cao | **Thấp** | Cao |
| Anti context impact | Lớn | 0 | Nhỏ | **Rất nhỏ** | 0 |
| Durable | ✅ | ✅ | ✅ | **✅** | ✅ |
| Cần cài thêm | Không | Bun, ChromaDB | Không | **Python (đã có)** | Telegram bot |
| Đã test? | ❌ | ❌ | ❌ | **✅ Build Phase 1+2** | ❌ |

# 🛡️ Shadow Scribe

> **The Execution Brain & Shadow Scribe Architecture.**  
> Hệ thống Quản trị Tri thức, Giám sát và Kiểm toán (Audit) vĩnh cửu dành cho AI Agents (Cursor, Windsurf, Antigravity).

[![Version](https://img.shields.io/badge/version-1.1.0-blue.svg)]()
[![Python](https://img.shields.io/badge/python-%E2%89%A5%203.9-brightgreen.svg)]()
[![Zero Dependency](https://img.shields.io/badge/dependencies-0-success.svg)]()
[![Powered by Gemini](https://img.shields.io/badge/Powered%20by-Gemini%202.5%20Flash-orange.svg)]()

---

## 🛑 Nỗi đau của AI IDEs (The Problem)

Các AI IDE hiện nay đều mắc chung 2 căn bệnh chí mạng:

1. **Mất trí nhớ (Context Decay):** Khi kết thúc phiên làm việc, AI quên sạch bối cảnh. Bắt AI đọc lại log cũ sẽ đốt hàng ngàn token đắt đỏ (Opus/Sonnet) một cách vô ích.
2. **Lệch hướng mục tiêu (Goal Drift):** AI tự ý thay đổi kiến trúc hoặc code sai lệch so với kế hoạch ban đầu mà không báo cáo.

---

## 💡 Giải pháp: Shadow Scribe (The Solution)

**Shadow Scribe** giải quyết triệt để vấn đề này bằng kiến trúc **Offloading (Chuyển giá)**:

- **IDE Agent (Anti):** Chỉ tập trung 100% Context Window vào việc gõ code. Cuối ngày chỉ nhả ra 15 dòng tóm tắt siêu nhẹ.
- **Watchdog (Python Script):** Chạy ngầm bên ngoài, sử dụng **Gemini 2.5 Flash** (1 Triệu token context, Free tier) để đọc Git Diff, đối chiếu Kế hoạch, soi lỗi, và tổng hợp thành một **Ma trận Tri thức (Knowledge Matrix)** vĩnh cửu.

---

## ✨ Tính năng nổi bật (Key Features)

- 🪶 **Zero-Dependency:** Script Python viết bằng 100% thư viện chuẩn (`urllib`, `json`, `pathlib`). Không cần `pip install`, không rác hệ thống.
- 🧠 **Dual-Tier Audit (Kiểm toán Kép):**
  - *Soft Audit:* Quét `git diff` để tìm lỗi logic.
  - *Hard Audit:* Tự động tìm `implementation_plan.md` theo `mtime`, đối chiếu chéo với code thực tế để bắt quả tang AI "lươn lẹo" (Goal Drift).
- 🗄️ **Persistent Knowledge Matrix:** Mọi phiên làm việc được nén thành Markdown chuẩn và liên kết trong `00_INDEX_MATRIX.md`.
- 📊 **Project Digest:** Tổng hợp N session logs thành báo cáo tiến độ, filter theo project và khoảng thời gian.
- 🛡️ **Bulletproof I/O:** Chống ghi đè file, tự truncate nếu vượt 900K chars, tự fallback `git diff HEAD~1` nếu không có staged changes.

---

## 🏗️ Sơ đồ Kiến trúc (Architecture)

```mermaid
graph TD
    subgraph IDE ["IDE / AI Agent (Anti)"]
        A["Code & Thảo luận"] -->|@adr| B("Tạo ADR - Quyết định Kiến trúc")
        A -->|@dump| C("Viết session_brief 15 dòng + git diff")
    end

    subgraph OS ["Terminal / Watchdog Script"]
        C --> D{"watchdog_scribe.py"}
        Plan["implementation_plan.md"] -.->|Hard Audit| D
    end

    subgraph Cloud ["LLM API"]
        D <-->|HTTP Call| E(("Gemini 2.5 Flash"))
    end

    subgraph Vault ["Agent Vault  ~/Documents/agent_vault/"]
        B --> F["projects/adr/"]
        E -->|watchdog scribe| G["sessions/YYYY-MM/"]
        E -->|1 dòng index| H["00_INDEX_MATRIX.md"]
        E -->|watchdog digest| I["digests/"]
    end
```

---

## 📸 Showcase

> **1. Bắt quả tang Goal Drift bằng `watchdog audit`:**

![Audit Demo](docs/audit-demo.png)

> **2. Ma trận Tri thức tự động sinh ra trong `00_INDEX_MATRIX.md`:**

![Matrix Demo](docs/matrix-demo.png)

---

## 🚀 Cài đặt (Setup — Làm 1 lần duy nhất)

### Bước 1 — Set Gemini API Key
Lấy API Key miễn phí tại [Google AI Studio](https://aistudio.google.com/), thêm vào `~/.zshrc`:
```bash
export GEMINI_API_KEY="your_gemini_api_key_here"
```

### Bước 2 — Thêm `watchdog` function vào `~/.zshrc`
Copy toàn bộ block này vào cuối file `~/.zshrc`:
```bash
# ─── Shadow Scribe Watchdog ───────────────────────────
#   watchdog scribe                          → cuối ngày, ghi Session Log + Index
#   watchdog scribe --mock                   → dry-run, không ghi file
#   watchdog audit                           → soi goal drift (read-only)
#   watchdog audit --plan /path/to/plan.md   → chỉ định rõ file plan
#   watchdog digest                          → tổng hợp tất cả sessions
#   watchdog digest --project shadow-scribe --last 30
function watchdog() {
    python3 ~/Documents/shadow\ scribe/watchdog_scribe.py "$@"
}
# ──────────────────────────────────────────────────────
```

### Bước 3 — Reload và test
```bash
source ~/.zshrc
watchdog --help
```

---

## 🕹️ Hướng dẫn sử dụng (Workflow)

### Trong lúc Code (Giao tiếp với AI IDE)
- **Chốt kiến trúc:** Gõ `@adr [Tên vấn đề]` → AI tạo ngay "Bản đồ đường sống/đường chết" lưu vào Vault.
- **Kết thúc ngày:** Gõ `@dump` → AI viết 15 dòng tóm tắt và chụp `git diff` ra file tạm.

### Trên Terminal (Sức mạnh của Watchdog)

| Lệnh | Chức năng | Loại |
| :--- | :--- | :--- |
| `watchdog audit` | **(Dùng giữa giờ)** Soi Goal Drift ngay lập tức | 🟢 READ-ONLY |
| `watchdog audit --plan /path` | Hard Audit với plan chỉ định rõ | 🟢 READ-ONLY |
| `watchdog scribe` | **(Dùng cuối ngày)** Gọi Gemini viết Full Log, cập nhật Index, dọn rác | 🔴 DESTRUCTIVE |
| `watchdog scribe --mock` | Dry-run: chỉ print, không ghi file | 🟢 READ-ONLY |
| `watchdog digest` | **(Dùng cuối tuần)** Tổng hợp tất cả sessions thành báo cáo | 🟡 READ + WRITE |
| `watchdog digest --project NAME` | Filter theo project (vd: `shadow-scribe`, `z-zero`) | 🟡 READ + WRITE |
| `watchdog digest --last N` | Chỉ lấy N ngày gần nhất (vd: `--last 30`) | 🟡 READ + WRITE |

<details>
<summary>📋 Chi tiết flags & input requirements</summary>

**`watchdog scribe` cần có trước khi chạy:**
```
~/Documents/agent_vault/raw_logs/
├── session_brief.md   # Anti viết qua @dump (~15 dòng)
└── git_diff.txt       # Chụp bằng lệnh bên dưới
```
```bash
# Từ thư mục project:
git diff > ~/Documents/agent_vault/raw_logs/git_diff.txt
# Nếu không có staged changes:
git show HEAD > ~/Documents/agent_vault/raw_logs/git_diff.txt
```

**`watchdog audit` auto-scan `implementation_plan.md`:**
1. Tìm trong CWD (thư mục project hiện tại)
2. Nếu không có → tìm trong `.gemini/antigravity/brain/` (mtime-sort, lấy conversation mới nhất)
3. **Hard Audit** nếu tìm thấy plan | **Soft Audit** nếu không có

**Output `watchdog digest` lưu tại:**
```
~/Documents/agent_vault/digests/{project}_{YYYY-MM-DD}.md
```
*(Không ghi đè file cũ cùng ngày — tự thêm counter `_1`, `_2`...)*

</details>

---

## 🗂️ Cấu trúc Vault (Data Taxonomy)

```
~/Documents/agent_vault/
├── 00_INDEX_MATRIX.md          # Master Index — Bảng mục lục vĩnh cửu
├── raw_logs/                   # Trạm trung chuyển (Watchdog đọc xong sẽ xóa)
│   ├── session_brief.md        # Anti viết (~15 dòng)
│   └── git_diff.txt            # git diff snapshot
├── sessions/                   # Full Session Logs (Gemini Flash tổng hợp)
│   └── YYYY-MM/DD_MM_YY.md
├── digests/                    # Báo cáo tổng hợp từ watchdog digest
│   └── {project}_{date}.md
├── artifacts/                  # File nháp, schema, migration gom từ các phiên
│   └── YYYY-MM/
└── projects/
    └── {project_name}/
        ├── PROJECT_INDEX.md    # Timeline + Key Decisions + Roadmap
        └── adr/                # Architecture Decision Records (Hiến pháp dự án)
```

---

## ⚙️ Config

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `GEMINI_API_KEY` | *(required)* | Google AI API Key — [lấy miễn phí tại đây](https://aistudio.google.com/) |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model dùng cho scribe + audit + digest |
| `VAULT_DIR` | `~/Documents/agent_vault/` | Root của vault |

---

## 🗺️ Roadmap

- [x] **Phase 1 & 2:** Giao thức `@dump`, `@adr` và Cấu trúc Vault cơ bản.
- [x] **Phase 3.1:** `watchdog audit` — Dual-Tier Audit (Hard + Soft), read-only.
- [x] **Phase 3.2:** `watchdog digest` — Project-filtered summary, dual output.
- [ ] **Phase 4:** Tích hợp Telegram Bot — nhận cảnh báo Goal Drift qua điện thoại.
- [ ] **Phase 5:** Git Pre-commit Hook — tự động chặn commit nếu Audit phát hiện lỗi.

---

## 📚 Tài liệu liên quan

- [ROADMAP.md](ROADMAP.md) — Chi tiết phases đã xong & kế hoạch
- [Project Index](../agent_vault/projects/shadow-scribe/PROJECT_INDEX.md) — Timeline sessions
- [ADR Index](../agent_vault/projects/shadow-scribe/adr/ADR_INDEX.md) — Quyết định kiến trúc (3 ADRs)

---

*Được thiết kế với kỷ luật kỹ thuật khắt khe. Shadow Scribe không làm thay bạn — nó giúp bạn và AI không bao giờ đi lạc.*

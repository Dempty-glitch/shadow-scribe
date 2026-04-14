# 🛡️ Shadow Scribe — Watchdog System

> **Não Thực Thi & Thư Ký Bóng Tối** — Hệ thống ghi nhớ & kiểm toán phiên làm việc cho AI Agent  
> **Version:** 1.1.0 | **Python:** ≥ 3.9 | **Vault:** `~/Documents/agent_vault/`

---

## 🚀 Quick Start

```bash
# 1. Set API key (thêm vào ~/.zshrc để dùng mỗi ngày)
export GEMINI_API_KEY="your_key_here"

# 2. Thêm alias vào ~/.zshrc để gọi từ bất kỳ thư mục nào
echo 'function watchdog() { python3 ~/Documents/shadow\ scribe/watchdog_scribe.py "$@"; }' >> ~/.zshrc
source ~/.zshrc

# 3. Test
watchdog --help
```

---

## 📖 Command Reference

### `watchdog scribe` — Cuối phiên: ghi Session Log

> ⚠️ **DESTRUCTIVE** — Ghi file + xóa raw_logs. Chỉ chạy cuối phiên làm việc, SAU KHI đã `@dump`.

```bash
watchdog scribe            # Chạy thật: ghi Session Log + cập nhật Index
watchdog scribe --mock     # Dry-run: chỉ print output, không ghi file nào
```

**Luồng hoạt động:**
1. Anti (IDE Agent) viết `session_brief.md` → `~/Documents/agent_vault/raw_logs/`
2. Chạy `git diff` → `git_diff.txt`
3. `watchdog scribe` đọc brief + diff → gọi Gemini Flash → tổng hợp Session Log
4. Ghi file vào `sessions/YYYY-MM/DD_MM_YY.md`
5. Chèn 1 dòng vào `00_INDEX_MATRIX.md`
6. Dọn sạch `raw_logs/`

**Input cần có trước khi chạy:**
```
~/Documents/agent_vault/raw_logs/
├── session_brief.md   # Anti viết qua @dump
└── git_diff.txt       # git diff > ~/Documents/agent_vault/raw_logs/git_diff.txt
```

---

### `watchdog audit` — Giữa phiên: kiểm tra Goal Drift

> ✅ **READ-ONLY** — Idempotent, không ghi file, không chạm Index. Chạy bao nhiêu lần cũng an toàn.

```bash
watchdog audit                              # Auto-scan implementation_plan.md
watchdog audit --plan /path/to/plan.md     # Chỉ định rõ file plan
```

**Logic auto-scan `implementation_plan.md`:**
1. Tìm trong CWD (thư mục hiện tại của project)
2. Nếu không có → tìm trong `.gemini/antigravity/brain/` (mtime-sort, lấy conversation mới nhất)
3. **Hard Audit** nếu tìm thấy plan — đối chiếu git diff vs plan
4. **Soft Audit** nếu không có plan — chỉ xem git diff

**Output mẫu:**
```
✅ On-track — Không phát hiện lệch hướng
⚠️ Minor drift — Thêm file logs/ chưa có trong plan (có thể chấp nhận)
🔴 GOAL DRIFT — Đang implement feature X không có trong plan
```

---

### `watchdog digest` — Tổng hợp nhiều sessions thành digest

> ✅ **READ-ONLY + GHI FILE** — Đọc session logs, gọi Gemini Flash, in terminal + lưu file.

```bash
watchdog digest                                         # Tất cả projects, tất cả thời gian
watchdog digest --project shadow-scribe                 # 1 project cụ thể
watchdog digest --project z-zero --last 30              # Z-ZERO trong 30 ngày gần nhất
watchdog digest --project shadow-scribe --last 7        # Shadow Scribe tuần này
```

**Filter options:**
| Flag | Mô tả | Ví dụ |
|------|-------|-------|
| `--project NAME` | Filter theo tên project trong session log header | `--project shadow-scribe` |
| `--last N` | Chỉ lấy sessions trong N ngày gần nhất | `--last 30` |

**Output lưu tại:** `~/Documents/agent_vault/digests/{project}_{YYYY-MM-DD}.md`  
_(Không ghi đè file cũ cùng ngày — tự thêm counter `_1`, `_2`...)_

---

## 🗂️ Vault Structure

```
~/Documents/agent_vault/
├── 00_INDEX_MATRIX.md          # Master index — mọi session trong 1 bảng
├── raw_logs/                   # Staging area (Anti dump vào đây, watchdog dọn sau)
│   ├── session_brief.md        # Anti viết (~15 dòng) — watchdog đọc xong xóa
│   └── git_diff.txt            # git diff snapshot — watchdog đọc xong xóa
├── sessions/
│   ├── 2026-03/
│   │   └── DD_MM_YY.md         # Full Session Log (Gemini Flash tổng hợp)
│   └── 2026-04/
│       └── DD_MM_YY.md
├── digests/
│   └── {project}_{date}.md     # Digest output từ `watchdog digest`
├── artifacts/
│   └── 2026-MM/                # File nháp, schema, migration được gom từ phiên
└── projects/
    ├── shadow-scribe/
    │   ├── PROJECT_INDEX.md    # Timeline + Key Decisions + Roadmap
    │   └── adr/                # Architecture Decision Records
    └── z-zero/
        └── PROJECT_INDEX.md
```

---

## 🔄 Workflow hàng ngày

```
Trong phiên làm việc:
  1. Code như bình thường
  2. Nếu ra quyết định kiến trúc quan trọng → gõ @adr {tên} → Anti tạo ADR
  3. Muốn check drift giữa giờ → watchdog audit (từ thư mục project)

Cuối phiên:
  4. Gõ @dump → Anti viết session_brief.md + chạy git diff
  5. watchdog scribe → Gemini Flash tổng hợp, ghi log, cập nhật Index

Định kỳ (hàng tuần / khi cần review):
  6. watchdog digest --project {tên} --last 7
```

---

## ⚙️ Config

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `GEMINI_API_KEY` | *(required)* | Google AI API Key |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model dùng cho scribe + audit + digest |
| `VAULT_DIR` | `~/Documents/agent_vault/` | Root của vault |

---

## 📚 Tài liệu liên quan

- [ROADMAP.md](ROADMAP.md) — Phases đã xong & kế hoạch
- [Vault / Project Index](../agent_vault/projects/shadow-scribe/PROJECT_INDEX.md) — Timeline sessions
- [ADR Index](../agent_vault/projects/shadow-scribe/adr/ADR_INDEX.md) — Quyết định kiến trúc

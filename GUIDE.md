# 🛡️ Shadow Scribe — Sổ tay Vận hành (v1.2.0)

> File này là **hướng dẫn vận hành duy nhất** cho AI Agent.
> Nếu bạn là Agent IDE (Antigravity, Cursor, Windsurf, Claude Code), hãy đọc hết file này trước khi hành động.
> Tài liệu chi tiết hơn: `~/Documents/shadow scribe/README.md`

---

## ⚙️ Nguyên tắc Kiến trúc

```
Agent IDE  = ĐIỀU PHỐI VIÊN — gom file, chạy lệnh, viết brief 15 dòng.
Watchdog   = BỘ NÃO         — đọc, phân tích, tổng hợp (dùng Gemini Flash).
```

⛔ Agent **KHÔNG BAO GIỜ** tự đọc log/conversation rồi tổng hợp thay Watchdog.
Watchdog script: `~/Documents/shadow scribe/watchdog_scribe.py`
API Key: tự động load từ file `~/Documents/agent_vault/.env`.
  *(⚠️ Phải dùng API chính hãng. Tuyệt đối không dùng API proxy trôi nổi để tránh lộ source code/bảo mật)*

---

## 📂 Cấu trúc Vault

```
~/Documents/agent_vault/
├── .env                        # GEMINI_API_KEY (auto-load, không cần export)
├── 00_INDEX_MATRIX.md          # Bảng mục lục vĩnh cửu tất cả sessions
├── raw_logs/                   # Trạm trung chuyển (tạm, Watchdog đọc xong sẽ dọn)
│   └── {project-name}/         # Mỗi project 1 thư mục riêng (kebab-case)
│       ├── session_brief.md    # Agent viết (~15 dòng)
│       └── git_diff.txt        # git diff snapshot
├── sessions/                   # Full Session Logs (Gemini Flash tổng hợp)
│   └── YYYY-MM/DD_MM_YY.md
├── trash/                      # Soft-Delete — raw_logs backup (tự dọn sau 30 ngày)
├── artifacts/                  # File nháp, plan, schema gom từ các phiên
├── digests/                    # Báo cáo tổng hợp từ watchdog digest
└── projects/
    └── {project_name}/
        ├── PROJECT_INDEX.md    # Timeline + Key Decisions
        └── adr/                # Architecture Decision Records
```

---

## 🗺️ Mapping Workspace → Project

| Workspace (tên folder code) | Project (tên trong vault) |
|------------------------------|---------------------------|
| `shadow-prominence`, `shadow scribe` | `shadow-scribe` |
| `ai-card-mcp`, `z-zero-dashboard`, `z-zero-mcp` | `z-zero` |
| `kya-network`, `kya-mcp-server` | `kya-network` |

> Nếu workspace chưa có trong bảng → tạo tên project mới bằng kebab-case, không dùng space.

---

## 🔄 Workflow mỗi phiên làm việc

### Đầu phiên — Nạp Context

Đọc lần lượt 3 file trước khi làm việc:
1. `~/Documents/agent_vault/00_INDEX_MATRIX.md` — Xem session gần nhất của dự án
2. `~/Documents/agent_vault/sessions/{YYYY-MM}/{session mới nhất}.md` — Đọc full log phiên trước
3. `~/Documents/agent_vault/projects/{project}/adr/ADR_INDEX.md` — Nắm các quyết định kiến trúc đã chốt

Tóm tắt ngắn cho user: đang ở đâu, pending gì, rồi mới bắt đầu code.

### Trong phiên — Code bình thường

- Ra quyết định kiến trúc quan trọng → Gõ `@adr [tên vấn đề]` (xem mục @adr bên dưới)
- Muốn kiểm tra giữa giờ → Gõ `audit đi` hoặc bất kỳ lệnh vibe tương đương

### Cuối phiên — @dump (3-in-1, tự động)

Khi user gõ `@dump`, `tổng kết đi`, hoặc ý tương tự:

**Bước 1:** Chạy lệnh terminal:
```bash
mkdir -p ~/Documents/agent_vault/raw_logs/{project_name}
git diff > ~/Documents/agent_vault/raw_logs/{project_name}/git_diff.txt
```

**Bước 2:** Viết file `~/Documents/agent_vault/raw_logs/{project_name}/session_brief.md`:
```markdown
# Session Brief
Date: YYYY-MM-DD
Project: {project_name}
Workspace: {workspace_path}
Conversation ID: {conv_id}
Plan Path: {path_tới_implementation_plan.md hoặc (none)}
Time: {HH:MM} - {HH:MM}

## FOCUS (Làm gì hôm nay?)
{Mục tiêu chính 1-2 câu}

## DONE (Đã hoàn thành)
- {Action cụ thể}

## DECISIONS (Quyết định quan trọng)
- {Quyết định}: {Lý do}

## PIVOTS & DEAD ENDS (Hướng đi đã bỏ)
- {Hướng AA}: {Lý do bỏ}

## BLOOD LESSONS (Lỗi đã gặp & Bài học) ⬅️ BẮT BUỘC
- {Bug}: {Mô tả} → {Cách fix}
- (Nếu trơn tru, ghi: "Luồng code trơn tru — không có lỗi.")

## RISKS (Rủi ro phát hiện)
- {Risk}: {Context}

## PENDING (Chưa xong → next session)
- {Việc chưa xong}

## ARTIFACTS DUMPED
- {tên file} → artifacts/YYYY-MM/{tên file}
- (none nếu không có)

## FILES CHANGED (quan trọng nhất)
- {path/file.ext} — {mô tả thay đổi}
```

**Bước 3:** Tự động gọi Watchdog (không cần user làm gì):
```bash
python3 ~/Documents/shadow\ scribe/watchdog_scribe.py scribe
```

**Bước 4:** Báo cáo kết quả cho user:
```
✅ Watchdog hoàn tất:
- Session Log → sessions/YYYY-MM/DD_MM_YY.md
- Index đã cập nhật | 🗑️ raw_logs → trash/
- [Risk nếu có / "Audit Pass" nếu không]
```

---

## 🔍 Watchdog Commands (chạy trên Terminal)

| Lệnh | Chức năng | Loại |
|-------|----------|------|
| `watchdog scribe` | Gọi Gemini viết Full Log, cập nhật Index, dọn rác | 🔴 WRITE |
| `watchdog scribe --mock` | Dry-run: chỉ print, không ghi file | 🟢 READ |
| `watchdog audit` | Soi Goal Drift ngay lập tức | 🟢 READ |
| `watchdog audit --plan /path` | Hard Audit với plan chỉ định | 🟢 READ |
| `watchdog digest` | Tổng hợp tất cả sessions thành báo cáo | 🟡 R+W |
| `watchdog digest --project NAME` | Filter theo project | 🟡 R+W |

> Lệnh thật khi chạy trên terminal:
> `python3 ~/Documents/shadow\ scribe/watchdog_scribe.py {command} [flags]`

---

## 🗺️ @adr — Ghi ADR ngay lúc ra quyết định

Khi user gõ `@adr [tên vấn đề]`:

1. Đọc `~/Documents/agent_vault/projects/{project}/adr/ADR_INDEX.md` → lấy số ADR tiếp theo
2. Tạo file `~/Documents/agent_vault/projects/{project}/adr/NNN_{ten_snake_case}.md`
3. Dùng template: Context → Quyết định đã chọn → Đường loại bỏ → Đường tiềm năng → Ma trận so sánh
4. Cập nhật `ADR_INDEX.md`

---

## ♻️ Retroactive Dump (dump bù khi quên)

Nếu user quên dump 1-2 ngày:
- Dùng `git log --since="{ngày}"` để gom code changes → viết brief → chạy watchdog
- Nếu user cung cấp conversation log → copy vào `raw_logs/{project}/` → gọi watchdog
- Lưu ý: **Watchdog đọc**, không phải Agent. Agent chỉ copy file và chạy lệnh.

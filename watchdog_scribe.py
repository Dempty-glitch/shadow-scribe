#!/usr/bin/env python3
"""
Shadow Scribe — watchdog_scribe.py
Watchdog agent: đọc session_brief + git diff → gọi Gemini Flash → tổng hợp session log

Usage:
  watchdog scribe                                         # Cuối ngày: ghi file + cập nhật Index (destructive)
  watchdog scribe --mock                                  # Dry-run với mock data, chỉ print
  watchdog audit                                          # Giữa giờ: soi goal drift (read-only, zero side effects)
  watchdog audit --plan /path/to/plan.md                  # Chỉ định rõ file plan
  watchdog digest                                         # Digest tất cả projects
  watchdog digest --project shadow-scribe                 # Digest 1 project cụ thể
  watchdog digest --project shadow-scribe --last 30       # Digest 30 ngày gần nhất
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import json
import re
import subprocess
import urllib.request
import urllib.error

# ─── CONFIG ───────────────────────────────────────────────────────────────────

VAULT_DIR = Path.home() / "Documents" / "agent_vault"
RAW_LOGS_DIR = VAULT_DIR / "raw_logs"
SESSIONS_DIR = VAULT_DIR / "sessions"
INDEX_FILE = VAULT_DIR / "00_INDEX_MATRIX.md"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"
VERSION = "1.1.0"  # Phase 3.2: digest subcommand

# ─── PROMPT ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Bạn là "Shadow Scribe" — AI archivist chuyên tổng hợp nhật ký phiên làm việc.
KHÔNG ĐƯỢC viết lời chào, lời giới thiệu, hay bọc output trong ```markdown```.
Trả về NỘI DUNG THUẦN trực tiếp, bắt đầu ngay bằng dấu #.

INPUT bạn nhận:
1. <SESSION_BRIEF> — Tóm tắt do agent chính ghi (đóng vai "la bàn")
2. <GIT_DIFF> — Thay đổi code thực tế (bằng chứng khách quan)

OUTPUT bạn PHẢI trả về ĐÚNG 2 phần, phân tách bằng dòng ===INDEX===

─── PHẦN 1: Full Session Log (Markdown) ───

# 🛡️ Session Log: {ngày từ brief}
**Project:** `{project}` | **Workspace:** `{workspace}`
**Thời gian:** {time} | **Conversation ID:** {conv_id}

## 📊 Matrix Tổng Quan
| Phạm vi | Nội dung | Trạng thái |
|---------|----------|------------|
| 🎯 Mục tiêu | {tóm từ FOCUS} | 🟢/🟡/🔴 |
| 🔧 Thực hiện | {tóm từ DONE} | 🟢/🟡/🔴 |
| 💡 Quyết định | {tóm từ DECISIONS} | 🟢/🟡/🔴 |
| ⚠️ Rủi ro | {tóm từ RISKS} | 🟢/🟡/🔴 |
| 📌 Tồn đọng | {tóm từ PENDING} | ⚪ |

## ⏱️ Timeline
Suy luận thứ tự hành động từ brief + diff. Viết dạng bullet:
- **Action 1:** Mô tả
- **Action 2:** Mô tả

## 🔧 Code Changes (từ git diff)
Chỉ liệt kê các file CÓ THAY ĐỔI LOGIC QUAN TRỌNG (thêm/sửa/xóa hàm, fix bug, đổi flow).
BỎ QUA: đổi tên biến hàng loạt, format lại code, thay đổi comment, cập nhật version number.
Tối đa 10 file. Nếu vượt, gom phần còn lại thành 1 dòng "và N file khác (cosmetic changes)".

| File | Action | Mô tả thay đổi |
|------|--------|----------------|
{Parse từ git diff. KHÔNG ĐƯỢC bịa file không có trong diff}

## 💡 Quyết định quan trọng
{Liệt kê từ DECISIONS trong brief. Giữ nguyên ý, có thể diễn đạt rõ hơn}

## ⚠️ Risks & Bài học
{Liệt kê từ RISKS. Mỗi risk ghi severity 🔴/🟡/🟢}

## ✅ Status
- [x] {từ DONE}
- [ ] {từ PENDING}

## 🔄 Next Session
{Từ PENDING — liệt kê việc cần làm tiếp}

## 📎 Artifacts & ADR
{Nếu ARTIFACTS DUMPED trong brief có file → liệt kê với relative path}
{Nếu brief đề cập ADR → ghi link đến file ADR}
{Nếu không có → ghi "Không có file đính kèm trong phiên này."}

═══ QUY TẮC BẮT BUỘC ═══
- TUYỆT ĐỐI KHÔNG mở đầu bằng "Dạ", "Đây là", "Dưới đây", hay bất kỳ câu chào nào
- TUYỆT ĐỐI KHÔNG bọc output trong ```markdown``` code block
- KHÔNG ĐƯỢC bịa thêm file, commit, hoặc code không có trong input
- KHÔNG ĐƯỢC bỏ sót thông tin từ SESSION_BRIEF
- Status: 🟢 = xong tốt, 🟡 = có vấn đề, 🔴 = fail/blocked, ⚪ = chưa làm
- Viết tiếng Việt, thuật ngữ kỹ thuật giữ tiếng Anh

===INDEX===

─── PHẦN 2: Một dòng Markdown Table ───
| {DD/MM} | {project} | {workspace} | {TL;DR tối đa 15 từ} | [→](sessions/{YYYY-MM}/{DD_MM_YY}.md) | {link artifacts/ADR nếu có, — nếu không} | #{tag1} #{tag2} |

KHÔNG ĐƯỢC thêm bất kỳ text nào trước hoặc sau dòng này."""

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def read_file(path: Path, label: str, required: bool = True) -> str:
    if not path.exists():
        if required:
            print(f"❌ LỖI: File bắt buộc không tồn tại: {path}")
            sys.exit(1)
        else:
            print(f"⚠️  Không tìm thấy {label}: {path.name} (Bỏ qua)")
            return "(Không có dữ liệu)"
    content = path.read_text(encoding="utf-8")
    print(f"✅ Đọc {label}: {path.name} ({len(content)} chars)")
    return content


def parse_output(raw: str) -> tuple[str, str]:
    """Tách output Gemini thành (session_log, index_row)."""
    separator = "===INDEX==="
    if separator not in raw:
        print("❌ Gemini không trả về đúng format — thiếu ===INDEX===")
        print("─── RAW OUTPUT ───")
        print(raw)
        sys.exit(1)

    parts = raw.split(separator, 1)
    session_log = parts[0].strip()
    index_row = parts[1].strip()

    # Kiểm tra Phần 2 chỉ có đúng 1 dòng table
    index_lines = [l for l in index_row.splitlines() if l.strip()]
    if len(index_lines) != 1:
        print(f"⚠️  Phần 2 có {len(index_lines)} dòng thay vì 1. Lấy dòng đầu tiên bắt đầu bằng |")
        index_row = next((l for l in index_lines if l.startswith("|")), index_lines[0])

    return session_log, index_row


def call_gemini(brief: str, diff: str, plan: str = "") -> str:
    """Gọi Gemini HTTP API trực tiếp (bỏ qua SDK) để tránh lỗi Python namespace."""
    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY chưa set. Export biến môi trường trước:")
        print("   export GEMINI_API_KEY=your_key_here")
        sys.exit(1)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    user_message = f"<SESSION_BRIEF>\n{brief}\n</SESSION_BRIEF>\n\n<GIT_DIFF>\n{diff}\n</GIT_DIFF>"
    
    if plan:
        print("🔍 Đã kích hoạt [Hard Audit] - Đang nạp Implementation Plan vào bộ nhớ thẩm định.")
        user_message += f"\n\n<PLAN>\n{plan}\n</PLAN>"
        user_message += "\n\n⚠️ BẮT BUỘC ĐỐI CHIẾU HARD AUDIT: Hãy so sánh <SESSION_BRIEF> và <GIT_DIFF> với <PLAN> ban đầu. Nếu Agent làm khác Plan (thêm bớt files, sửa sai logic, đổi tech stack v.v...) mà KHÔNG CÓ giải thích hợp lý trong mục PIVOTS & DEAD ENDS, hãy đánh dấu 🔴 RISK CAO: LỆCH HƯỚNG LOGIC (Goal Drift) và giải thích sự mâu thuẫn vào mục Risks của log báo cáo."
    else:
        print("🔍 Kích hoạt [Soft Audit] - Không tìm thấy chỉ định Plan.")
        
    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "contents": [
            {
                "parts": [{"text": user_message}]
            }
        ],
        "generationConfig": {
            "temperature": 0.2
        }
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    print(f"🤖 Gọi Gemini qua HTTP ({GEMINI_MODEL})...")
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as e:
        error_info = e.read().decode("utf-8")
        print(f"❌ Lỗi API HTTP: {e.code} {e.reason}")
        print(error_info)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Lỗi kết nối: {str(e)}")
        sys.exit(1)


# ─── COMMAND: --scribe ────────────────────────────────────────────────────────

def cmd_scribe(mock: bool):
    print("\n" + "═" * 60)
    print("🛡️  SHADOW SCRIBE — Session Compiler")
    print("═" * 60)
    if mock:
        print("🧪 MODE: DRY-RUN (mock data, không ghi file)\n")
        brief_path = RAW_LOGS_DIR / "session_brief_mock.md"
        diff_path  = RAW_LOGS_DIR / "git_diff_mock.txt"
    else:
        brief_path = RAW_LOGS_DIR / "session_brief.md"
        diff_path  = RAW_LOGS_DIR / "git_diff.txt"

    # 1. Đọc input
    brief = read_file(brief_path, "Session Brief", required=True)
    diff  = read_file(diff_path,  "Git Diff", required=False)
    
    # 1.5. Trích xuất Plan Path và Load Plan (Tầng 2 Audit)
    import re
    import os
    plan_content = ""
    plan_match = re.search(r'Plan Path:\s*(.+)', brief)
    if plan_match:
        plan_path_str = plan_match.group(1).strip()
        # Bỏ qua các placeholder hoặc chuỗi rỗng
        if plan_path_str and "absolute_path" not in plan_path_str and "_{" not in plan_path_str and plan_path_str != "(none)" and plan_path_str != "—":
            plan_path = Path(plan_path_str)
            if plan_path.exists() and plan_path.is_file():
                plan_content = read_file(plan_path, "Implementation Plan", required=False)
            else:
                print(f"⚠️  Plan Path được khai báo là '{plan_path_str}' nhưng file không tồn tại trên ổ cứng. Bỏ qua Plan.")
                
    print()

    # 2. Gọi Gemini
    raw_output = call_gemini(brief, diff, plan_content)
    print(f"✅ Gemini trả về {len(raw_output)} chars\n")

    # 3. Parse output
    session_log, index_row = parse_output(raw_output)

    # 4. In kết quả ra terminal
    print("─" * 60)
    print("📄 PHẦN 1: Full Session Log")
    print("─" * 60)
    print(session_log)
    print()
    print("─" * 60)
    print("📋 PHẦN 2: Index Row (1 dòng để chèn vào INDEX_MATRIX)")
    print("─" * 60)
    print(index_row)
    print()

    if mock:
        print("═" * 60)
        print("🧪 DRY-RUN hoàn tất — không có file nào được ghi.")
        print("Nếu output trên đẹp → chạy lại KHÔNG có --mock để lưu thật.")
        print("═" * 60)
    else:
        import re
        # Lấy ngày từ brief
        date_match = re.search(r'Date:\s*(\d{4})-(\d{2})-(\d{2})', brief)
        if date_match:
            yyyy, mm, dd = date_match.groups()
        else:
            now = datetime.now()
            yyyy, mm, dd = now.strftime("%Y"), now.strftime("%m"), now.strftime("%d")
            
        session_folder = SESSIONS_DIR / f"{yyyy}-{mm}"
        session_folder.mkdir(parents=True, exist_ok=True)
        session_file = session_folder / f"{dd}_{mm}_{yyyy[2:]}.md"
        
        # Nếu đã có file trong ngày, thêm suffix
        counter = 1
        while session_file.exists():
            session_file = session_folder / f"{dd}_{mm}_{yyyy[2:]}_{counter}.md"
            counter += 1
            
        # Ghi session log
        session_file.write_text(session_log, encoding="utf-8")
        
        # Cập nhật Index
        if INDEX_FILE.exists():
            lines = INDEX_FILE.read_text(encoding="utf-8").splitlines()
            insert_idx = -1
            
            # Tìm vị trí ngay dưới dòng phân cách của Master Index
            for i, line in enumerate(lines):
                if line.startswith("|------|---------"):
                    insert_idx = i + 1
                    break
                    
            if insert_idx != -1:
                lines.insert(insert_idx, index_row)
                INDEX_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
            else:
                # Fallback nếu không tìm thấy bảng
                with INDEX_FILE.open("a", encoding="utf-8") as f:
                    f.write(f"\n{index_row}\n")
        
        # Dọn dẹp
        if brief_path.exists(): brief_path.unlink()
        if diff_path.exists(): diff_path.unlink()

        # —— Silent Assassin: chỉ in tóm tắt + Risk ——
        print("\n" + "═" * 60)
        print(f"✅ Session Log: {session_file}")
        print(f"✅ Index đã cập nhật | 🧹 raw_logs đã dọn")
        
        # Trích xuất và in phần Risks
        risks_match = re.search(r'## ⚠️ Risks.*?(?=\n## |\Z)', session_log, re.DOTALL)
        if risks_match:
            risks_text = risks_match.group(0).strip()
            has_real_risk = any(c in risks_text for c in ['🔴', '🟡'])
            if has_real_risk:
                print("\n🚨 RISK PHÁT HIỆN:")
                print("-" * 40)
                print(risks_text)
            else:
                print("🔍 Audit Pass: Không phát hiện Risk 🔴/🟡")
        print("═" * 60)

    print()


# ─── COMMAND: audit (READ-ONLY) ───────────────────────────────────────────────

AUDIT_PROMPT = """Bạn là Shadow Scribe Auditor. Nhiệm vụ duy nhất: So sánh <GIT_DIFF> với <PLAN> và phát hiện Goal Drift.
TUYỆT ĐỐI KHÔNG viết lời chào, giải thích hay tóm tắt dài.
Trả về ĐÚNG 3-5 gạch đầu dòng, không hơn:
- Đầu tiên: Kết luận tổng quát (✅ On-track / ⚠️ Minor drift / 🔴 GOAL DRIFT)
- Tiếp theo: Từng điểm lệch hướng cụ thể (nếu có)
- Cuối cùng: 1 câu hành động gợi ý
Không giải thích thêm bất kỳ điều gì."""


def cmd_audit(plan_path_arg: str = ""):
    cwd = Path.cwd()
    print("\n" + "═" * 60)
    print("🔍 SHADOW SCRIBE — Quick Audit")
    print(f"   CWD: {cwd}")
    print("═" * 60)

    # 1. Lấy git diff từ CWD (nơi user đang đứng = project folder)
    result = subprocess.run(
        ["git", "diff"],
        capture_output=True, text=True, cwd=str(cwd)
    )
    if result.returncode != 0:
        print(f"❌ Không thể chạy git diff tại {cwd}")
        print(f"   {result.stderr.strip()}")
        sys.exit(1)

    diff = result.stdout.strip()
    if not diff:
        # Thử diff với commit gần nhất
        result2 = subprocess.run(
            ["git", "diff", "HEAD~1"],
            capture_output=True, text=True, cwd=str(cwd)
        )
        if result2.returncode == 0 and result2.stdout.strip():
            diff = result2.stdout.strip()
            print("⚠️  Không có staged/unstaged changes. Dùng diff với HEAD~1.")
        else:
            diff = "(Không có thay đổi nào)"

    print(f"✅ Git diff: {len(diff)} chars từ [{cwd.name}]")

    # 2. Tìm implementation_plan.md
    plan = ""
    plan_path = None

    if plan_path_arg:
        p = Path(plan_path_arg)
        if p.exists():
            plan_path = p
        else:
            print(f"⚠️  --plan '{plan_path_arg}' không tồn tại. Tự tìm kiếm...")

    if not plan_path:
        # Auto-scan: CWD trước, sau đó brain dir mới nhất
        brain_dir = Path.home() / ".gemini" / "antigravity" / "brain"
        candidates = [cwd / "implementation_plan.md"]
        if brain_dir.exists():
            for conv_dir in sorted(brain_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                candidate = conv_dir / "implementation_plan.md"
                if candidate.exists():
                    candidates.insert(0, candidate)
                    break
        for c in candidates:
            if c.exists():
                plan_path = c
                break

    if plan_path:
        plan = plan_path.read_text(encoding="utf-8")
        print(f"✅ Implementation Plan: ...{str(plan_path)[-50:]} ({len(plan)} chars)")
        print("🔍 Kích hoạt [Hard Audit]")
    else:
        print("⚠️  Không tìm thấy Plan. Chỉ audit git diff (Soft Audit).")

    # 3. Gọi Gemini với prompt gọn
    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY chưa set.")
        sys.exit(1)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

    user_msg = f"<GIT_DIFF>\n{diff}\n</GIT_DIFF>"
    if plan:
        user_msg += f"\n\n<PLAN>\n{plan}\n</PLAN>"

    payload = {
        "system_instruction": {"parts": [{"text": AUDIT_PROMPT}]},
        "contents": [{"parts": [{"text": user_msg}]}],
        "generationConfig": {"temperature": 0.1}
    }

    print("🤖 Đang chạy audit...")
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req) as response:
            result_json = json.loads(response.read().decode("utf-8"))
            answer = result_json["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as e:
        print(f"❌ API Error: {e.code} {e.read().decode()}")
        sys.exit(1)

    # 4. In kết quả — READ-ONLY, không ghi file, không chạm Index
    print("\n" + "═" * 60)
    print("📊 Kết quả Audit:")
    print("-" * 40)
    print(answer.strip())
    print("═" * 60)
    print("🚨 READ-ONLY — Không ghi file, không chạm Index.\n")


# ─── COMMAND: digest (PROJECT-FILTERED SUMMARY) ──────────────────────────────

DIGEST_PROMPT = """Bạn là Shadow Scribe Digest Engine. Nhiệm vụ: tổng hợp N session logs thành 1 bản digest ngắn gọn.
TUYỆT ĐỐI KHÔNG viết lời chào, giải thích, hay bọc output trong ```markdown```.
Trả về NỘI DUNG THUẦN trực tiếp, bắt đầu ngay bằng dấu #.

INPUT: <SESSION_LOGS> chứa nhiều session logs ghép lại, mỗi session phân tách bằng ---SESSION---

OUTPUT bắt buộc đúng format:

# 📊 Digest: {project} — {date_range}
> Generated: {timestamp} | Sessions: {N} sessions

## 🎯 Tổng quan giai đoạn
{2-3 câu mô tả tổng thể tiến độ, velocity, hướng đi của project}

## ✅ Thành tựu chính
{Gom và deduplicate từ DONE sections. Chỉ liệt kê milestones quan trọng, không liệt kê trivial tasks}
- ...

## 💡 Quyết định kiến trúc
{Gom và deduplicate từ DECISIONS sections. Đánh số nếu nhiều. Bao gồm lý do ngắn gọn.}
- ...

## ⚠️ Rủi ro tích lũy
{Chỉ liệt kê risks CHƯA resolve. Đánh dấu severity 🔴/🟡}
- ...

## 📌 Việc còn lại
{PENDING items từ session mới nhất — đây là trạng thái hiện tại của project}
- ...

## 📈 Trajectory
{1 đoạn ngắn 2-3 câu: tốc độ tiến triển, bottleneck hiện tại, dự đoán next milestone}

═══ QUY TẮC ═══
- Viết tiếng Việt, thuật ngữ kỹ thuật giữ tiếng Anh
- Không bịa thêm thông tin không có trong input
- Không lặp lại thông tin giống nhau từ nhiều sessions"""


DIGEST_SESSIONS_DIR = SESSIONS_DIR  # alias cho rõ
DIGESTS_OUTPUT_DIR = VAULT_DIR / "digests"


def _parse_session_date(filename: str) -> Optional[datetime]:
    """Parse date từ filename dạng DD_MM_YY.md hoặc DD_MM_YY_N.md."""
    import re
    m = re.match(r"(\d{2})_(\d{2})_(\d{2})", filename)
    if not m:
        return None
    dd, mm, yy = m.groups()
    try:
        return datetime.strptime(f"{dd}/{mm}/20{yy}", "%d/%m/%Y")
    except ValueError:
        return None


def _parse_project_from_log(content: str) -> str:
    """Trích xuất Project từ header session log."""
    import re
    # Tìm **Project:** `shadow-scribe` | hoặc **Project:** shadow-scribe
    m = re.search(r'\*\*Project:\*\*\s*`?([\w\-]+)`?', content)
    if m:
        return m.group(1).strip().lower()
    return ""


def cmd_digest(project_filter: str = "", last_days: int = 0):
    print("\n" + "═" * 60)
    print("📊 SHADOW SCRIBE — Digest Engine")
    if project_filter:
        print(f"   Filter: project={project_filter}")
    if last_days:
        print(f"   Filter: last {last_days} ngày")
    print("═" * 60)

    # 1. Thu thập tất cả session files
    all_session_files: list[tuple[datetime, Path]] = []
    if not DIGEST_SESSIONS_DIR.exists():
        print(f"❌ Không tìm thấy sessions dir: {DIGEST_SESSIONS_DIR}")
        sys.exit(1)

    for month_dir in sorted(DIGEST_SESSIONS_DIR.iterdir()):
        if not month_dir.is_dir():
            continue
        for f in sorted(month_dir.iterdir()):
            if f.suffix != ".md":
                continue
            dt = _parse_session_date(f.name)
            if dt is None:
                continue
            all_session_files.append((dt, f))

    # Sắp xếp theo thời gian
    all_session_files.sort(key=lambda x: x[0])

    if not all_session_files:
        print("⚠️  Không tìm thấy session nào trong vault.")
        sys.exit(0)

    # 2. Filter theo --last
    if last_days > 0:
        cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff -= timedelta(days=last_days)
        all_session_files = [(dt, f) for (dt, f) in all_session_files if dt >= cutoff]

    if not all_session_files:
        print(f"⚠️  Không có session nào trong {last_days} ngày gần nhất.")
        sys.exit(0)

    # 3. Đọc content + filter theo --project
    matched: list[tuple[datetime, Path, str]] = []
    skipped = 0
    for dt, f in all_session_files:
        try:
            content = f.read_text(encoding="utf-8")
        except Exception:
            skipped += 1
            continue

        if project_filter:
            proj = _parse_project_from_log(content)
            if proj != project_filter.lower():
                skipped += 1
                continue

        matched.append((dt, f, content))

    if not matched:
        filter_info = f"project='{project_filter}'" if project_filter else "tất cả"
        print(f"⚠️  Không tìm thấy session nào khớp với filter [{filter_info}].")
        if skipped:
            print(f"   (Đã bỏ qua {skipped} sessions không khớp)")
        sys.exit(0)

    print(f"✅ Tìm thấy {len(matched)} sessions phù hợp (bỏ qua {skipped})")

    # 4. Ghép sessions lại, truncate nếu quá lớn
    MAX_CHARS = 900_000  # ~900K chars để fit 1M context Gemini
    parts = []
    total_chars = 0
    truncated_at = None

    for i, (dt, f, content) in enumerate(matched):
        entry = f"---SESSION--- [{dt.strftime('%d/%m/%Y')}] {f.name}\n{content}"
        if total_chars + len(entry) > MAX_CHARS:
            truncated_at = i
            print(f"⚠️  Đã truncate tại session {i+1}/{len(matched)} để fit context 1M Gemini.")
            break
        parts.append(entry)
        total_chars += len(entry)

    combined = "\n\n".join(parts)

    date_range = (
        f"{matched[0][0].strftime('%d/%m/%Y')} → "
        f"{matched[min(len(matched)-1, len(parts)-1)][0].strftime('%d/%m/%Y')}"
    )
    proj_label = project_filter if project_filter else "all-projects"
    print(f"   Date range: {date_range}")
    print(f"   Total chars: {total_chars:,}\n")

    # 5. Gọi Gemini
    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY chưa set.")
        sys.exit(1)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

    user_msg = (
        f"Project filter: {proj_label}\n"
        f"Date range: {date_range}\n"
        f"Sessions count: {len(parts)}\n\n"
        f"<SESSION_LOGS>\n{combined}\n</SESSION_LOGS>"
    )

    payload = {
        "system_instruction": {"parts": [{"text": DIGEST_PROMPT}]},
        "contents": [{"parts": [{"text": user_msg}]}],
        "generationConfig": {"temperature": 0.2},
    }

    print("🤖 Đang tổng hợp digest...")
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req) as response:
            result_json = json.loads(response.read().decode("utf-8"))
            digest_text = result_json["candidates"][0]["content"]["parts"][0]["text"].strip()
    except urllib.error.HTTPError as e:
        print(f"❌ API Error: {e.code} {e.read().decode()}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Lỗi kết nối: {str(e)}")
        sys.exit(1)

    # 6. In ra terminal (luôn)
    print("\n" + "═" * 60)
    print("📊 DIGEST OUTPUT:")
    print("-" * 40)
    print(digest_text)
    print("═" * 60)

    # 7. Ghi file
    DIGESTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    out_file = DIGESTS_OUTPUT_DIR / f"{proj_label}_{today_str}.md"

    # Không ghi đè file cũ cùng ngày
    counter = 1
    while out_file.exists():
        out_file = DIGESTS_OUTPUT_DIR / f"{proj_label}_{today_str}_{counter}.md"
        counter += 1

    out_file.write_text(digest_text, encoding="utf-8")

    if truncated_at is not None:
        note = f"\n\n---\n> ⚠️ Digest bị truncate: chỉ bao gồm {len(parts)}/{len(matched)} sessions đầu do giới hạn context."
        with out_file.open("a", encoding="utf-8") as fh:
            fh.write(note)

    print(f"\n✅ Digest đã lưu: {out_file}")
    print()


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=f"Shadow Scribe v{VERSION} — Watchdog Agent for AI sessions"
    )
    subparsers = parser.add_subparsers(dest="command")

    # scribe (cuối ngày, destructive)
    scribe_parser = subparsers.add_parser("scribe", help="Cuối ngày: ghi Session Log + cập nhật Index")
    scribe_parser.add_argument("--mock", action="store_true", help="Dry-run với mock data")

    # audit (giữa giờ, read-only)
    audit_parser = subparsers.add_parser("audit", help="Giữa giờ: soi goal drift (read-only)")
    audit_parser.add_argument("--plan", default="", help="Đường dẫn tới file implementation_plan.md")

    # digest (tổng hợp nhiều sessions, project-filtered)
    digest_parser = subparsers.add_parser("digest", help="Tổng hợp digest theo project")
    digest_parser.add_argument(
        "--project", default="",
        help="Filter theo project (vd: shadow-scribe, z-zero). Bỏ trống = tất cả."
    )
    digest_parser.add_argument(
        "--last", type=int, default=0, metavar="N",
        help="Chỉ lấy sessions trong N ngày gần nhất (vd: --last 30). Bỏ trống = tất cả."
    )

    args = parser.parse_args()

    if args.command == "scribe":
        cmd_scribe(mock=args.mock)
    elif args.command == "audit":
        cmd_audit(plan_path_arg=args.plan)
    elif args.command == "digest":
        cmd_digest(project_filter=args.project, last_days=args.last)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

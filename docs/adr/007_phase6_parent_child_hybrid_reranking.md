# ADR-007: Phase 6 Implementation — Parent-Child Retrieval + Sparse-LLM Hybrid Reranking

| Field | Value |
|-------|-------|
| **Ngày tạo** | 25/04/2026 |
| **Project** | shadow-scribe |
| **Status** | ✅ IMPLEMENTED |
| **Plan liên quan** | (sẽ tạo `plans/v1.3.0_phase6.md` sau khi sign-off) |
| **Architecture ADR** | ADR-006 (WHY Lightweight Agentic RAG) |
| **Author** | Claude Opus 4.7 (independent reviewer agent) |

> **Next status flip:** ACCEPTED khi user sign-off → IMPLEMENTED khi `watchdog query` ship.

---

## Context

ADR-006 đã chốt: **Lightweight Agentic RAG**, dựa trên 3-layer vault structure (kế thừa từ ADR-001/002/003).

ADR-007 trả lời câu hỏi: **Thực hiện cụ thể như thế nào?**
- Retrieval pattern (Parent-Child)
- Search strategy (Sparse + LLM rerank)
- API design (`watchdog query`)
- Output format (progressive disclosure)
- Module placement

---

## 📍 Quyết định (The Chosen Path)

### 1. Parent-Child Retrieval (3-layer descent)

Map theo terminology academic literature 2025-2026:

```
Child layer:        INDEX_MATRIX.md row              (precise, ~100 chars)
Parent layer:       sessions/YYYY-MM/*.md            (full context, ~5KB)
Grandparent layer:  projects/{p}/adr/*.md            (decision root, ~3KB)
```

**Workflow:**
1. Stage 1: grep keyword trên INDEX_MATRIX → trả về N **child rows** (precise hits)
2. Agent đọc child rows → quyết định có cần parent không
3. Nếu cần context đầy đủ → follow link → đọc **parent** (session log)
4. Nếu cần root quyết định → follow link tiếp → đọc **grandparent** (ADR)

**Key insight:** Không kéo cả 3 layers cùng lúc. Agent **descend on demand** — đây là "agentic" element của ADR-006.

**Citation:** Pattern này khớp với "Parent-Child Retrieval" trong RAG literature (cite [45, 47]) — đạt cân bằng giữa precision (child level) và bức tranh toàn cảnh (parent/grandparent level).

### 2. Sparse-LLM Hybrid Reranking (2-stage retrieval)

**Stage 1 (cheap-fast, default):**
```python
results = grep_index_matrix(keyword)
if 2 <= len(results) <= TOP_N:
    return format_results(results)  # Đủ tốt, return luôn
```

**Stage 2 (smart-fallback, on-demand):**
```python
# Trigger khi:
# - Stage 1 < 2 hits (keyword mơ hồ, có thể miss)
# - Stage 1 > TOP_N hits (quá nhiều, cần rank)
# - User explicit: --smart flag
prompt = f"Query: {keyword}\n\nINDEX_MATRIX:\n{full_index_matrix}"
ranked = gemini_rerank(prompt)  # Reuse shadow_scribe.gemini.call_gemini
return ranked[:TOP_N]
```

**Vì sao gọi "Hybrid":** Khác BM25+Vector hybrid truyền thống. Đây là **"cheap-fast (grep) + smart-expensive (LLM)"** — cùng triết lý cost-aware retrieval, citation [36, 42, 48, 49] về RRF + Cross-Encoder reranking.

### 3. API Design

```bash
# Basic
watchdog query "atomic write decision"

# Filter by project
watchdog query "payment" --project z-zero

# Limit results
watchdog query "refactor" --top 3

# Force Stage 2 (skip grep, đi thẳng LLM rerank)
watchdog query "tại sao chọn gemini-flash" --smart
```

**Default values:**
- `TOP_N = 5`
- `--project = None` (search all projects)
- `--smart = False` (auto-decide stage)

### 4. Output Format

```
🔍 Query: "atomic write decision"
   Found: 3 results (Stage 1 grep, 23ms)

┌─────────┬───────────────┬──────────────────────────────────────┬──────────────┐
│ Date    │ Project       │ TL;DR                                │ Link         │
├─────────┼───────────────┼──────────────────────────────────────┼──────────────┤
│ 24/04   │ shadow-scribe │ Hardening v1.2.1, atomic write fcntl │ ADR-004      │
│ 24/04   │ shadow-scribe │ 6 security fixes, atomic file ops    │ session→     │
│ 14/04   │ shadow-scribe │ Watchdog architecture, broker design │ ADR-001      │
└─────────┴───────────────┴──────────────────────────────────────┴──────────────┘

💡 Để xem chi tiết: agent tự follow link bằng read tool.
```

**Nguyên tắc cốt lõi:** **KHÔNG dump nội dung file vào output.** In bảng ngắn → agent tự follow link nếu cần. Đây là **progressive disclosure** đúng nghĩa — tránh tràn context.

### 5. Module Placement

```
shadow_scribe/
├── cmd_query.py          ← MỚI (~120-150 dòng)
├── (existing modules)

watchdog_scribe.py        ← thêm subcommand "query" vào argparse
```

**Reuse existing modules:**
- `gemini.py` cho Stage 2 LLM rerank (call_gemini với prompt mới)
- `io_utils.py` cho file reading + path parsing
- `config.py` cho `VAULT_DIR`

---

## 🚫 Rejected Implementation Choices

### ❌ Tự parse markdown table phức tạp (markdown-it library)
- **Lý do:** INDEX_MATRIX format đã chuẩn → regex `^\| (\d{2}/\d{2}) \| (\S+) \| ... \|$` đơn giản là đủ. Không cần markdown parser library.

### ❌ Cache results vào SQLite
- **Lý do:** Vi phạm zero-dep. Mỗi grep < 100ms → không cần cache.

### ❌ Stream output
- **Lý do:** Output ngắn (5 rows max). Stream chỉ phức tạp hóa code.

### ❌ Auto-trigger Stage 2 luôn
- **Lý do:** Theo dự đoán 70%+ queries Stage 1 đủ. Auto Stage 2 = waste cost.

### ❌ Query rewriting (gọi Gemini parse query trước)
- **Lý do:** Add latency + cost mà chưa rõ benefit. Có thể add sau ở v1.3.x nếu KPI cho thấy keyword search miss nhiều.

### ❌ Snippet preview trong output
- **Lý do:** Vi phạm progressive disclosure. Bảng nên gọn — agent follow link xem chi tiết.

### ❌ Boolean query (`AND`/`OR`/`NOT`)
- **Lý do:** YAGNI. Stage 2 LLM rerank đã handle queries phức tạp.

---

## ⚠️ Trade-offs chấp nhận

| Trade-off | Mức độ | Lý do chấp nhận |
|-----------|--------|-----------------|
| Output không có snippet preview | 🟢 LOW | Progressive disclosure đúng nghĩa — agent follow link xem snippet |
| Stage 2 cost khi keyword mơ hồ | 🟡 MED | Acceptable nếu fallback rate < 30% (KPI ADR-006) |
| Không support boolean query | 🟢 LOW | YAGNI — thêm sau nếu cần |
| Fixed regex parser cho INDEX format | 🟡 MED | Nếu INDEX format thay đổi → break parser. Mitigated bằng test + format đã stable từ ADR-003 |
| Output dạng table CLI có thể vỡ trên terminal hẹp | 🟢 LOW | Test với width 80 chars; truncate TL;DR nếu cần |

---

## 📊 Success Metrics

| Metric | Target |
|--------|--------|
| `cmd_query.py` ≤ 150 dòng | ✅ (giữ minimal) |
| Stage 1 latency p95 | < 100ms |
| Stage 2 latency p95 | < 1500ms |
| Test coverage `cmd_query.py` | ≥ 80% |
| Unit tests cover: grep hit, grep miss, Stage 2 trigger, project filter, --smart flag | All cases |
| Integration test: query thực trên vault hiện tại trả kết quả relevant | ≥ 4/5 queries |

---

## 🛠️ Implementation Plan (high-level)

> Detailed step-by-step plan sẽ ở `plans/v1.3.0_phase6.md` sau khi ADR-006 + 007 ACCEPTED.

```
Step 1: Tạo cmd_query.py skeleton + tests/test_query.py
Step 2: Implement Stage 1 grep parser cho INDEX_MATRIX
Step 3: Implement Stage 2 Gemini rerank
Step 4: Wire entry point watchdog_scribe.py thêm subcommand
Step 5: Verify với 5 real queries trên vault hiện tại (~15 sessions)
Step 6: Bump v1.3.0, update README/ROADMAP, tag release
```

---

## 🔄 Rollback Plan

Same as ADR-006: gỡ subcommand `watchdog query`, không destructive (read-only operation).

---

## 🔮 Consequences

### Tích cực
- **Pattern Parent-Child Retrieval lần đầu hiện thực hoá** trong project, đúng terminology academic
- **Stage 2 fallback** giải quyết điểm yếu cố hữu của sparse search
- **Zero new dependencies** — chỉ thêm 1 file Python ~150 dòng
- **Module reuse cao:** tận dụng `gemini.py`, `io_utils.py`, `config.py` đã có

### Tiêu cực / Rủi ro
- **Regex parser dễ vỡ** nếu format INDEX_MATRIX thay đổi → cần test kỹ + format đã stable từ ADR-003
- **TOP_N hardcoded 5** — có thể chưa optimal, cần tune dựa trên user feedback sau v1.3.0
- **Stage 2 fallback rate** là KPI quan trọng nhất để monitor — nếu cao bất thường → review tagging discipline

---

## 📎 Citations & References

### RAG techniques literature (2025-2026)
- **Parent-Child Retrieval** — cite [45, 47] từ "Sự Nâng Cấp Từ RAG Cơ Bản Đến RAG Thích Ứng"
- **Hybrid Search & Reranking** — cite [36, 42, 48, 49] (BM25/RRF + Cross-Encoder reranking)

### Architectural foundation (existing)
- ADR-006: Lightweight Agentic RAG (WHY this architecture)
- ADR-001/002/003: Vault 3-layer structure (foundation cho Parent-Child)

### Module dependencies (existing in shadow_scribe/)
- `gemini.py`: call_gemini, parse_output (Stage 2 reuse)
- `io_utils.py`: file reading, path parsing
- `config.py`: VAULT_DIR

# ADR-006: Phase 6 — Lightweight Agentic RAG (Architecture)

| Field | Value |
|-------|-------|
| **Ngày tạo** | 25/04/2026 |
| **Project** | shadow-scribe |
| **Status** | ✅ IMPLEMENTED |
| **Plan liên quan** | (sẽ tạo `plans/v1.3.0_phase6.md` sau khi sign-off) |
| **Implementation ADR** | ADR-007 |
| **Author** | Claude Opus 4.7 (independent reviewer agent) |

> **Next status flip:** ACCEPTED khi user sign-off → IMPLEMENTED khi `watchdog query` ship trong v1.3.0.

---

## Context (Bài toán)

Vault hiện có ~15 sessions (sau 2 tuần dùng), pace ~270/tháng theo usage thực tế (3-4 project active, ~3 session/ngày/project). **Cold-start problem** ngày càng đau:

- Quay lại project sau 2-3 tuần → quên decisions cụ thể (vd: "tại sao chọn `fcntl.flock` không phải `threading.Lock`?")
- `watchdog digest` cho summary nhưng KHÔNG retrieve được câu hỏi cụ thể — phải đọc cả digest
- Phải mở từng file ADR/session bằng tay → tốn thời gian + token

**Trigger thực tế:** User muốn `watchdog query "atomic write decision"` → trả về context relevant trong < 1 giây.

**Constraint cốt lõi (kế thừa từ ADR-001):** Zero-dependency. Không SQLite, không ChromaDB, không embedding model.

**Ghi chú quan trọng về scope:** Cấu trúc lưu trữ 3-layer (INDEX_MATRIX → sessions → ADR) đã được thiết kế từ ADR-001/002/003. Phase 6 **KHÔNG thay đổi cấu trúc**, chỉ thêm query layer khai thác cấu trúc đã có.

---

## 📍 Quyết định (The Chosen Path)

> **Chọn: Lightweight Agentic RAG** — đạt agentic behavior ở cost của Naive RAG.

### Phân loại theo industry taxonomy (2025-2026)

| RAG Type | Latency | Cost/Query | Phase 6 fit? |
|----------|---------|-----------|--------------|
| Naive RAG | 300ms | $0.005 | ❌ Single-shot, không có agent decision |
| Advanced RAG | 1250ms | $0.0175 | ⚠️ Có rerank nhưng không có query rewriting/HyDE |
| GraphRAG | 3000ms | $0.085 | ❌ Không build knowledge graph riêng |
| Full Agentic RAG | 6000ms | $0.055 | ✅ Đúng category về behavior |
| **Phase 6 (Lightweight Agentic)** | **~500ms** | **~$0.001** | ✅ **Đạt agentic ở Naive cost** |

### Vì sao gọi là "Lightweight Agentic"

- **Agentic element:** Agent quyết định query Layer 1 → đủ thì dừng, chưa đủ thì descend Layer 2 → cần root thì descend Layer 3. Không phải single-shot.
- **Lightweight element:** Không có multi-step reasoning loop kéo dài (như full Agentic 6000ms). Mỗi query = 1-2 round trips, shallow nhưng có agentic decision.

### USP (Unique Selling Point)

> **Đạt agentic behavior ở cost của Naive RAG vì tận dụng human-curated INDEX.**

Mỗi session brief đã có TL;DR + tags do người (hoặc agent) viết — INDEX_MATRIX trở thành "human-curated semantic index". Không cần auto-embedding vì semantics đã được encode bằng natural language tags.

---

## 🚫 Các con đường đã loại bỏ (Rejected Paths)

### ❌ Vector RAG (ChromaDB / SQLite + embeddings)
- **Lý do chính:** Vi phạm zero-dep principle (kế thừa từ ADR-001). Cần `pip install` + embedding model.
- **Cost ẩn:** Re-index mỗi khi sửa file, black-box debug, không hiển thị được "tại sao tìm ra kết quả này".
- **Khi nào nên dùng:** Vault > 10K documents không có human curation. Hiện tại chưa.

### ❌ Naive RAG (single-shot grep, dump full)
- **Lý do:** Không có agent decision → thường trả quá nhiều hoặc quá ít. Tràn context khi grep match nhiều files.
- **Cụ thể:** `grep "atomic" sessions/` trả về 20 hits không xếp hạng → agent phải đọc hết.

### ❌ GraphRAG (build knowledge graph riêng)
- **Lý do:** INDEX_MATRIX đã là pseudo-graph (mỗi row link tới session, ADR, artifacts). Build graph riêng = duplicate data + maintenance burden.
- **Cost:** Cần re-build graph mỗi khi có session mới.

### ❌ Full Agentic RAG (multi-step reasoning loops)
- **Lý do:** Latency 6000ms không acceptable cho cold-start use case. User muốn câu trả lời nhanh, không phải dialog dài.
- **Cost:** $0.055/query × 10 queries/ngày = $16/tháng — overkill cho personal use.

### ❌ Tự build embedding pipeline với Gemini
- **Lý do:** Gemini có embedding API nhưng vẫn cần lưu trữ vector → cần SQLite/file format → vi phạm zero-dep.

---

## ⚠️ Trade-offs chấp nhận

| Trade-off | Mức độ | Lý do chấp nhận |
|-----------|--------|-----------------|
| Sparse search cần keyword chính xác hơn vector | 🟡 MED | Bù bằng Stage 2 LLM rerank (chi tiết ADR-007) khi grep < N hits hoặc keyword mơ hồ |
| Phụ thuộc chất lượng tagging của INDEX_MATRIX | 🟡 MED | Watchdog scribe đã enforce TL;DR + tags trong brief format. Chất lượng tăng theo discipline. |
| Không fuzzy match ("payment" → "billing") | 🟢 LOW | Stage 2 LLM rerank giải quyết. Test thực tế khi vault > 50 sessions. |
| Phụ thuộc Gemini API (Stage 2) | 🟢 LOW | Đã có sẵn từ Phase 1. Không thêm dep mới. |
| Stage 1 grep linear-scan → chậm khi vault > 5K sessions | 🟢 LOW | Hiện 15 sessions, ~270/tháng → 5K rows = ~18 tháng. Khi đó add markdown index file (vẫn không Vector DB). |

---

## 📊 Success Metrics

> Đo sau khi v1.3.0 ship 2 tuần dùng thực tế.

| Metric | Baseline (v1.2.2) | Target (v1.3.0) |
|--------|-------------------|-----------------|
| Cold-start time (mở session mới, agent có context) | ~5 phút (manual mớm) | < 30 giây (`watchdog query`) |
| Avg query latency (Stage 1 only) | N/A | < 100ms |
| Avg query latency (Stage 2 fallback) | N/A | < 1500ms |
| Cost per query (avg) | N/A | < $0.002 |
| Stage 2 fallback rate | N/A | < 30% (nếu cao hơn → tagging discipline kém, cần improve) |
| User-reported "found what I need" | N/A | ≥ 80% sessions |

---

## 🔄 Rollback Plan

- **Non-destructive:** Phase 6 chỉ ADD subcommand `watchdog query`, không thay đổi `scribe`/`audit`/`digest`
- **Rollback đơn giản:** Gỡ subcommand → vault structure không bị ảnh hưởng (read-only operation)
- **Tag anchor:** `v1.2.2` (đã tag) làm rollback target nếu v1.3.0 fail

---

## 🔮 Consequences

### Tích cực
- **Cold-start solved:** Agent tự query thay vì user mớm context
- **INDEX_MATRIX upgrade:** Trở thành "human-curated semantic index" có giá trị tăng dần theo session
- **Cross-project query:** Query span được z-zero, kya-network, shadow-scribe trong cùng vault — value tăng khi multi-project
- **Validates hypothesis:** "Structured markdown + LLM rerank = đủ thay vector DB ở scale này" — pattern có thể export sau

### Tiêu cực / Rủi ro
- **Tagging discipline:** Phải maintain — nếu lười tag → query precision giảm. Mitigated bằng scribe prompt enforce.
- **Stage 2 fallback rate là KPI cần monitor** — nếu > 50% nghĩa là Stage 1 không hoạt động hiệu quả → cần review tagging hoặc thêm query rewriting

### Long-term implication
- Khi vault > 5K sessions, Stage 1 grep có thể chậm → lúc đó add markdown index file pre-built (vẫn không Vector DB)
- Pattern này có thể export thành standalone tool cho người dùng Obsidian/Logseq sau này

---

## 📊 Ma trận so sánh

| Tiêu chí | Vector RAG ❌ | Naive RAG ❌ | Full Agentic ❌ | **Lightweight Agentic ✅** |
|----------|---------------|---------------|------------------|-----------------------------|
| Zero-dep | ❌ | ✅ | ⚠️ | **✅** |
| Cost/query | $0.0175 | $0.005 | $0.055 | **$0.001** |
| Latency | 1250ms | 300ms | 6000ms | **~500ms** |
| Agent decision | ❌ | ❌ | ✅ | **✅** |
| Debug transparency | ❌ (black box) | ✅ | ⚠️ | **✅** |
| Vault scale phù hợp | 10K+ docs | < 100 docs | bất kỳ | **100-5K docs** ← chúng ta đang ở đây |

---

## 📎 Citations & References

### Industry RAG taxonomy (2025-2026)
- Naive / Advanced / Graph / Agentic RAG framework — Starmorph Blog, 2026
- Cost & Latency benchmark numbers — Starmorph Blog, 2026

### Architectural foundation (existing)
- ADR-001: Watchdog Architecture (vault folder structure 3-layer)
- ADR-002: Dual-Tier Audit (separation scribe/audit, Phase 6 sẽ thêm tier query)
- ADR-003: Digest Architecture (INDEX rows format — base cho query parser)

### Implementation details
- Xem ADR-007: cách thực thi cụ thể (Parent-Child Retrieval + Sparse-LLM Hybrid Reranking)

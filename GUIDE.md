# 🛡️ Shadow Scribe — Operations Manual (v1.3.0)

> This file is the **sole operations guide** for AI Agents.
> If you are an IDE Agent (Antigravity, Cursor, Windsurf, Claude Code), read this entire file before taking action.
> Detailed documentation: `~/Documents/shadow scribe/README.md`

---

## ⚙️ Architecture Principles

```
IDE Agent  = ORCHESTRATOR — gathers files, runs commands, writes 15-line brief.
Watchdog   = BRAIN         — reads, analyzes, synthesizes (powered by Gemini Flash).
```

⛔ Agent **NEVER** reads logs/conversations and summarizes on its own — that's Watchdog's job.
Watchdog script: `~/Documents/shadow scribe/watchdog_scribe.py`
API Key: auto-loaded from `~/Documents/agent_vault/.env`.
  *(⚠️ Must use official API. Never use leaked/proxy API keys to avoid exposing source code/secrets)*

---

## 📂 Vault Structure

```
~/Documents/agent_vault/
├── .env                        # GEMINI_API_KEY (auto-loaded, no export needed)
├── 00_INDEX_MATRIX.md          # Perpetual index of all sessions
├── raw_logs/                   # Transit station (temp — Watchdog reads then cleans)
│   └── {project-name}/         # Each project gets its own directory (kebab-case)
│       ├── session_brief.md    # Agent writes (~15 lines)
│       └── git_diff.txt        # git diff snapshot
├── sessions/                   # Full Session Logs (Gemini Flash synthesis)
│   └── YYYY-MM/DD_MM_YY.md
├── trash/                      # Soft-Delete — raw_logs backup (auto-purge after 30 days)
├── artifacts/                  # Draft files, plans, schemas from sessions
├── digests/                    # Summary reports from watchdog digest
└── projects/
    └── {project_name}/
        ├── PROJECT_INDEX.md    # Timeline + Key Decisions
        └── adr/                # Architecture Decision Records
```

---

## 🗺️ Workspace → Project Mapping

| Workspace (code folder name) | Project (vault name) |
|-------------------------------|----------------------|
| `shadow-prominence`, `shadow scribe` | `shadow-scribe` |
| `ai-card-mcp`, `z-zero-dashboard`, `z-zero-mcp` | `z-zero` |
| `kya-network`, `kya-mcp-server` | `kya-network` |

> If workspace is not in the table → create a new project name using kebab-case, no spaces.

---

## 🔄 Session Workflow

### Start of Session — Load Context

Read these 3 files in order before starting work:
1. `~/Documents/agent_vault/00_INDEX_MATRIX.md` — Find the latest session for the project
2. `~/Documents/agent_vault/sessions/{YYYY-MM}/{latest_session}.md` — Read full log from previous session
3. `~/Documents/agent_vault/projects/{project}/adr/ADR_INDEX.md` — Review locked architecture decisions

Provide a brief summary to the user: where we are, what's pending, then start coding.

### During Session — Code as normal

- Making an important architecture decision → Type `@adr [issue name]` (see @adr section below)
- Want a mid-session check → Type `run audit` or any equivalent vibe command

### End of Session — @dump (3-in-1, automated)

When user types `@dump`, `summarize`, or similar intent:

**Step 1:** Run terminal command:
```bash
mkdir -p ~/Documents/agent_vault/raw_logs/{project_name}
git diff > ~/Documents/agent_vault/raw_logs/{project_name}/git_diff.txt
```

**Step 2:** Write file `~/Documents/agent_vault/raw_logs/{project_name}/session_brief.md`:
```markdown
# Session Brief
Date: YYYY-MM-DD
Project: {project_name}
Workspace: {workspace_path}
Conversation ID: {conv_id}
Plan Path: {path_to_implementation_plan.md or (none)}
Time: {HH:MM} - {HH:MM}

## FOCUS (What was today's goal?)
{Main objective in 1-2 sentences}

## DONE (Completed)
- {Specific action}

## DECISIONS (Key decisions)
- {Decision}: {Reasoning}

## PIVOTS & DEAD ENDS (Abandoned approaches)
- {Approach AA}: {Why abandoned}

## BLOOD LESSONS (Bugs & Lessons Learned) ⬅️ REQUIRED
- {Bug}: {Description} → {Fix}
- (If smooth sailing, write: "Clean run — no issues encountered.")

## RISKS (Discovered risks)
- {Risk}: {Context}

## PENDING (Unfinished → next session)
- {Incomplete work}

## ARTIFACTS DUMPED
- {filename} → artifacts/YYYY-MM/{filename}
- (none if N/A)

## FILES CHANGED (most important)
- {path/file.ext} — {change description}
```

**Step 3:** Automatically invoke Watchdog (no user action needed):
```bash
python3 ~/Documents/shadow\ scribe/watchdog_scribe.py scribe
```

**Step 4:** Report results to user:
```
✅ Watchdog complete:
- Session Log → sessions/YYYY-MM/DD_MM_YY.md
- Index updated | 🗑️ raw_logs → trash/
- [Risk if any / "Audit Pass" if clean]
```

---

## 🔍 Watchdog Commands (run in Terminal)

| Command | Function | Type |
|---------|----------|------|
| `watchdog scribe` | Gemini writes Full Log, updates Index, cleans up | 🔴 WRITE |
| `watchdog scribe --mock` | Dry-run: print only, no file writes | 🟢 READ |
| `watchdog audit` | Instant Goal Drift check | 🟢 READ |
| `watchdog audit --plan /path` | Hard Audit with explicit plan | 🟢 READ |
| `watchdog digest` | Aggregate all sessions into report | 🟡 R+W |
| `watchdog digest --project NAME` | Filter by project | 🟡 R+W |
| `watchdog query <keyword>` | **(Phase 6)** Search vault — Stage 1 grep, Stage 2 Gemini fallback | 🟢 READ |
| `watchdog query <keyword> --project NAME` | Filter results by project | 🟢 READ |
| `watchdog query <keyword> --smart` | Force Stage 2 Gemini even if Stage 1 has results | 🟢 READ |

> Actual terminal command:
> `python3 ~/Documents/shadow\ scribe/watchdog_scribe.py {command} [flags]`

---

## 🗺️ @adr — Record ADR at Decision Time

When user types `@adr [issue name]`:

1. Read `~/Documents/agent_vault/projects/{project}/adr/ADR_INDEX.md` → get next ADR number
2. Create file `~/Documents/agent_vault/projects/{project}/adr/NNN_{snake_case_name}.md`
3. Use template: Context → Chosen Path → Rejected Paths → Potential Paths → Comparison Matrix
4. Update `ADR_INDEX.md`

---

## ♻️ Retroactive Dump (catching up on missed days)

If user forgot to dump for 1-2 days:
- Use `git log --since="{date}"` to gather code changes → write brief → run watchdog
- If user provides conversation log → copy into `raw_logs/{project}/` → invoke watchdog
- Remember: **Watchdog reads**, not Agent. Agent only copies files and runs commands.

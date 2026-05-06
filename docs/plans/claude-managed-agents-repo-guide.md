# Claude Managed Agents: layout and operating guide for `accessible-surfaceome`

> Status: design guide. Claude Managed Agents is a beta API; pin SDK versions and expect API details to move.

## 1. Scope

This guide covers how the **surface-proteome annotator** — a single Claude Managed Agent that produces `GeneAnnotation` records per gene by querying UniProt / HGNC / NCBI / EuropePMC / Google Patents through custom tools — is laid out and operated inside this repo. It is intentionally tight: we have one agent, one environment, and one CLI today. When a second agent appears, factor shared helpers up at that point.

The companion document is [docs/tools-design.md](../tools-design.md), which specifies the custom-tool surface (`gene_lookup`, `gene_literature`, `patent_lookup`) and Pydantic return shapes.

## 2. Mental model

Claude Managed Agents has four primary concepts:

| Concept | Repo representation | Runtime behavior |
|---|---|---|
| Agent | `src/accessible_surfaceome/agents/surface_annotator/agent.py` + `prompts/system.md` | Reusable, versioned remote resource. Create once, update intentionally. |
| Environment | `src/accessible_surfaceome/agents/surface_annotator/environment.py` | Reusable container template. Not Anthropic-versioned, so we track our own hash. |
| Session | `src/accessible_surfaceome/agents/surface_annotator/orchestrator.py`, `tasks/`, CLI args | One running agent instance inside an environment. One per gene, normally. |
| Events | `src/accessible_surfaceome/agents/_support/events.py` | User messages go in; agent/tool/session events stream back. |

We use Managed Agents (rather than the lower-level Messages API) because the work benefits from a managed container, long-running execution, and event streaming, and because custom-tool dispatch fits naturally into the session lifecycle.

## 3. Directory layout

Everything lives inside the existing `accessible_surfaceome` package — same uv project, same CLI, same dependency tree as `sources/`, `merge/`, and `audit/`.

```text
src/accessible_surfaceome/
├── agents/
│   ├── __init__.py
│   ├── surface_annotator/
│   │   ├── __init__.py
│   │   ├── agent.py              # build the agent definition
│   │   ├── environment.py        # build the environment definition
│   │   ├── orchestrator.py       # session lifecycle + event-stream loop +
│   │   │                         # custom-tool dispatcher
│   │   ├── tool_registry.py      # name → (handler, input_schema, description)
│   │   └── prompts/
│   │       ├── system.md
│   │       └── task_template.md
│   └── _support/
│       ├── __init__.py
│       ├── client.py             # Anthropic() factory
│       ├── events.py             # stream + tool-confirmation helper
│       └── registry.py           # .runs/agents-registry.json reader/writer
├── tools/                        # custom-tool handlers (surfaceome science)
│   ├── __init__.py
│   ├── gene_lookup.py
│   ├── gene_literature.py
│   ├── patent_lookup.py
│   └── _shared/
│       ├── cache.py              # SQLite-backed, per-source TTLs
│       ├── ratelimit.py
│       └── models.py             # Pydantic return shapes + Evidence / GeneAnnotation
├── installs/                     # per-machine install plumbing
│                                 # (renamed from tools/ to free up that name)
└── (existing: cli.py, controls.py, sources/, merge/, audit/, paths.py, ...)
```

Run logs (gitignored):

```text
.runs/
└── 2026-05-06-KAAG1-sesn_abc/
    ├── task.md
    ├── session.json
    ├── usage.json
    ├── events.jsonl
    ├── files/
    └── final.md
```

Registry (a small JSON file, not committed by default — decide per-environment):

```text
.runs/agents-registry.json
```

```json
{
  "agent_id": "agent_...",
  "agent_version": 3,
  "environment_id": "env_...",
  "system_prompt_sha256": "..."
}
```

## 4. CLI

We extend the existing `accessible-surfaceome` console_script — no second binary.

```bash
uv run accessible-surfaceome agents sync                # create-or-update agent + environment, write registry
uv run accessible-surfaceome agents annotate KAAG1      # one gene → data/annotations/KAAG1.json
uv run accessible-surfaceome agents annotate --batch controls.txt
uv run accessible-surfaceome agents send --session sesn_... --message "Run targeted tests."
```

`sync` and `annotate` are kept separate. Creating/updating remote agents should not happen on the hot path of an annotation run.

## 5. Agent definition

Build the agent in Python (no YAML — we have one agent and one set of fields, so a typed Python module is the simpler diff target). The system prompt lives in a separate `.md` file so it stays readable.

```python
# src/accessible_surfaceome/agents/surface_annotator/agent.py
from pathlib import Path
from anthropic import Anthropic

from .tool_registry import custom_tool_definitions

PROMPTS = Path(__file__).parent / "prompts"


def build_agent_payload() -> dict:
    return {
        "name": "Surface Proteome Annotator",
        "description": "Annotates human cell-surface proteins by querying UniProt, HGNC, "
                       "NCBI, EuropePMC, and Google Patents via custom tools.",
        "model": {"id": "claude-opus-4-7"},
        "system_prompt": (PROMPTS / "system.md").read_text(),
        "tools": [
            {
                "type": "agent_toolset_20260401",
                "default_config": {"permission_policy": {"type": "always_ask"}},
                "configs": [
                    {"name": "read", "permission_policy": {"type": "always_allow"}},
                    {"name": "grep", "permission_policy": {"type": "always_allow"}},
                    {"name": "glob", "permission_policy": {"type": "always_allow"}},
                    {"name": "web_fetch", "permission_policy": {"type": "always_allow"}},
                    {"name": "web_search", "permission_policy": {"type": "always_allow"}},
                    # bash, write, edit are not enabled — the agent doesn't need them
                    # and we want the orchestrator to own all persistence.
                ],
            },
            *custom_tool_definitions(),
        ],
        "metadata": {
            "owner": "accessible-surfaceome",
            "managed_by": "src/accessible_surfaceome/agents/surface_annotator",
        },
    }


def upsert_agent(client: Anthropic, *, current_id: str | None = None, current_version: int | None = None):
    payload = build_agent_payload()
    if current_id is None:
        return client.beta.agents.create(**payload)
    return client.beta.agents.update(current_id, version=current_version, **payload)
```

The agent does **not** include `bash`, `write`, or `edit`. Persistence (writing `data/annotations/{gene}.json`, run logs under `.runs/`) is the orchestrator's job, not the agent's.

## 6. Environment

```python
# src/accessible_surfaceome/agents/surface_annotator/environment.py
from anthropic import Anthropic


def build_environment_payload() -> dict:
    return {
        "name": "surface-annotator-py-3-12",
        "config": {
            "type": "cloud",
            "packages": {
                "pip": ["pandas", "numpy", "pydantic", "httpx"],
            },
            "networking": {
                "type": "limited",
                "allowed_hosts": [
                    "https://rest.uniprot.org",
                    "https://eutils.ncbi.nlm.nih.gov",
                    "https://www.ebi.ac.uk",
                    "https://rest.genenames.org",
                    "https://patents.google.com",
                    "https://api.openalex.org",
                    "https://api.platform.opentargets.org",
                ],
                "allow_package_managers": True,
                "allow_mcp_servers": False,
            },
        },
    }
```

We start with one environment. Add a permissive `dev` variant only if a real need surfaces; YAGNI until then.

## 7. Custom-tool dispatch

The detailed tool surface is specified in [docs/tools-design.md](../tools-design.md). For this guide, the shape of the dispatcher is what matters:

```python
# src/accessible_surfaceome/agents/surface_annotator/orchestrator.py
from anthropic import Anthropic

from .tool_registry import HANDLERS  # name → (handler, input_schema, description)


def stream_and_dispatch(client: Anthropic, *, session_id: str) -> None:
    with client.beta.sessions.events.stream(session_id) as stream:
        for event in stream:
            match event.type:
                case "agent.custom_tool_use":
                    handler = HANDLERS[event.name][0]
                    result_text = handler(**event.input).model_dump_json(indent=2)
                    client.beta.sessions.events.send(
                        session_id,
                        events=[{
                            "type": "user.custom_tool_result",
                            "custom_tool_use_id": event.id,
                            "content": [{"type": "text", "text": result_text}],
                        }],
                    )
                case "session.status_idle":
                    if getattr(event.stop_reason, "type", None) != "requires_action":
                        return
                case "session.error":
                    raise RuntimeError(f"session error: {event}")
```

Handlers are pure Python functions returning Pydantic models; the dispatcher JSON-stringifies them and sends a `user.custom_tool_result` event with the matching `custom_tool_use_id`. (See `docs/tools-design.md` § "How custom tools work in Claude Managed Agents" for the protocol details.)

## 8. Session lifecycle

For each gene:

1. Resolve `agent_id` and `environment_id` from `.runs/agents-registry.json`.
2. Create a fresh session (`client.beta.sessions.create(agent=agent_id, environment_id=environment_id)`). Pin the agent version for reproducibility runs.
3. Open the event stream; send the task message from `prompts/task_template.md` rendered with the gene symbol.
4. Dispatch `agent.custom_tool_use` events through `tool_registry.HANDLERS`.
5. On `session.status_idle` (without `requires_action`), persist the agent's final structured output to `data/annotations/{gene}.json` and write the run log under `.runs/<timestamp>-<gene>-<session_id>/`.

One session per gene. We do not treat sessions as durable memory; cross-gene state goes in `data/annotations/` and the audit tables.

## 9. Files, repos, memory — what we don't need yet

- **No GitHub repo mounts.** The agent reads no repo code. All inputs come from custom tools.
- **No Files API uploads.** Outputs fit in the agent's final structured message.
- **No memory stores.** Per-gene output is the persistence layer; nothing is shared across sessions.
- **No MCP servers.** Custom tools cover all upstream services we use.
- **No vaults.** API keys for upstream services live in `.env` on the orchestrator side; the cloud container doesn't need them because all upstream calls happen in our process via custom-tool handlers.

If any of these become necessary, add them then. Don't add them now.

## 10. Permission policy

Default: `always_ask` for any built-in tool we haven't explicitly allow-listed. Allow-listed today: `read`, `grep`, `glob`, `web_fetch`, `web_search`. Bash and any write/edit tool are not enabled. Custom tools are auto-allowed (they pause the session for orchestrator dispatch, not for human approval).

If a session pauses with `requires_action` for a built-in tool, the orchestrator surfaces the requested tool call and waits for an explicit human signal before sending `user.tool_confirmation`.

## 11. Sync workflow

`uv run accessible-surfaceome agents sync` does:

1. Read `.runs/agents-registry.json` (create if missing).
2. Build the environment payload; if missing in registry or hash changed, create/update and store the new ID + hash.
3. Build the agent payload; if missing, create. If the system-prompt sha or any other field changed, update with the version precondition and store the new version + sha.
4. Write the registry atomically.

Agent array fields (`tools`, `mcp_servers`, `skills`) are fully replaced on update — always send the complete desired set from the local definition.

## 12. Run workflow

`uv run accessible-surfaceome agents annotate <gene>` does:

1. Load the registry.
2. Render `prompts/task_template.md` with the gene symbol.
3. Create the session (pinning agent version when running batches for reproducibility).
4. Stream events, dispatch custom tools.
5. On idle, persist the agent's final `GeneAnnotation` to `data/annotations/{gene}.json`, run the deterministic validators (substring/source-id/char-offset/retraction checks per `docs/tools-design.md`), and emit the run log.

## 13. CI

```bash
uv sync --frozen
uv lock --check
bash scripts/check-py.sh        # ruff + ty + compile + pytest
```

`accessible-surfaceome agents sync` and live annotation runs are not in PR CI. Live tests run behind an env var:

```bash
ACCESSIBLE_SURFACEOME_LIVE=1 uv run pytest tests/live
```

## 14. Build order

Mapped onto the layout above:

1. **Pydantic models** in `tools/_shared/models.py` — `IdentifierBundle`, `DBVotePanel`, `UniProtSummary`, `MissDiagnosis`, `LiteraturePack`, `Paper`, `PatentSummary`, `Evidence`, `GeneAnnotation`. Drives every other decision.
2. **`gene_lookup`** end-to-end (all four modes). Smoke-test against KAAG1, CD19, ABCB9 at the function level — no agent yet.
3. **`agents/_support/client.py` + `events.py`** — Anthropic client factory and generic stream loop.
4. **`agents/surface_annotator/agent.py` + `environment.py`** — agent and environment payload builders. System prompt in `prompts/system.md`.
5. **`agents/surface_annotator/orchestrator.py`** + `tool_registry.py` — dispatch `gene_lookup`. End-to-end KAAG1 producing a `GeneAnnotation`.
6. **`agents/_support/registry.py`** + `accessible-surfaceome agents sync` — persist registry.
7. `gene_literature` (all four modes), wire into orchestrator.
8. `patent_lookup`, smoke-test against `WO2024036333A2`.
9. Run the six worked-example genes (CD19, ABCB9, KRAS, MSLN, ST3GAL1, KAAG1) end-to-end; compare against the hand-investigated ground truth in `docs/worked-examples/kaag1.md`.

## 15. Open questions

- **Registry commit policy.** `.runs/agents-registry.json` is gitignored by default. If a small team wants a shared `agent_id` so everyone uses the same remote agent, commit a non-secret variant (resource IDs are not secrets). Decide once we have a second user.
- **Agent version pinning for batches.** Default to pinned versions for batch annotation runs; unpinned latest for interactive iteration.
- **Tool-result size ceiling for `gene_literature.fetch_fulltext`.** Capped at 10k tokens with truncation flags per `docs/tools-design.md`; revisit once we have empirical data.
- **Whether the agent needs writable memory** for cross-gene patterns. Not now; revisit if the audit pass surfaces lessons that should propagate.

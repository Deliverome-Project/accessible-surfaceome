"""Local registry for remote Managed Agents resource IDs.

Persisted at ``.runs/agents-registry.json`` (gitignored). Records the agent ID
+ pinned version, environment ID, and a sha256 of the system prompt so
``agents sync`` can detect drift without round-tripping the API.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from accessible_surfaceome.paths import REPO_ROOT


@dataclass
class AgentEntry:
    id: str
    version: int | None = None
    system_prompt_sha256: str = ""


@dataclass
class EnvironmentEntry:
    id: str
    config_sha256: str = ""


@dataclass
class Registry:
    agents: dict[str, AgentEntry] = field(default_factory=dict)
    environments: dict[str, EnvironmentEntry] = field(default_factory=dict)


def default_registry_path() -> Path:
    return REPO_ROOT / ".runs" / "agents-registry.json"


def load(path: Path | None = None) -> Registry:
    p = path or default_registry_path()
    if not p.exists():
        return Registry()
    raw = json.loads(p.read_text())
    return Registry(
        agents={k: AgentEntry(**v) for k, v in (raw.get("agents") or {}).items()},
        environments={k: EnvironmentEntry(**v) for k, v in (raw.get("environments") or {}).items()},
    )


def save(reg: Registry, path: Path | None = None) -> Path:
    """Atomic write so a crash mid-write doesn't leave a half-baked registry."""

    p = path or default_registry_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "agents": {k: asdict(v) for k, v in reg.agents.items()},
        "environments": {k: asdict(v) for k, v in reg.environments.items()},
    }
    fd, tmp = tempfile.mkstemp(prefix="agents-registry.", suffix=".json", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, p)
    except BaseException:
        try:
            os.unlink(tmp)
        finally:
            raise
    return p


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

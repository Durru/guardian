from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

import yaml

import guardian_shared as shared

_GUARDIAN_HOME = os.environ.get("GUARDIAN_HOME", "")
_GUARDIAN_DATA = os.environ.get("GUARDIAN_DATA", "")

if _GUARDIAN_HOME:
    GENOME_DIR = Path(_GUARDIAN_HOME) / "genome"
elif _GUARDIAN_DATA:
    GENOME_DIR = Path(_GUARDIAN_DATA) / "genome"
else:
    GENOME_DIR = Path("/srv/guardian/genome")

BRANCHES_DIR = shared.BACKEND_DIR / "genome" / "branches"
IDENTITY_FILE = GENOME_DIR / "identity.yaml"
SCHEMA_FILE = GENOME_DIR / "schema.yaml"
CONSCIOUSNESS_FILE = GENOME_DIR / "consciousness.yaml"
UPDATES_DIR = GENOME_DIR / "updates"


def _branch_hash():
    """Machine-specific hash for the single branch."""
    return shared._branch_hash()


def _branch_path():
    """Single branch path for this machine."""
    return BRANCHES_DIR / _branch_hash()


def _default_branch_path():
    return BRANCHES_DIR / "default"


def _projects_dir():
    """Projects live inside the branch."""
    return _branch_path() / "projects"


def load_genome():
    """Load the full genome: identity (immutable) + schema + consciousness.

    The identity is yours (inmutable, no se modifica en runtime).
    Schema and consciousness are loaded with safe fallbacks.
    """
    result = {}
    if IDENTITY_FILE.exists():
        try:
            with open(IDENTITY_FILE, "r", encoding="utf-8") as f:
                result = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError):
            result = {}
    # Schema (v4): definition of brain levels, codegraph, observer, advisor
    if SCHEMA_FILE.exists():
        try:
            with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
                schema = yaml.safe_load(f) or {}
            result["schema"] = schema
        except (OSError, yaml.YAMLError):
            result["schema"] = _default_schema()
    else:
        result["schema"] = _default_schema()
    # Consciousness (v4): thresholds, modes, tracability, principles
    if CONSCIOUSNESS_FILE.exists():
        try:
            with open(CONSCIOUSNESS_FILE, "r", encoding="utf-8") as f:
                cons = yaml.safe_load(f) or {}
            result["consciousness"] = cons
        except (OSError, yaml.YAMLError):
            result["consciousness"] = _default_consciousness()
    else:
        result["consciousness"] = _default_consciousness()
    return result


def _default_schema():
    return {
        "schema_version": 4,
        "brain": {
            "levels": ["semantic", "episodic", "procedural", "reflection"],
            "global_levels": ["semantic_global", "procedural_global", "reflection_global"],
            "extended_levels": ["codegraph_symbols", "codegraph_edges", "prompt_log",
                                "decision_log", "stack_history", "test_results", "event_log"],
        },
        "codegraph": {"enabled": True, "languages": ["python", "typescript", "javascript", "go"]},
        "observer": {"enabled": True, "auto_save_prompts": True},
        "advisor": {"enabled": True, "max_context_tokens": 1000},
    }


def _default_consciousness():
    return {
        "thresholds": {"assume": 0.8, "ask_little_floor": 0.5, "ask_much_floor": 0.2},
        "modes": ["read", "plan", "build", "commit", "review"],
        "default_mode": "plan",
        "tracability": {"require_sources_for_assume": True, "max_sources_per_decision": 10},
        "principles": ["Razonar en base a lo que sabe, no a lo que se imagina",
                       "No ensuciar la ventana de contexto"],
    }


def apply_to_user_branch(branch_path: Path) -> dict:
    """v4: When the user does `guardian update`, apply the genome to their branch.

    This is one of the FEW functions that touches the user branch directly.
    The genome is the ONLY thing that decides what goes in the branch.
    """
    branch_path = Path(branch_path)
    branch_path.mkdir(parents=True, exist_ok=True)
    (branch_path / "evolution").mkdir(exist_ok=True)
    genome = load_genome()
    branch_file = branch_path / "branch.json"
    if branch_file.exists():
        try:
            with open(branch_file) as f:
                current = json.load(f)
        except (OSError, json.JSONDecodeError):
            current = {}
    else:
        current = {}
    current["genome_version"] = genome.get("schema", {}).get("schema_version", 4)
    current["genome_updated_at"] = shared._now_epoch() if hasattr(shared, "_now_epoch") else 0
    with open(branch_file, "w") as f:
        json.dump(current, f, indent=2)
    return {"ok": True, "branch": str(branch_path), "genome_version": current["genome_version"]}


def accept_user_proposal(branch_path: Path, proposal: dict) -> dict:
    """v4: Accept a new pattern proposal from the user's work into their branch.

    The user branch contains learnings/customizations. Only the genome
    decides what goes here (this function). Guardian proposes; genome accepts.
    """
    branch_path = Path(branch_path)
    proposals_dir = branch_path / "evolution" / "proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    proposal_id = f"prop_{shared._now_epoch() if hasattr(shared, '_now_epoch') else 0}"
    proposal_file = proposals_dir / f"{proposal_id}.json"
    with open(proposal_file, "w") as f:
        json.dump(proposal, f, indent=2)
    return {"ok": True, "id": proposal_id, "path": str(proposal_file)}


def load_branch(slug):
    """Load a single project's context within the machine's unique branch."""
    branch_path = _branch_path()
    identity_file = branch_path / "identity.yaml"
    state_file = branch_path / "state.json"
    identity = {}
    state = {}
    if identity_file.exists():
        with open(identity_file, "r", encoding="utf-8") as f:
            identity = yaml.safe_load(f) or {}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            state = {}
    # Return project-specific state merged in
    projects = state.get("projects", {})
    project_state = projects.get(slug, {})
    return identity, project_state, branch_path


def fork_branch(slug=None, force=False):
    """Create/load the SINGLE branch for this machine.
    
    With the new model:
    - There's ONE branch per machine (identified by machine-id hash)
    - Projects are sub-contexts within that branch
    - The branch holds consciousness, memory, knowledge, learnings for ALL projects
    - slug is only used to track per-project state within the branch
    """
    branch_path = _branch_path()
    if branch_path.exists() and not force:
        return _load_branch_state(branch_path)
    
    # Create default branch template if needed
    default_path = _default_branch_path()
    if not default_path.exists():
        default_path.mkdir(parents=True, exist_ok=True)
    
    # Create branch dirs
    branch_path.mkdir(parents=True, exist_ok=True)
    _ensure_dirs(branch_path)
    
    # Copy identity from genome with fork metadata
    genome = load_genome()
    branch_id = dict(genome) if genome else {}
    branch_id["forked_from"] = str(IDENTITY_FILE)
    branch_id["forked_at"] = shared.ts()
    branch_id["creator"] = genome.get("creator", "unknown")
    branch_id["branch_hash"] = _branch_hash()
    
    dst_id = branch_path / "identity.yaml"
    with open(dst_id, "w", encoding="utf-8") as f:
        yaml.dump(branch_id, f, default_flow_style=False, allow_unicode=True)
    
    state = _fresh_state()
    (branch_path / "state.json").write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    
    # If slug provided, initialize project entry
    if slug:
        state.setdefault("projects", {})[slug] = {
            "created": shared.ts(),
            "session_count": 0,
            "last_session": None,
        }
        (branch_path / "state.json").write_text(
            json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    
    return state, branch_path


def _load_branch_state(branch_path):
    state_file = branch_path / "state.json"
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            state = _fresh_state()
    else:
        state = _fresh_state()
    return state, branch_path


def _fresh_state():
    return {
        "version": "2.0.0",
        "machine_id": _branch_hash(),
        "created": shared.ts(),
        "forked_from_genome": str(IDENTITY_FILE),
        "branch_meta": {
            "session_count": 0,
            "last_session": None,
            "plan_sessions": 0,
            "build_sessions": 0,
        },
        "consciousness": {
            "thresholds": {
                "assume": 0.8,
                "ask_little_floor": 0.5,
                "ask_much_floor": 0.2,
            },
            "last_action": None,
            "last_confidence": 0.0,
        },
        "projects": {},
        "evolution": {
            "current_version": 0,
            "total_generations": 0,
            "last_generative_cycle": None,
        },
    }


def _ensure_dirs(branch_path):
    """Create all required subdirectories for the branch."""
    dirs = [
        branch_path / "consciousness",
        branch_path / "memory" / "cross-project",
        branch_path / "memory" / "projects",
        branch_path / "knowledge" / "tomes",
        branch_path / "knowledge" / "projects",
        branch_path / "learnings" / "cross-project",
        branch_path / "learnings" / "projects",
        branch_path / "context",
        branch_path / "evolved" / "commands",
        branch_path / "evolved" / "mcp_tools",
        branch_path / "evolved" / "context_providers",
        branch_path / "evolved" / "conciencia_actions",
        branch_path / "evolved" / "thresholds",
        branch_path / "evolved" / "patches",
        branch_path / "evolution" / "proposals",
        branch_path / "projects",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def init_project(slug):
    """Initialize a project entry within the single branch."""
    state, branch_path = fork_branch()
    projects = state.setdefault("projects", {})
    if slug in projects:
        return projects[slug]
    projects[slug] = {
        "created": shared.ts(),
        "session_count": 0,
        "last_session": None,
        "mode_count": {"plan": 0, "build": 0},
    }
    # Ensure project subdirs exist
    project_root = branch_path / "projects" / slug
    (project_root / "memory").mkdir(parents=True, exist_ok=True)
    (project_root / "knowledge").mkdir(parents=True, exist_ok=True)
    (project_root / "learnings").mkdir(parents=True, exist_ok=True)
    
    (branch_path / "state.json").write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return projects[slug]


def list_branches():
    """Return info about the single branch + its projects."""
    branch_path = _branch_path()
    if not branch_path.exists():
        return []
    
    state_file = branch_path / "state.json"
    state = {}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    
    identity_file = branch_path / "identity.yaml"
    identity = {}
    if identity_file.exists():
        with open(identity_file, "r", encoding="utf-8") as f:
            identity = yaml.safe_load(f) or {}
    
    projects = list(state.get("projects", {}).keys())
    branch_info = {
        "hash": _branch_hash(),
        "path": str(branch_path),
        "machine_id": state.get("machine_id", _branch_hash()),
        "forked_from_genome": state.get("forked_from_genome", ""),
        "created": state.get("created", ""),
        "creator": identity.get("creator", "unknown"),
        "projects": projects,
        "session_count": state.get("branch_meta", {}).get("session_count", 0),
        "evolution_version": state.get("evolution", {}).get("current_version", 0),
        "total_generations": state.get("evolution", {}).get("total_generations", 0),
    }
    return [branch_info]


def branch_status(slug=None):
    """Return full status of the single branch, optionally filtered by project."""
    branch_path = _branch_path()
    if not branch_path.exists():
        return None
    
    identity_file = branch_path / "identity.yaml"
    identity = {}
    if identity_file.exists():
        with open(identity_file, "r", encoding="utf-8") as f:
            identity = yaml.safe_load(f) or {}
    
    state_file = branch_path / "state.json"
    state = {}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    
    result = {
        "hash": _branch_hash(),
        "path": str(branch_path),
        "identity": identity,
        "state": state,
        "projects": list(state.get("projects", {}).keys()),
    }
    
    if slug:
        project_data = state.get("projects", {}).get(slug, {})
        result["project"] = {"slug": slug, **project_data}
    
    return result


def branch_diff():
    """Show differences between genome identity and branch identity."""
    genome = load_genome()
    branch_path = _branch_path()
    identity_file = branch_path / "identity.yaml"
    branch_id = {}
    if identity_file.exists():
        with open(identity_file, "r", encoding="utf-8") as f:
            branch_id = yaml.safe_load(f) or {}
    
    diffs = []
    g_id = genome.get("identity", {})
    b_id = branch_id.get("identity", {}) if isinstance(branch_id, dict) else {}
    for key in g_id:
        if g_id.get(key) != b_id.get(key):
            diffs.append({"key": key, "genome": g_id.get(key), "branch": b_id.get(key)})
    return diffs


# ── Legacy backward compat aliases ─────────────────────────────

def _slug_hash(slug):
    """Legacy: hash a slug (kept for backward compat)."""
    return hashlib.sha256(slug.encode("utf-8")).hexdigest()[:16]

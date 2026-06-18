from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path

import yaml

import guardian_shared as shared

def _genome_dir():
    home = os.environ.get("GUARDIAN_HOME", "")
    data = os.environ.get("GUARDIAN_DATA", "")
    if home:
        return Path(home) / "genome"
    if data:
        return Path(data) / "genome"
    return Path("/srv/guardian/genome")


def genome_identity_path():
    return _genome_dir() / "identity.yaml"


def genome_schema_path():
    return _genome_dir() / "schema.yaml"


def genome_consciousness_path():
    return _genome_dir() / "consciousness.yaml"


def genome_updates_dir():
    return _genome_dir() / "updates"


def load_genome():
    """Load the full genome: identity (immutable) + schema + consciousness.

    The identity is yours (inmutable, no se modifica en runtime).
    Schema and consciousness are loaded with safe fallbacks.
    """
    gd = _genome_dir()
    identity_file = gd / "identity.yaml"
    schema_file = gd / "schema.yaml"
    consciousness_file = gd / "consciousness.yaml"
    result = {}
    if identity_file.exists():
        try:
            with open(identity_file, "r", encoding="utf-8") as f:
                result = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError):
            result = {}
    if schema_file.exists():
        try:
            with open(schema_file, "r", encoding="utf-8") as f:
                schema = yaml.safe_load(f) or {}
            result["schema"] = schema
        except (OSError, yaml.YAMLError):
            result["schema"] = _default_schema()
    else:
        result["schema"] = _default_schema()
    if consciousness_file.exists():
        try:
            with open(consciousness_file, "r", encoding="utf-8") as f:
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
    Creates a .bak backup of the previous branch.json automatically.
    """
    import shutil
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
    # Backup pre-update state
    if branch_file.exists() and current:
        backup_file = branch_path / f"branch.json.bak.{int(time.time())}"
        shutil.copy2(str(branch_file), str(backup_file))
    current["genome_version"] = genome.get("schema", {}).get("schema_version", 4)
    current["genome_updated_at"] = round(time.time(), 2)
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
    """Load project's identity from its branch.json."""
    target = shared.project_dir(slug)
    branch_file = target / "branch.json"
    if not branch_file.exists():
        return {}, {}, target
    try:
        data = json.loads(branch_file.read_text(encoding="utf-8"))
        return data, {}, target
    except (json.JSONDecodeError, OSError):
        return {}, {}, target


def fork_branch(slug=None, force=False):
    """Initialize a project branch with identity forked from genome.
    
    Each project is its own branch/world. This function creates
    the branch.json with the genome's identity and sets up subdirs.
    """
    if not slug:
        return {}, shared.project_dir("_default")
    target = shared.project_dir(slug)
    branch_file = target / "branch.json"
    if branch_file.exists() and not force:
        try:
            data = json.loads(branch_file.read_text(encoding="utf-8"))
            return data, target
        except (json.JSONDecodeError, OSError):
            pass
    
    genome = load_genome()
    branch_data = {
        "slug": slug,
        "genome_version": genome.get("schema", {}).get("schema_version", 4),
        "forked_from_genome": str(_genome_dir() / "identity.yaml"),
        "created": shared.ts(),
        "creator": genome.get("creator", "unknown"),
        "session_count": 0,
        "last_session": None,
        "consciousness": {"last_action": None, "last_confidence": 0.0},
        "evolution": {"generation": 0, "last_cycle": None},
    }
    branch_file.write_text(json.dumps(branch_data, indent=2), encoding="utf-8")
    
    for d in ("brain", "knowledge/tomes", "learnings", "evolution/proposals"):
        (target / d).mkdir(parents=True, exist_ok=True)
    
    return branch_data, target


def init_project(slug):
    """Initialize a project entry."""
    target = shared.project_dir(slug)
    fork_branch(slug)
    return {"slug": slug, "path": str(target), "created": shared.ts()}


def list_branches():
    """Return info about all projects (each project is its own branch/world)."""
    branches = []
    if not shared.MEMORY_DIR.exists():
        return branches
    for d in sorted(shared.MEMORY_DIR.iterdir()):
        if not d.is_dir():
            continue
        slug = d.name
        branch_file = d / "branch.json"
        data = {}
        if branch_file.exists():
            try:
                data = json.loads(branch_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        branches.append({
            "slug": slug,
            "path": str(d),
            "created": data.get("created", ""),
            "creator": data.get("creator", "unknown"),
            "genome_version": data.get("genome_version", "?"),
            "session_count": data.get("session_count", 0),
            "evolution_version": data.get("evolution", {}).get("generation", 0),
        })
    return branches


def branch_status(slug=None):
    """Return status of one or all projects."""
    if not slug:
        return list_branches()
    target = shared.project_dir(slug)
    branch_file = target / "branch.json"
    if not branch_file.exists():
        return None
    try:
        data = json.loads(branch_file.read_text(encoding="utf-8"))
        data["path"] = str(target)
        return data
    except (json.JSONDecodeError, OSError):
        return None


def branch_diff():
    """Compare current genome with a project's branch.json."""
    genome = load_genome()
    return {"genome_version": genome.get("schema", {}).get("schema_version", 4)}


def _slug_hash(slug):
    return hashlib.sha256(slug.encode("utf-8")).hexdigest()[:16]

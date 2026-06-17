#!/usr/bin/env python3
"""
Guardian Absorb System — skill scanning, rating, relevance matching, and learning.
Zero deps, JSONL-based usage tracking.

Commands:
  scan [--force]
  match <slug>
  learn <slug> <skillname> <action> [rating]
  suggest <slug> [--all]
  status <slug>
"""
import json, os, sys, hashlib, re
from pathlib import Path

import guardian_shared as shared
from guardian_shared import _

SKILLS_GLOBAL = shared.BACKEND_DIR / "skills-global.json"
MEMORY_DIR = shared.MEMORY_DIR
SKILL_DIRS = [
    Path(os.environ.get("HOME", "/root")) / ".agents" / "skills",
    Path(os.environ.get("HOME", "/root")) / ".config" / "opencode" / "skills",
]
ALWAYS_RELEVANT = {"nexxoria-guardian", "brainstorming", "context-engineering"}


def _knowledge_dir(slug):
    """Path to project knowledge tomes within the branch (fallback to legacy)."""
    new_path = shared.branch_path_for(slug, "knowledge", "tomes")
    if new_path.exists():
        return new_path
    legacy = MEMORY_DIR / slug / "knowledge" / "tomes"
    if legacy.exists():
        return legacy
    return new_path


def _knowledge_index_path(slug):
    """Path to knowledge index within the branch (fallback to legacy)."""
    new_path = shared.branch_path_for(slug, "knowledge", "index.json")
    if new_path.exists():
        return new_path
    legacy = MEMORY_DIR / slug / "knowledge" / "index.json"
    if legacy.exists():
        return legacy
    return new_path


def _skill_summary(skill):
    rating = skill.get("rating", {})
    total = skill.get("total", 0)
    lines = [
        f"# {skill.get('name', 'skill')}",
        "",
        skill.get("description", "") or "Skill absorbido como base de conocimiento.",
        "",
        "## Puntaje",
        f"- total: {total}",
        f"- stars: {skill.get('stars', '')}",
        "",
        "## Señales",
    ]
    if rating:
        for k, v in rating.items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- (sin rating)")
    triggers = skill.get("triggers", [])
    if triggers:
        lines.extend(["", "## Triggers"])
        lines.extend([f"- {t}" for t in triggers[:10]])
    keywords = skill.get("keywords", [])
    if keywords:
        lines.extend(["", "## Keywords"])
        lines.extend([f"- {k}" for k in keywords[:20]])
    return "\n".join(lines).strip() + "\n"


def cmd_ingest(slug, rebuild=False):
    """Convert matched skills into knowledge tomes for RAG consumption."""
    if not slug:
        print("Falta el slug del proyecto")
        return 1

    skills_data = _read_skills_json(slug)
    if not skills_data or not skills_data.get("scores"):
        print("  No hay skills clasificados. Ejecutá 'guardian absorb classify <slug>' primero.")
        return 1

    knowledge_dir = _knowledge_dir(slug)
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    skills = _read_global().get("skills", {})
    selected = skills_data.get("hot") or skills_data.get("relevant") or []
    if not selected:
        selected = list(skills_data.get("scores", {}).keys())[:10]

    tomes = []
    for name in selected:
        skill = skills.get(name, {"name": name, "description": ""})
        tome_name = f"{name}.md"
        tome_path = knowledge_dir / tome_name
        if tome_path.exists() and not rebuild:
            tomes.append(tome_name)
            continue
        tome_path.write_text(_skill_summary(skill), encoding="utf-8")
        tomes.append(tome_name)

    index = {
        "updated": shared.ts(),
        "tomes": tomes,
        "source": "absorb",
    }
    _knowledge_index_path(slug).parent.mkdir(parents=True, exist_ok=True)
    _knowledge_index_path(slug).write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")

    print(_("  📚 {n} tomos de conocimiento listos para RAG", n=len(tomes)))
    return 0

# ── helpers ──────────────────────────────────────────────────────────

def _read_memory(slug):
    return shared.read_memory(slug)

def _write_memory(slug, entries):
    mf = MEMORY_DIR / slug / "memory.jsonl"
    with open(mf, "w") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

def _read_global():
    if not SKILLS_GLOBAL.exists():
        return {"version": 1, "skills": {}, "last_absorb": None}
    with open(SKILLS_GLOBAL) as f:
        data = json.load(f)
    # Migrate from list format to dict format
    if isinstance(data.get("skills"), list):
        skills = {}
        for s in data["skills"]:
            skills[s["name"]] = s
        data["skills"] = skills
    return data

def _write_global(data):
    with open(SKILLS_GLOBAL, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def _read_skills_json(slug):
    data = shared.read_skills_json(slug)
    if "scores" not in data:
        data["scores"] = {}
    if "hot" not in data:
        data["hot"] = []
    if "last_match" not in data:
        data["last_match"] = None
    return data

def _write_skills_json(slug, data):
    shared.write_skills_json(slug, data)

def _read_config(slug):
    return shared.read_config(slug)

# ── rating engine ────────────────────────────────────────────────────

def rate_skill(filepath):
    """Analyze SKILL.md content and return (scores dict, total, stars, description, triggers)."""
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except FileNotFoundError:
        return {}, 0, "", "", []

    scores = {}

    # 1. Frontmatter (0-5)
    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if fm_match:
        fm = fm_match.group(1)
        has_name = "name:" in fm
        has_desc = "description:" in fm
        scores["frontmatter"] = 5 if (has_name and has_desc) else (3 if (has_name or has_desc) else 1)
    else:
        scores["frontmatter"] = 0

    # 2. Triggers (0-10)
    trigger_match = re.search(r"^##\s*(Trigger|When|Cuándo|Use when|Se activa)", content, re.MULTILINE | re.IGNORECASE)
    trigger_items = []
    if trigger_match:
        section = content[trigger_match.end():]
        ns = re.search(r"^##\s", section, re.MULTILINE)
        if ns:
            section = section[:ns.start()]
        trigger_items = re.findall(r"^\s*[-*]\s+(.+)", section, re.MULTILINE)
        trigger_items = [t.strip() for t in trigger_items if t.strip()]
    scores["triggers"] = min(10, len(trigger_items) * 3)

    # 3. Workflow steps (0-10)
    steps = re.findall(r"^\d+\.\s+", content, re.MULTILINE)
    checklists = re.findall(r"\[[\sx]\]", content, re.MULTILINE | re.IGNORECASE)
    has_workflow_section = bool(re.search(r"^##\s*(Flow|Workflow|Steps|Process|Cómo|Proceso)", content, re.MULTILINE | re.IGNORECASE))
    wf_score = len(steps) + len(checklists)
    if has_workflow_section and wf_score == 0:
        wf_score = 2  # Has the section but no explicit steps
    scores["workflow"] = min(10, wf_score)

    # 4. Examples / code blocks (0-10)
    code_blocks = re.findall(r"```", content)
    scores["examples"] = min(10, len(code_blocks) // 2)

    # 5. DO/DON'T sections (0-5)
    has_do = bool(re.search(r"DO\b|✅|✓|Hacer|Best Practice", content, re.IGNORECASE))
    has_dont = bool(re.search(r"DON'T|❌|✗|NO hacer|Avoid|Never|MAL", content, re.IGNORECASE))
    scores["do_dont"] = 5 if (has_do and has_dont) else (3 if (has_do or has_dont) else 0)

    # 6. Depth — sections + subsections (0-10)
    sections = re.findall(r"^##\s+", content, re.MULTILINE)
    subsections = re.findall(r"^###\s+", content, re.MULTILINE)
    depth_score = len(sections) + len(subsections)
    scores["depth"] = min(10, depth_score)

    total = sum(scores.values())
    if total <= 16:
        stars = "★"
    elif total <= 33:
        stars = "★★"
    else:
        stars = "★★★"

    # Description from frontmatter or first paragraph
    description = ""
    if fm_match:
        fm_lines = fm_match.group(1).split("\n")
        for line in fm_lines:
            if line.strip().startswith("description:"):
                description = line.split(":", 1)[1].strip().strip('"').strip("'")
                break
    if not description:
        lines = content.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
                description = stripped[:200]
                break

    return scores, total, stars, description, trigger_items

def extract_keywords(name, description, triggers, content):
    """Extract searchable keywords from skill metadata."""
    keywords = set()
    for part in name.split("-"):
        part = part.strip().lower()
        if len(part) > 2:
            keywords.add(part)
    if description:
        for word in re.findall(r"[a-zA-Záéíóúñ]{3,}", description.lower()):
            keywords.add(word)
    for t in triggers:
        for word in re.findall(r"[a-zA-Záéíóúñ]{3,}", t.lower()):
            keywords.add(word)
    # From section headers (first 80 lines)
    for line in content.split("\n")[:80]:
        if line.startswith("## ") or line.startswith("# "):
            for word in re.findall(r"[a-zA-Záéíóúñ]{3,}", line.lower()):
                keywords.add(word)
    return sorted(keywords)

# ── commands ─────────────────────────────────────────────────────────

def cmd_scan(force=False):
    """Scan skill directories, rate new/changed skills."""
    data = _read_global()
    skills = data.get("skills", {})

    scanned = set()
    changes = {"new": 0, "updated": 0, "removed": 0, "unchanged": 0}

    for skills_dir in SKILL_DIRS:
        if not skills_dir.exists():
            continue
        for skill_dir in sorted(skills_dir.iterdir()):
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            name = skill_dir.name
            scanned.add(name)
            mtime = skill_file.stat().st_mtime

            cached = skills.get(name, {})
            if not force and cached and cached.get("mtime") == mtime:
                changes["unchanged"] += 1
                continue

            scores, total, stars, description, triggers = rate_skill(skill_file)
            content = skill_file.read_text(encoding="utf-8", errors="replace")
            keywords = extract_keywords(name, description, triggers, content)

            skills[name] = {
                "name": name,
                "file": str(skill_file),
                "mtime": mtime,
                "rating": scores,
                "total": total,
                "stars": stars,
                "description": description[:300] if description else "",
                "triggers": triggers[:10],
                "keywords": keywords[:50],
            }

            if name in cached and cached.get("mtime") != mtime:
                changes["updated"] += 1
            elif name not in cached:
                changes["new"] += 1

    # Detect removed skills
    for name in list(skills.keys()):
        if name not in scanned:
            del skills[name]
            changes["removed"] += 1

    data["skills"] = skills
    data["last_absorb"] = shared.ts()
    _write_global(data)

    parts = []
    if changes["new"]:
        parts.append(f"{changes['new']} nuevo(s)")
    if changes["updated"]:
        parts.append(f"{changes['updated']} actualizado(s)")
    if changes["removed"]:
        parts.append(f"{changes['removed']} eliminado(s)")
    parts.append(f"{changes['unchanged']} sin cambios")
    print(_("  📦 Skills: {}", ', '.join(parts)))

    # Return new/updated skill names for auto-scoring
    new_skills = []
    for name in scanned:
        if name in skills and (not data.get("last_absorb") or skills[name].get("mtime", 0) > 0):
            # Report all skills in summary
            pass
    return skills

def cmd_match(slug):
    """Score skills against a project, update skills.json, print hot skills."""
    data = _read_global()
    skills = data.get("skills", {})
    config = _read_config(slug)

    last_absorb = data.get("last_absorb")
    existing_skills = _read_skills_json(slug)
    last_match = existing_skills.get("last_match")
    if last_match and last_absorb and last_match >= last_absorb:
        print(shared._("skills_already_current", slug=slug, last=last_match[:19]))
        return

    project_type = config.get("project", {}).get("type", "") if isinstance(config.get("project"), dict) else ""
    stack = config.get("stack", {}).get("detected", "") if isinstance(config.get("stack"), dict) else ""
    framework = config.get("stack", {}).get("framework", "") if isinstance(config.get("stack"), dict) else ""

    # Usage stats from memory
    usage = {}
    for e in _read_memory(slug):
        if e.get("type") == "skill_usage":
            usage[e.get("skill", "")] = e.get("hits", 1)

    scored = []
    for name, skill in skills.items():
        rating_total = skill.get("total", 25)
        keywords = skill.get("keywords", [])
        triggers = skill.get("triggers", [])

        score = float(rating_total) * 0.6

        # Always relevant skills get a baseline
        if name in ALWAYS_RELEVANT:
            score += 25

        # Stack/framework match
        search_terms = keywords + [t.lower() for t in triggers]
        for term in search_terms:
            tl = term.lower()
            if stack and stack.lower() in tl:
                score += 20
                break
        for term in search_terms:
            tl = term.lower()
            if framework and framework.lower() in tl:
                score += 15
                break
        for term in search_terms:
            tl = term.lower()
            if project_type and project_type.lower() in tl:
                score += 10
                break

        # Usage boost
        hits = usage.get(name, 0)
        if hits > 0:
            score += min(10, hits * 2)

        scored.append((name, round(score, 1), skill.get("stars", ""), skill.get("total", 0)))

    scored.sort(key=lambda x: -x[1])

    hot = [n for n, s, _, _ in scored if s > 50]
    warm = [n for n, s, _, _ in scored if 30 < s <= 50]
    relevant = hot + warm

    skills_data = {
        "relevant": relevant,
        "scores": {n: s for n, s, _, _ in scored},
        "hot": hot,
        "last_match": shared.ts(),
    }
    _write_skills_json(slug, skills_data)
    cmd_ingest(slug)

    print(_("  📦 {} skills relevantes para {slug}", len(relevant), slug=slug))
    if hot:
        print(_("  🔥 Hot — carga automática: {}", ', '.join(hot[:5])))
    if warm:
        print(_("  🟡 Warm — disponibles: {}", ', '.join(warm[:5])))
    print()
    print(_("  Mejores 5 por relevancia:"))
    for name, s, stars, total in scored[:5]:
        bar = "█" * int(s / 10) + "░" * (10 - int(s / 10))
        print(_("    {bar} {name:<30} {s:>5.1f}  {stars}", bar=bar, name=name, s=s, stars=stars))

    return hot

def cmd_learn(slug, skillname, action, rating=None):
    """Record skill usage in memory for learning."""
    entries = _read_memory(slug)
    now = shared.ts()

    found = None
    for e in entries:
        if e.get("type") == "skill_usage" and e.get("skill") == skillname:
            found = e
            break

    if found:
        found["hits"] = found.get("hits", 1) + 1
        found["last_used"] = now
        found["ts"] = now
        found["content"] = f"skill {skillname}: {action}"
        acts = found.get("actions", [])
        if len(acts) > 20:
            acts = acts[-20:]
        acts.append(action)
        found["actions"] = acts
        if rating is not None:
            found["rating"] = rating
    else:
        eid = hashlib.md5(f"skill_usage:{slug}:{skillname}".encode()).hexdigest()[:16]
        entries.append({
            "id": eid,
            "ts": now,
            "type": "skill_usage",
            "content": f"skill {skillname}: {action}",
            "skill": skillname,
            "slug": slug,
            "hits": 1,
            "last_used": now,
            "actions": [action],
            "ttl": 90,
        })

    # Also add to scope project memory for context visibility
    _write_memory(slug, entries)

    hits = found["hits"] if found else 1
    action_label = {"used": "lo usaste", "success": "funcionó bien", "fail": "no funcionó"}.get(action, action)
    print(_("  📈 {skillname}: {action_label} (x{hits})", skillname=skillname, action_label=action_label, hits=hits))
    return 0

def cmd_suggest(slug, show_all=False, json_output=False):
    """Suggest relevant skills with scores."""
    data = _read_global()
    skills = data.get("skills", {})
    skills_data = _read_skills_json(slug)
    scores = skills_data.get("scores", {})
    hot = skills_data.get("hot", [])

    if not scores:
        if json_output:
            print(json.dumps({"slug": slug, "items": []}, ensure_ascii=False))
            return 0
        print("  Todavía no hay skills matcheados. Primero ejecutá: guardian_absorb.py match <slug>")
        return 1

    ordered = sorted(scores.items(), key=lambda x: -x[1])

    if json_output:
        items = []
        for name, score in ordered:
            skill = skills.get(name, {})
            if not show_all and score < 20:
                continue
            items.append({
                "name": name,
                "score": score,
                "hot": name in hot,
                "stars": skill.get("stars", ""),
                "description": skill.get("description", "")[:60],
            })
        print(json.dumps({"slug": slug, "items": items, "hot_count": len(hot)}, ensure_ascii=False))
        return 0

    print(_("  📚 Skills recomendados para {slug}", slug=slug))
    print()
    for name, score in ordered:
        skill = skills.get(name, {})
        if not show_all and score < 20:
            continue
        tag = "🔥" if name in hot else "🟡" if score > 30 else "  "
        bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
        stars = skill.get("stars", "")
        desc = skill.get("description", "")[:60]
        print(_("  {tag} {bar} {name:<30} {score:>5.1f}  {stars}  {desc}", tag=tag, bar=bar, name=name, score=score, stars=stars, desc=desc))
    print()
    print(_("  {} skill(s) en hot list — se cargan solos en cada sesión", len(hot)))
    return 0

def cmd_status(slug=None, json_output=False):
    """Show absorption status."""
    data = _read_global()
    skills = data.get("skills", {})
    last = data.get("last_absorb", "nunca")

    total = len(skills)
    by_stars = {}
    for s in skills.values():
        st = s.get("stars", "")
        by_stars[st] = by_stars.get(st, 0) + 1

    if json_output:
        result = {
            "total_skills": total,
            "by_stars": by_stars,
            "last_absorb": last,
        }
        if slug:
            skills_data = _read_skills_json(slug)
            result["relevant_count"] = len(skills_data.get("relevant", []))
            result["hot_count"] = len(skills_data.get("hot", []))
            result["hot_list"] = skills_data.get("hot", [])
        print(json.dumps(result, ensure_ascii=False))
        return 0

    print(_("  📦 Skills catalogados: {total}   (último escaneo: {last})", total=total, last=last))
    for st, count in sorted(by_stars.items()):
        print(_("    {st} {count} skill(s)", st=st, count=count))

    if slug:
        skills_data = _read_skills_json(slug)
        rel = skills_data.get("relevant", [])
        hot = skills_data.get("hot", [])
        print(_("  Proyecto {slug}: {} relevantes, {} hot", len(rel), len(hot), slug=slug))
    return 0


# ── auto-classification ────────────────────────────────────────


def _detect_project_features(root):
    """Analyze project files and return a dict of detected features."""
    root = Path(root)
    features = {
        "languages": set(),
        "frameworks": set(),
        "databases": set(),
        "tools": set(),
        "patterns": set(),
        "dirs": set(),
        "keywords": set(),
        "package_managers": set(),
    }

    # Detect dir structure
    for d in root.iterdir():
        if d.is_dir() and not d.name.startswith("."):
            features["dirs"].add(d.name)

    # package.json
    pkg = root / "package.json"
    if pkg.exists():
        features["languages"].add("javascript")
        features["package_managers"].add("npm")
        try:
            data = json.loads(pkg.read_text())
            all_deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            for dep in all_deps:
                dl = dep.lower()
                if "next" in dl: features["frameworks"].add("next")
                if "react" in dl: features["frameworks"].add("react")
                if "vue" in dl: features["frameworks"].add("vue")
                if "svelte" in dl: features["frameworks"].add("svelte")
                if "angular" in dl: features["frameworks"].add("angular")
                if "express" in dl: features["frameworks"].add("express")
                if "django" in dl: features["frameworks"].add("django")
                if "tailwindcss" in dl: features["tools"].add("tailwind")
                if "typescript" in dl or "ts" == dl: features["languages"].add("typescript")
                if "prisma" in dl: features["databases"].add("prisma")
                if "postgres" in dl: features["databases"].add("postgresql")
                if "redis" in dl: features["tools"].add("redis")
                if "vitest" in dl or "jest" in dl: features["tools"].add("test")
                if "eslint" in dl: features["tools"].add("eslint")
                if "shadcn" in dl: features["tools"].add("shadcn")
                # Framework sub-types
                if "next" in dl and "next" not in features["frameworks"]:
                    features["frameworks"].add("next")
        except json.JSONDecodeError:
            pass

    # pyproject.toml
    pyproj = root / "pyproject.toml"
    if pyproj.exists():
        features["languages"].add("python")
        content = pyproj.read_text().lower()
        if "django" in content: features["frameworks"].add("django")
        if "fastapi" in content: features["frameworks"].add("fastapi")
        if "flask" in content: features["frameworks"].add("flask")
        if "pytest" in content: features["tools"].add("pytest")
        if "poetry" in content or "pdm" in content: features["package_managers"].add("pip")
        if "ruff" in content: features["tools"].add("ruff")
        if "sqlalchemy" in content: features["databases"].add("sqlalchemy")

    # requirements.txt
    req = root / "requirements.txt"
    if req.exists():
        features["languages"].add("python")
        features["package_managers"].add("pip")

    # Cargo.toml
    cargo = root / "Cargo.toml"
    if cargo.exists():
        features["languages"].add("rust")
        content = cargo.read_text().lower()
        if "actix" in content: features["frameworks"].add("actix")
        if "axum" in content: features["frameworks"].add("axum")
        if "rocket" in content: features["frameworks"].add("rocket")
        if "tokio" in content: features["tools"].add("tokio")

    # composer.json
    comp = root / "composer.json"
    if comp.exists():
        features["languages"].add("php")

    # .csproj files
    if list(root.glob("*.csproj")):
        features["languages"].add("csharp")

    # go.mod
    if (root / "go.mod").exists():
        features["languages"].add("go")

    # Dockerfile
    if (root / "Dockerfile").exists():
        features["tools"].add("docker")

    # Docker compose
    if (root / "docker-compose.yml").exists() or (root / "docker-compose.yaml").exists():
        features["tools"].add("docker-compose")

    # README keywords
    for readme in root.glob("README*"):
        try:
            text = readme.read_text(encoding="utf-8", errors="replace").lower()
            for kw in ["wordpress", "woocommerce", "shopify", "saas", "api", "rest", "graphql",
                       "landing page", "ecommerce", "blog", "dashboard", "portfolio", "cli",
                       "telegram", "bot", "chrome extension", "vscode extension", "mobile"]:
                if kw in text:
                    features["keywords"].add(kw)
            # Extract common tech keywords
            for word in re.findall(r'\b[a-z]{3,20}\b', text):
                if word in ("nextjs", "nuxt", "vuejs", "sveltekit", "remix", "gatsby",
                           "tailwind", "bootstrap", "material", "chakra", "shadcn",
                           "prisma", "typeorm", "mongoose", "sequelize",
                           "docker", "kubernetes", "aws", "gcp", "azure", "vercel",
                           "netlify", "heroku", "digitalocean", "supabase", "firebase"):
                    features["tools"].add(word)
                    features["keywords"].add(word.replace("js", "").replace("ui", ""))
        except (OSError, UnicodeError):
            pass

    # git config
    git_config = root / ".git" / "config"
    if git_config.exists():
        features["tools"].add("git")

    # Convert sets to sorted lists
    return {k: sorted(v) for k, v in features.items()}


def _score_skill_vs_features(name, skill, features):
    """Score a single skill against detected project features. Returns (score, reasons)."""
    keywords = [k.lower() for k in skill.get("keywords", [])]
    triggers = [t.lower() for t in skill.get("triggers", [])]
    all_terms = set(keywords + triggers)
    score = float(skill.get("total", 25)) * 0.5
    reasons = []

    # Language matches (+15 each)
    for lang in features.get("languages", []):
        if lang in all_terms:
            score += 15
            reasons.append(f"lang:{lang}")

    # Framework matches (+20 each)
    for fw in features.get("frameworks", []):
        if fw in all_terms:
            score += 20
            reasons.append(f"fw:{fw}")

    # Database matches (+15 each)
    for db in features.get("databases", []):
        if db in all_terms:
            score += 15
            reasons.append(f"db:{db}")

    # Tool matches (+10 each)
    for tool in features.get("tools", []):
        if tool in all_terms:
            score += 10
            reasons.append(f"tool:{tool}")

    # Pattern matches (+10 each)
    for pat in features.get("patterns", []):
        if pat in all_terms:
            score += 10
            reasons.append(f"pat:{pat}")

    # Directory names (+5 each)
    for d in features.get("dirs", []):
        if d.lower() in all_terms:
            score += 5
            reasons.append(f"dir:{d}")

    # README keyword matches (+8 each)
    for kw in features.get("keywords", []):
        kw_lower = kw.lower().replace(" ", "_")
        if kw_lower in all_terms or kw in all_terms:
            score += 8
            reasons.append(f"kw:{kw}")

    # Always-relevant baseline
    if name in ALWAYS_RELEVANT:
        score += 25
        reasons.append("always")

    # Name-based directory match: skill name parts in project dirs
    name_parts = name.split("-")
    for part in name_parts:
        if part in features.get("dirs", set()) or part in [d.lower() for d in features.get("dirs", [])]:
            score += 8
            reasons.append(f"dir_match:{part}")
            break

    # Package manager match
    for pm in features.get("package_managers", []):
        if pm in all_terms:
            score += 5
            reasons.append(f"pm:{pm}")

    return round(score, 1), reasons[:8]


def cmd_classify(slug, json_output=False):
    """Deep project analysis: auto-classify skills with real file detection."""
    config = _read_config(slug)
    if not config:
        print(_("  ❌ Proyecto '{slug}' no encontrado.", slug=slug))
        return 1

    root = config.get("project_root", "")
    if not root or not Path(root).exists():
        print(_("  ❌ Project root no encontrado: {root}", root=root))
        return 1

    data = _read_global()
    all_skills = data.get("skills", {})
    if not all_skills:
        print("  No hay skills escaneados. Ejecutá 'guardian absorb scan' primero.")
        return 1

    verbose = not json_output
    if verbose:
        print(_("  🔬 Clasificando skills para {slug}...", slug=slug))
        print(_("  📁 Analizando: {root}", root=root))

    # Detect features
    features = _detect_project_features(root)
    lang_s = ", ".join(features["languages"]) or "(ninguno)"
    fw_s = ", ".join(features["frameworks"]) or "(ninguno)"
    tools_s = ", ".join(features["tools"][:8]) or "(ninguno)"
    if verbose:
        print(_("     Lenguajes: {lang_s}", lang_s=lang_s))
        print(_("     Frameworks: {fw_s}", fw_s=fw_s))
        print(_("     Herramientas: {tools_s}", tools_s=tools_s))
        print()

    # Score all skills
    scored = []
    for name, skill in all_skills.items():
        s, reasons = _score_skill_vs_features(name, skill, features)
        scored.append((name, s, reasons, skill.get("stars", ""), skill.get("total", 0)))

    scored.sort(key=lambda x: -x[1])

    # Classification tiers
    hot = [(n, s, r) for n, s, r, _, _ in scored if s > 50]
    warm = [(n, s, r) for n, s, r, _, _ in scored if 30 < s <= 50]
    cold = [(n, s, r) for n, s, r, _, _ in scored if s <= 30]

    # Print classification
    def _print_tier(title, icon, items, max_show):
        if not items:
            if verbose:
                print(_("  {icon} {title}: (ninguno)", icon=icon, title=title))
            return
        if verbose:
            print(_("  {icon} {title}:", icon=icon, title=title))
            for name, s, reasons in items[:max_show]:
                bar = "█" * min(10, max(1, int(s / 10)))
                reason_str = f"  [{', '.join(reasons[:4])}]" if reasons else ""
                print(_("    {bar} {name:<30} {s:>5.1f}{reason_str}", bar=bar, name=name, s=s, reason_str=reason_str))
            if len(items) > max_show:
                print(_("    ... y {} más", len(items) - max_show))

    _print_tier("Hot (carga automática)", "🔥", hot, 8)
    if verbose:
        print()
    _print_tier("Warm (relevantes)", "🟡", warm, 8)
    if verbose:
        print()
    _print_tier("Cold (baja relevancia)", "○", cold, 4)

    # Save results
    hot_names = [n for n, _, _ in hot]
    warm_names = [n for n, _, _ in warm]
    skills_data = {
        "relevant": hot_names + warm_names,
        "scores": {n: s for n, s, _, _, _ in scored},
        "hot": hot_names,
        "classification": {
            "features": {k: v for k, v in features.items()},
            "tiers": {
                "hot": [{"name": n, "score": s, "reasons": r} for n, s, r in hot],
                "warm": [{"name": n, "score": s, "reasons": r} for n, s, r in warm],
            },
            "last_classify": shared.ts(),
        },
    }
    _write_skills_json(slug, skills_data)
    if not json_output:
        cmd_ingest(slug)

    if json_output:
        print(json.dumps({
            "slug": slug,
            "hot": hot_names,
            "warm": warm_names,
            "cold_count": len(cold),
            "features": features,
            "scores": {n: s for n, s, _, _, _ in scored},
        }, ensure_ascii=False))
        return 0

    print()
    print(_("  📊 Total: {} hot · {} warm · {} cold", len(hot), len(warm), len(cold)))
    return 0

# ── main ─────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Uso del sistema de absorb:")
        print(_("  {} scan [--force]", sys.argv[0]))
        print(_("  {} match <slug>", sys.argv[0]))
        print(_("  {} classify <slug>", sys.argv[0]))
        print(_("  {} ingest <slug> [--force]", sys.argv[0]))
        print(_("  {} learn <slug> <skillname> <action> [rating]", sys.argv[0]))
        print(_("  {} suggest <slug> [--all]", sys.argv[0]))
        print(_("  {} status [<slug>]", sys.argv[0]))
        print()
        print("Acciones: used, success, fail, rated_<1-5>")
        return 1

    cmd = sys.argv[1]

    if cmd == "scan":
        force = "--force" in sys.argv
        cmd_scan(force)
        return 0

    elif cmd == "match":
        if len(sys.argv) < 3:
            print("Falta el slug del proyecto")
            return 1
        data = _read_global()
        skills = data.get("skills", {})
        if not skills:
            print("  No hay skills escaneados todavía. Ejecutá 'scan' primero.")
            return 1
        cmd_match(sys.argv[2])
        return 0

    elif cmd == "classify":
        if len(sys.argv) < 3:
            print("Falta el slug del proyecto")
            return 1
        data = _read_global()
        skills = data.get("skills", {})
        if not skills:
            print("  No hay skills escaneados todavía. Ejecutá 'scan' primero.")
            return 1
        json_output = "--json" in sys.argv
        return cmd_classify(sys.argv[2], json_output)

    elif cmd == "ingest":
        if len(sys.argv) < 3:
            print("Falta el slug del proyecto")
            return 1
        rebuild = "--force" in sys.argv
        return cmd_ingest(sys.argv[2], rebuild=rebuild)

    elif cmd == "learn":
        if len(sys.argv) < 5:
            print("Faltan datos: necesito slug, skillname y acción")
            return 1
        slug = sys.argv[2]
        skillname = sys.argv[3]
        action = sys.argv[4]
        rating = int(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[5].isdigit() else None
        return cmd_learn(slug, skillname, action, rating)

    elif cmd == "suggest":
        if len(sys.argv) < 3:
            print("Falta el slug del proyecto")
            return 1
        show_all = "--all" in sys.argv
        json_output = "--json" in sys.argv
        return cmd_suggest(sys.argv[2], show_all, json_output)

    elif cmd == "status":
        json_output = "--json" in sys.argv
        args = [a for a in sys.argv[2:] if a != "--json"]
        slug = args[0] if args else None
        return cmd_status(slug, json_output)

    else:
        print(_("No conozco el comando '{cmd}'. Usá: scan, match, classify, learn, suggest o status.", cmd=cmd))
        return 1

if __name__ == "__main__":
    sys.exit(main())

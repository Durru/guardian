#!/usr/bin/env python3
"""Shared helpers for Nexxoria Guardian."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

_GUARDIAN_DATA = os.environ.get("GUARDIAN_DATA", "")
if _GUARDIAN_DATA:
    MEMORY_DIR = Path(_GUARDIAN_DATA) / "projects"
    BACKEND_DIR = Path(_GUARDIAN_DATA)
else:
    MEMORY_DIR = Path("/var/guardian/projects")
    BACKEND_DIR = Path("/var/guardian")
DEFAULT_MODE = "plan"


def project_dir(slug: str) -> Path:
    """Root directory for a project. Everything about the project lives here."""
    d = MEMORY_DIR / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "brain").mkdir(exist_ok=True)
    return d

GUARDIAN_LANG = os.environ.get("GUARDIAN_LANG", "en")

_STRINGS = {
    "en": {
        "setup_already_exists": "Config already exists for '{slug}' (created: {created})",
        "setup_stack": "Stack: {stack}",
        "setup_reconfigure": "  Reconfigure?",
        "setup_memory_needed": "  Run memory setup?",
        "setup_skip_memory": "  Memory already configured, skipping",
        "setup_docs_needed": "  Scan initial docs?",
        "setup_skip_docs": "  Docs are up to date, skipping",
        "setup_skills_needed": "  Scan and match skills?",
        "setup_skip_skills": "  Skills already current, skipping",
        "docs_up_to_date": "  All docs are up to date.",
        "docs_unchanged": "  {name} unchanged, skipping",
        "docs_generated": "  {name} generated",
        "skills_already_current": "  Skills already current for {slug} (last match: {last})",
        "snapshot_identical": "  Snapshot already exists (identical content): {file}",
        "snapshot_taken": "  Snapshot: {name}",
        "projects_empty": "  No registered projects.",
        "projects_gc_done": "  GC completed on {total} project(s){extra}",
        "projects_cleanup_done": "  Cleaned {count} test projects ({size})",
        "projects_absorb_done": "  Absorb match completed on {total} project(s){extra}",
        "projects_skipped": " ({skipped} up to date)",
        "projects_skipped_run": " ({skipped} up to date, {ran} processed)",
        "precondition_exists": "  Already exists: {msg}",
    },
    "es": {
        "setup_already_exists": "  Ya existe config para '{slug}' (creado: {created})",
        "setup_stack": "  Stack: {stack}",
        "setup_reconfigure": "  ¿Reconfigurar?",
        "setup_memory_needed": "  ¿Ejecutar memory setup?",
        "setup_skip_memory": "  Memory ya configurada, saltando",
        "setup_docs_needed": "  ¿Escanear docs iniciales?",
        "setup_skip_docs": "  Docs están al día, saltando",
        "setup_skills_needed": "  ¿Escanear y matchear skills?",
        "setup_skip_skills": "  Skills ya están al día, saltando",
        "docs_up_to_date": "  📄 Todos los docs están al día.",
        "docs_unchanged": "  • {name} sin cambios, saltando",
        "docs_generated": "  ✓ {name} generado",
        "skills_already_current": "  📦 Skills ya están al día para {slug} (último match: {last})",
        "snapshot_identical": "  📸 Snapshot ya existe (contenido idéntico): {file}",
        "snapshot_taken": "  📸 Snapshot: {name}",
        "projects_empty": "  No hay proyectos registrados.",
        "projects_gc_done": "  🧹 GC completado en {total} proyecto(s){extra}",
        "projects_cleanup_done": "  🧹 {count} proyectos de test limpiados ({size})",
        "projects_absorb_done": "  ✅ Absorb match completado en {total} proyecto(s){extra}",
        "projects_skipped": " ({skipped} sin cambios)",
        "projects_skipped_run": " ({skipped} al día, {ran} procesados)",
        "precondition_exists": "  Ya existe: {msg}",
    },
}

# Flat Spanish→English translation dict for inline strings in guardian.py, guardian_memory.py, etc.
# Keys = Spanish string template (exactly as appears in source code, no f-prefix).
# Values = natural English translation.
ES_EN_DICT = {
    # ── guardian.py ──────────────────────────────────────────────────
    "  El slug especificado no es válido.":
        "  The specified slug is not valid.",
    "  No se pudo detectar el proyecto. Especificá un slug o ejecutá 'guardian setup'.":
        "  Could not detect the project. Specify a slug or run 'guardian setup'.",
    "{prompt} [s/N] ":
        "{prompt} [y/N] ",
    "Sin sesiones":
        "No sessions",
    "  🛡️  Nexxoria Guardian — Configuración":
        "  🛡️  Nexxoria Guardian — Setup",
    "  Nombre del proyecto [{default_slug}]: ":
        "  Project name [{default_slug}]: ",
    "El slug no es válido.":
        "The slug is not valid.",
    "  Ruta del proyecto [{Path.cwd()}]: ":
        "  Project path [{Path.cwd()}]: ",
    "\n  Detectando stack...":
        "\n  Detecting stack...",
    "    Stack detectado: {stack_type} / {framework}":
        "    Stack detected: {stack_type} / {framework}",
    "  Comando de tests [{detected.get('test_cmd', '')}]: ":
        "  Test command [{detected.get('test_cmd', '')}]: ",
    "  Comando de lint [{detected.get('lint_cmd', '')}]: ":
        "  Lint command [{detected.get('lint_cmd', '')}]: ",
    "\n  ✓ Proyecto '{slug}' configurado en {MEMORY_DIR / slug / 'config.yaml'}":
        "\n  ✓ Project '{slug}' configured at {MEMORY_DIR / slug / 'config.yaml'}",
    "  ⚠ Error en scan/match: {e}":
        "  ⚠ Error in scan/match: {e}",
    "Proyecto '{slug}' configurado":
        "Project '{slug}' configured",
    "\n  ✅ Guardian listo para '{slug}'":
        "\n  ✅ Guardian ready for '{slug}'",
    "  No se detectó ningún proyecto registrado en este directorio.":
        "  No registered project detected in this directory.",
    "  Ejecutá 'guardian setup' para crear uno nuevo.":
        "  Run 'guardian setup' to create a new one.",
    "  Proyecto: {slug}":
        "  Project: {slug}",
    "  Stack: {detected} / {framework}":
        "  Stack: {detected} / {framework}",
    "  Ruta: {root}":
        "  Path: {root}",
    "  Memoria: {len(mem)} entrada(s)":
        "  Memory: {len(mem)} entry(entries)",
    "  Skills: {len(skills.get('relevant', []))} relevante(s)":
        "  Skills: {len(skills.get('relevant', []))} relevant",
    "  Auditoría: {len(audit)} entrada(s)":
        "  Audit: {len(audit)} entry(entries)",
    "Proyecto '{slug}' no encontrado.":
        "Project '{slug}' not found.",
    "  Paths protegidos: {len(protected)}":
        "  Protected paths: {len(protected)}",
    "  Reglas:      {len(rules)}":
        "  Rules:       {len(rules)}",
    "  Docs activos: {avail_str}":
        "  Active docs: {avail_str}",
    "  Último scan docs: {last_scan[:19]}":
        "  Last docs scan: {last_scan[:19]}",
    "Cambios recientes":
        "Recent changes",
    "  🧠 Memoria: {len(mem)} entrada(s) [{type_str}]":
        "  🧠 Memory: {len(mem)} entry(entries) [{type_str}]",
    "  🧠 Memoria: vacía":
        "  🧠 Memory: empty",
    "  🔥 Skills hot: {', '.join(skills['hot'][:5])}":
        "  🔥 Hot skills: {', '.join(skills['hot'][:5])}",
    "  📦 Skills: {len(skills.get('relevant', []))} relevante(s)":
        "  📦 Skills: {len(skills.get('relevant', []))} relevant",
    "🔍 Verificando: {slug}":
        "🔍 Checking: {slug}",
    "  ✓ Protegido: {p}":
        "  ✓ Protected: {p}",
    "  ⚠ No existe: {p}":
        "  ⚠ Does not exist: {p}",
    "  • Sin paths protegidos":
        "  • No protected paths",
    "  ✓ Reglas: {len(rules)} definidas":
        "  ✓ Rules: {len(rules)} defined",
    "  • Sin reglas":
        "  • No rules",
    "  ⚠ Docs desactualizados: {age} días desde último scan":
        "  ⚠ Docs outdated: {age} days since last scan",
    "  ✓ Docs: {avail_count}/4 disponibles":
        "  ✓ Docs: {avail_count}/4 available",
    "  ✓ Skills cargados: {len(skills['hot'])} hot":
        "  ✓ Skills loaded: {len(skills['hot'])} hot",
    "  ✓ Skills: {len(skills['relevant'])} relevante(s)":
        "  ✓ Skills: {len(skills['relevant'])} relevant",
    "  ⚠ Sin skills — ejecutá 'guardian absorb match {slug}'":
        "  ⚠ No skills — run 'guardian absorb match {slug}'",
    "  ⚠ {expired}/{len(mem)} entradas de memoria vencidas":
        "  ⚠ {expired}/{len(mem)} memory entries expired",
    "  ✅ Todo en orden para '{slug}'":
        "  ✅ All good for '{slug}'",
    "  ⚠ {issues} problema(s) encontrado(s)":
        "  ⚠ {issues} issue(s) found",
    "  No hay auditoría para '{slug}'.":
        "  No audit for '{slug}'.",
    "📋 Reporte: {slug}":
        "📋 Report: {slug}",
    "  Total eventos:  {total}":
        "  Total events:   {total}",
    "  ⚠ Violaciones:  {violations}":
        "  ⚠ Violations:   {violations}",
    "  ✗ Bloqueos:     {blocked}":
        "  ✗ Blocks:       {blocked}",
    "  Cambios:        {changes}":
        "  Changes:        {changes}",
    "  Snapshots:      {snapshots}":
        "  Snapshots:      {snapshots}",
    "\n  Archivos más modificados:":
        "\n  Most modified files:",
    "\n  Hooks configurados: {len(hooks_config)}":
        "\n  Configured hooks: {len(hooks_config)}",
    "\n  ✅ Reporte generado para '{slug}'":
        "\n  ✅ Report generated for '{slug}'",
    "Especificá un path para proteger.":
        "Specify a path to protect.",
    "'{path}' ya está protegido.":
        "'{path}' is already protected.",
    "Path protegido: {path}":
        "Protected path: {path}",
    "  🔒 Path protegido: {p}":
        "  🔒 Protected path: {p}",
    "     Config: {MEMORY_DIR / slug / 'config.yaml'}":
        "     Config: {MEMORY_DIR / slug / 'config.yaml'}",
    "Especificá un archivo para hacer snapshot.":
        "Specify a file to snapshot.",
    "El archivo no existe: {path}":
        "The file does not exist: {path}",
    "  📸 Snapshot: {dest.name}":
        "  📸 Snapshot: {dest.name}",
    "     Backup creado en: {dest}":
        "     Backup created at: {dest}",
    "Snapshot: {path}":
        "Snapshot: {path}",
    "  No hay cambios sin commit.":
        "  No uncommitted changes.",
    "Diff excedió el tiempo de espera.":
        "Diff timed out.",
    "  No hay git ni snapshots disponibles.":
        "  No git or snapshots available.",
    "  Snapshots disponibles ({len(snapshots)}):":
        "  Available snapshots ({len(snapshots)}):",
    "📋 Workflow: {slug}":
        "📋 Workflow: {slug}",
    "  Paso actual:     {state.get('step', '—')}":
        "  Current step:    {state.get('step', '—')}",
    "  Último scope:    {state.get('last_scope', '—')}":
        "  Last scope:      {state.get('last_scope', '—')}",
    "  Próximo paso:    {state.get('next_step', 'identify')}":
        "  Next step:       {state.get('next_step', 'identify')}",
    "  Historial:":
        "  History:",
    "Paso no válido: '{step}'. Usá: {', '.join(WORKFLOW_STEPS)}":
        "Invalid step: '{step}'. Use: {', '.join(WORKFLOW_STEPS)}",
    "No se puede saltar de '{last_step}' a '{step}'. El siguiente paso debería ser '{expected}'. Usá --force para saltar esta verificación.":
        "Cannot jump from '{last_step}' to '{step}'. The next step should be '{expected}'. Use --force to skip this check.",
    "  ⚠ Atención: estás yendo de '{last_step}' a '{step}' (retrocediendo en el workflow)":
        "  ⚠ Note: you're going from '{last_step}' to '{step}' (going backwards in the workflow)",
    "Template no encontrado: {template_file}":
        "Template not found: {template_file}",
    "No hay cambios para revertir.":
        "No changes to revert.",
    "⏪ Revertir último cambio":
        "⏪ Revert last change",
    "  ❗ Esta acción es destructiva: los cambios se perderán.":
        "  ❗ This action is destructive: changes will be lost.",
    "  Archivos:":
        "  Files:",
    "  Escribí 'revertir' para confirmar: ":
        "  Type 'revertir' to confirm: ",
    "Cancelado.":
        "Canceled.",
    "  ✅ Cambio revertido.":
        "  ✅ Change reverted.",
    "No se pudo revertir (git checkout falló).":
        "Could not revert (git checkout failed).",
    "Revertir excedió el tiempo de espera.":
        "Revert timed out.",
    "Error al revertir: {e}":
        "Error reverting: {e}",
    "🔌 Hooks: {slug}":
        "🔌 Hooks: {slug}",
    "🔄 Pre-change: {slug}":
        "🔄 Pre-change: {slug}",
    "  ¿Modificar '{p}' de todas formas?":
        "  Modify '{p}' anyway?",
    "Operación bloqueada: '{p}' está protegido.":
        "Operation blocked: '{p}' is protected.",
    "Pre-change completado":
        "Pre-change completed",
    "  ✅ Pre-change completado":
        "  ✅ Pre-change completed",
    "🔄 Post-change: {slug}":
        "🔄 Post-change: {slug}",
    "  🔬 Ejecutando tests: {test_cmd}":
        "  🔬 Running tests: {test_cmd}",
    "  ✅ Tests pasaron":
        "  ✅ Tests passed",
    "  ❌ Tests fallaron (código: {result.returncode})":
        "  ❌ Tests failed (code: {result.returncode})",
    "  ⚠ Tests excedieron tiempo límite":
        "  ⚠ Tests timed out",
    "  ⚠ Comando no encontrado: {test_cmd}":
        "  ⚠ Command not found: {test_cmd}",
    "  • Sin comando de tests configurado":
        "  • No test command configured",
    "  • Tests omitidos":
        "  • Tests skipped",
    "  🔍 Ejecutando lint: {lint_cmd}":
        "  🔍 Running lint: {lint_cmd}",
    "  ✅ Lint pasó":
        "  ✅ Lint passed",
    "  ⚠ Lint encontró problemas (código: {result.returncode})":
        "  ⚠ Lint found issues (code: {result.returncode})",
    "  ⚠ Lint excedió tiempo límite":
        "  ⚠ Lint timed out",
    "  ⚠ Comando no encontrado: {lint_cmd}":
        "  ⚠ Command not found: {lint_cmd}",
    "  • Sin comando de lint configurado":
        "  • No lint command configured",
    "  • Lint omitido":
        "  • Lint skipped",
    "Post-change: {', '.join(files) if files else 'cambios'} | issues: {issues}":
        "Post-change: {', '.join(files) if files else 'changes'} | issues: {issues}",
    "Cambio aplicado: {content[:80]}":
        "Change applied: {content[:80]}",
    "\n  ✅ Post-change completado sin issues":
        "\n  ✅ Post-change completed without issues",
    "\n  ⚠ Post-change completado con {issues} issue(s)":
        "\n  ⚠ Post-change completed with {issues} issue(s)",
    "🚀 Pre-deploy: {slug}":
        "🚀 Pre-deploy: {slug}",
    "  🔨 Build: {build_cmd}":
        "  🔨 Build: {build_cmd}",
    "  ✅ Build exitoso":
        "  ✅ Build successful",
    "  ❌ Build falló (código: {result.returncode})":
        "  ❌ Build failed (code: {result.returncode})",
    "  ❌ Build excedió tiempo límite":
        "  ❌ Build timed out",
    "  ❌ Comando no encontrado: {build_cmd}":
        "  ❌ Command not found: {build_cmd}",
    "  • Sin comando de build configurado":
        "  • No build command configured",
    "\n  ✅ Pre-deploy: listo para desplegar":
        "\n  ✅ Pre-deploy: ready to deploy",
    "\n  ❌ Pre-deploy: {issues} issue(s) - corregí antes de desplegar":
        "\n  ❌ Pre-deploy: {issues} issue(s) - fix before deploying",
    "✅ Post-deploy: {slug}":
        "✅ Post-deploy: {slug}",
    "  ⚠ Smoke test excedió tiempo límite":
        "  ⚠ Smoke test timed out",
    "  • Sin URL ni comando de deploy configurados":
        "  • No deploy URL or command configured",
    "  📄 Documentos generados ({len(generated)}):":
        "  📄 Documents generated ({len(generated)}):",
    "Docs scan: {len(generated)} archivo(s)":
        "Docs scan: {len(generated)} file(s)",
    "Especificá un path para ruteo.":
        "Specify a path for routing.",
    "  No hay rutas de docs configuradas. Ejecutá 'guardian docs scan {slug}'.":
        "  No doc routes configured. Run 'guardian docs scan {slug}'.",
    "🗺️  Ruteo de docs: {slug}":
        "🗺️  Doc routing: {slug}",
    "  Archivo:     {doc_file}":
        "  File:         {doc_file}",
    "  Estado:      {status} {'existe' if exists else 'no encontrado'}":
        "  Status:       {status} {'exists' if exists else 'not found'}",
    "  Match:       (ninguno)":
        "  Match:       (none)",
    "  No hay cambios desde la última consulta.":
        "  No changes since last query.",
    "  (contexto omitido para evitar repetición)":
        "  (context omitted to avoid repetition)",
    "📌 Contexto: {slug}":
        "📌 Context: {slug}",
    "  Reglas activas ({len(rules)}):":
        "  Active rules ({len(rules)}):",
    "  Paths protegidos ({len(protected)}):":
        "  Protected paths ({len(protected)}):",
    "  Proyecto:    {slug}":
        "  Project:     {slug}",
    "  Stack:       {detected} / {framework}":
        "  Stack:       {detected} / {framework}",
    "  Ruta:        {root}":
        "  Path:        {root}",
    "  Docs:        {', '.join(avail)}":
        "  Docs:        {', '.join(avail)}",
    "  Doc scope:   {scope_filter} → {matched}":
        "  Doc scope:   {scope_filter} → {matched}",
    "\n  Memoria relevante ({len(show_mem)}):":
        "\n  Relevant memory ({len(show_mem)}):",
    "\n  🔥 Skills: {', '.join(skills['hot'][:5])}":
        "\n  🔥 Skills: {', '.join(skills['hot'][:5])}",
    "\n  Últimos cambios:":
        "\n  Recent changes:",
    "Falta el título del PR.":
        "Missing PR title.",
    "(sin descripción)":
        "(no description)",
    "  ✅ PR creado: {url}":
        "  ✅ PR created: {url}",
    "Error al crear PR":
        "Error creating PR",
    "Creación de PR excedió el tiempo de espera.":
        "PR creation timed out.",
    "gh CLI no encontrado. Instalá GitHub CLI: https://cli.github.com/":
        "gh CLI not found. Install GitHub CLI: https://cli.github.com/",
    "Sin PRs activos.":
        "No active PRs.",
    "Status de PR excedió el tiempo de espera.":
        "PR status timed out.",
    "gh CLI no encontrado.":
        "gh CLI not found.",
    "Sin PRs.":
        "No PRs.",
    "Listado de PRs excedió el tiempo de espera.":
        "PR listing timed out.",
    "Uso: guardian pr comment <número> <cuerpo>":
        "Usage: guardian pr comment <number> <body>",
    "  ✅ Comentario agregado a PR #{number}":
        "  ✅ Comment added to PR #{number}",
    "Error al comentar":
        "Error commenting",
    "Comentario excedió el tiempo de espera.":
        "Comment timed out.",
    "Falta el número de PR.":
        "Missing PR number.",
    "  ✅ PR #{number} aprobado":
        "  ✅ PR #{number} approved",
    "Error al aprobar":
        "Error approving",
    "Approve excedió el tiempo de espera.":
        "Approve timed out.",
    "  ✅ PR #{number} mergeado":
        "  ✅ PR #{number} merged",
    "Error al mergear":
        "Error merging",
    "Merge excedió el tiempo de espera.":
        "Merge timed out.",
    "  ✅ PR #{number} checkout realizado":
        "  ✅ PR #{number} checkout done",
    "Error al checkout":
        "Error checking out",
    "Checkout excedió el tiempo de espera.":
        "Checkout timed out.",
    "Subcomando de PR no válido: '{subcmd}'. Usá: create, status, comment, approve, merge, list, checkout":
        "Invalid PR subcommand: '{subcmd}'. Use: create, status, comment, approve, merge, list, checkout",
    "Sin issues.":
        "No issues.",
    "Listado de issues excedió el tiempo de espera.":
        "Issue listing timed out.",
    "Falta el título del issue.":
        "Missing issue title.",
    "  ✅ Issue creado: {url}":
        "  ✅ Issue created: {url}",
    "Error al crear issue":
        "Error creating issue",
    "Creación de issue excedió el tiempo de espera.":
        "Issue creation timed out.",
    "Falta el número de issue.":
        "Missing issue number.",
    "  ✅ Issue #{number} cerrado":
        "  ✅ Issue #{number} closed",
    "Error al cerrar issue":
        "Error closing issue",
    "Cierre de issue excedió el tiempo de espera.":
        "Issue close timed out.",
    "Uso: guardian issue comment <número> <cuerpo>":
        "Usage: guardian issue comment <number> <body>",
    "  ✅ Comentario agregado a issue #{number}":
        "  ✅ Comment added to issue #{number}",
    "Subcomando de issue no válido: '{subcmd}'. Usá: list, create, close, comment":
        "Invalid issue subcommand: '{subcmd}'. Use: list, create, close, comment",
    "  No hay proyectos registrados.":
        "  No registered projects.",
    "📋 Proyectos":
        "📋 Projects",
    "📊 Proyectos — Estadísticas":
        "📊 Projects — Statistics",
    "  Total:       {len(projects)}":
        "  Total:       {len(projects)}",
    "  Activos:     {active}":
        "  Active:      {active}",
    "  Memoria:     {total_mem} entrada(s)":
        "  Memory:      {total_mem} entry(entries)",
    "  Skills:      {total_skills} relevante(s)":
        "  Skills:      {total_skills} relevant",
    "  Hot skills:  {total_hot}":
        "  Hot skills:  {total_hot}",
    r"(\d+) vencido":
        r"(\d+) expired",
    "  ⚠ {slug}: {e}":
        "  ⚠ {slug}: {e}",
    "  {slug}: {last_line[:80]}":
        "  {slug}: {last_line[:80]}",
    "Uso: guardian projects absorb match":
        "Usage: guardian projects absorb match",
    "Subcomando no válido: '{subcmd}'. Usá: list, status, gc, absorb":
        "Invalid subcommand: '{subcmd}'. Use: list, status, gc, absorb",
    "Uso: guardian memory <save|search|context|gc|status|index|session> [args...]":
        "Usage: guardian memory <save|search|context|gc|status|index|session> [args...]",
    "No se encontró: {MEMORY_SCRIPT}":
        "Not found: {MEMORY_SCRIPT}",
    "Error: {e}":
        "Error: {e}",
    "Uso: guardian absorb <scan|match|classify|learn|suggest|status> [args...]":
        "Usage: guardian absorb <scan|match|classify|learn|suggest|status> [args...]",
    "No se encontró: {ABSORB_SCRIPT}":
        "Not found: {ABSORB_SCRIPT}",
    "No hay comando configurado para '{action}'. Usá 'guardian setup' para configurarlo.":
        "No command configured for '{action}'. Use 'guardian setup' to configure it.",
    "  ⚡ {cmd}":
        "  ⚡ {cmd}",
    "  ✓ {action} completado":
        "  ✓ {action} completed",
    "  ❌ {action} falló (código: {result.returncode})":
        "  ❌ {action} failed (code: {result.returncode})",
    "{action} excedió el tiempo de espera":
        "{action} timed out",
    "Error al ejecutar {action}: {e}":
        "Error running {action}: {e}",
    "Uso: guardian <comando> [args...]":
        "Usage: guardian <command> [args...]",
    "  detect                       Detectar proyecto actual":
        "  detect                       Detect current project",
    "  status [slug]                Dashboard del proyecto":
        "  status [slug]                Project dashboard",
    "  check [slug]                 Verificar reglas y paths protegidos":
        "  check [slug]                 Verify rules and protected paths",
    "  report [slug]                Violaciones, tendencias, cumplimiento":
        "  report [slug]                Violations, trends, compliance",
    "  setup [slug]                 Configurar proyecto":
        "  setup [slug]                 Configure project",
    "  protect <path> [slug]        Proteger un path":
        "  protect <path> [slug]        Protect a path",
    "  snapshot <path> [slug]       Backup de archivo":
        "  snapshot <path> [slug]       Backup a file",
    "  diff [path] [slug]           Mostrar diff (git o snapshot)":
        "  diff [path] [slug]           Show diff (git or snapshot)",
    "  rollback [slug]              Revertir último cambio":
        "  rollback [slug]              Revert last change",
    "  hooks [slug]                 Estado de hooks":
        "  hooks [slug]                 Hook status",
    "  context [opts] [slug]        Contexto del proyecto para AI":
        "  context [opts] [slug]        Project context for AI",
    "  docs scan [slug]             Generar docs desde templates":
        "  docs scan [slug]             Generate docs from templates",
    "  docs route <path> [slug]     Ver qué doc se sirve para un path":
        "  docs route <path> [slug]     See which doc serves a path",
    "  pr <sub> [args]              GitHub PR integration":
        "  pr <sub> [args]              GitHub PR integration",
    "  issue <sub> [args]           GitHub Issues integration":
        "  issue <sub> [args]           GitHub Issues integration",
    "  projects <sub> [args]        Gestión multi-proyecto":
        "  projects <sub> [args]        Multi-project management",
    "Uso: guardian protect <path> [slug]":
        "Usage: guardian protect <path> [slug]",
    "Uso: guardian snapshot <path> [slug]":
        "Usage: guardian snapshot <path> [slug]",
    "Uso: guardian docs <scan|route> [args...]":
        "Usage: guardian docs <scan|route> [args...]",
    "Uso: guardian docs route <path> [slug]":
        "Usage: guardian docs route <path> [slug]",
    "Subcomando docs no válido: '{sub}'. Usá: scan, route":
        "Invalid docs subcommand: '{sub}'. Use: scan, route",
    "Uso: guardian prompt <paso> [--scope=...] [--type=...] [--files=...] [slug]":
        "Usage: guardian prompt <step> [--scope=...] [--type=...] [--files=...] [slug]",
    "Uso: guardian pr <create|status|comment|approve|merge|list|checkout> [args]":
        "Usage: guardian pr <create|status|comment|approve|merge|list|checkout> [args]",
    "Uso: guardian issue <list|create|close|comment> [args]":
        "Usage: guardian issue <list|create|close|comment> [args]",
    "Uso: guardian projects <list|status|gc|absorb> [args]":
        "Usage: guardian projects <list|status|gc|absorb> [args]",
    "Comando desconocido: '{cmd}'. Ejecutá 'guardian' sin argumentos para ver la ayuda.":
        "Unknown command: '{cmd}'. Run 'guardian' without arguments to see help.",

    # ── guardian_absorb.py ──────────────────────────────────────────
    "{changes['new']} nuevo(s)":
        "{changes['new']} new",
    "{changes['updated']} actualizado(s)":
        "{changes['updated']} updated",
    "{changes['removed']} eliminado(s)":
        "{changes['removed']} removed",
    "  📦 Skills: {', '.join(parts)}":
        "  📦 Skills: {', '.join(parts)}",
    "  📦 {len(relevant)} skills relevantes para {slug}":
        "  📦 {len(relevant)} relevant skills for {slug}",
    "  🔥 Hot — carga automática: {', '.join(hot[:5])}":
        "  🔥 Hot — auto-load: {', '.join(hot[:5])}",
    "  🟡 Warm — disponibles: {', '.join(warm[:5])}":
        "  🟡 Warm — available: {', '.join(warm[:5])}",
    "  Mejores 5 por relevancia:":
        "  Top 5 by relevance:",
    "lo usaste":
        "used it",
    "funcionó bien":
        "worked well",
    "no funcionó":
        "didn't work",
    "  📈 {skillname}: {action_label} (x{hits})":
        "  📈 {skillname}: {action_label} (x{hits})",
    "  Todavía no hay skills matcheados. Primero ejecutá: guardian_absorb.py match <slug>":
        "  No skills matched yet. First run: guardian_absorb.py match <slug>",
    "  📚 Skills recomendados para {slug}":
        "  📚 Recommended skills for {slug}",
    "  {len(hot)} skill(s) en hot list — se cargan solos en cada sesión":
        "  {len(hot)} skill(s) in hot list — auto-load every session",
    "  📦 Skills catalogados: {total}   (último escaneo: {last})":
        "  📦 Skills cataloged: {total}   (last scan: {last})",
    "  Proyecto {slug}: {len(rel)} relevantes, {len(hot)} hot":
        "  Project {slug}: {len(rel)} relevant, {len(hot)} hot",
    "  ❌ Proyecto '{slug}' no encontrado.":
        "  ❌ Project '{slug}' not found.",
    "  ❌ Project root no encontrado: {root}":
        "  ❌ Project root not found: {root}",
    "  No hay skills escaneados. Ejecutá 'guardian absorb scan' primero.":
        "  No skills scanned. Run 'guardian absorb scan' first.",
    "  🔬 Clasificando skills para {slug}...":
        "  🔬 Classifying skills for {slug}...",
    "  📁 Analizando: {root}":
        "  📁 Analyzing: {root}",
    "(ninguno)":
        "(none)",
    "     Lenguajes: {lang_s}":
        "     Languages: {lang_s}",
    "     Frameworks: {fw_s}":
        "     Frameworks: {fw_s}",
    "     Herramientas: {tools_s}":
        "     Tools: {tools_s}",
    "  {icon} {title}: (ninguno)":
        "  {icon} {title}: (none)",
    "  {icon} {title}:":
        "  {icon} {title}:",
    "    ... y {len(items) - max_show} más":
        "    ... and {len(items) - max_show} more",
    "Hot (carga automática)":
        "Hot (auto-load)",
    "Warm (relevantes)":
        "Warm (relevant)",
    "Cold (baja relevancia)":
        "Cold (low relevance)",
    "  📊 Total: {len(hot)} hot · {len(warm)} warm · {len(cold)} cold":
        "  📊 Total: {len(hot)} hot · {len(warm)} warm · {len(cold)} cold",
    "Uso del sistema de absorb:":
        "Absorb system usage:",
    "Falta el slug del proyecto":
        "Missing project slug",
    "  No hay skills escaneados todavía. Ejecutá 'scan' primero.":
        "  No skills scanned yet. Run 'scan' first.",
    "Faltan datos: necesito slug, skillname y acción":
        "Missing data: need slug, skillname and action",
    "No conozco el comando '{cmd}'. Usá: scan, match, classify, learn, suggest o status.":
        "Unknown command '{cmd}'. Use: scan, match, classify, learn, suggest or status.",

    # ── guardian_memory.py ──────────────────────────────────────────
    "Faltan datos: necesito el slug, el tipo y el contenido":
        "Missing data: need slug, type and content",
    "El tipo '{type_}' no es válido. Usá uno de: {', '.join(sorted(valid_types))}":
        "Type '{type_}' is not valid. Use one of: {', '.join(sorted(valid_types))}",
    "Actualizado":
        "Updated",
    "  🧠 {action}: {type_}":
        "  🧠 {action}: {type_}",
    "  La memoria está vacía":
        "  Memory is empty",
    "  🧬 Índice semántico: {len(cached)} entrada(s) indexada(s) (usá --force para reindexar)":
        "  🧬 Semantic index: {len(cached)} entry(entries) indexed (use --force to reindex)",
    "  🧬 Índice semántico: {len(embeddings)}/{len(entries)} entrada(s) indexada(s) (TF-IDF, zero deps)":
        "  🧬 Semantic index: {len(embeddings)}/{len(entries)} entry(entries) indexed (TF-IDF, zero deps)",
    "Faltan datos: necesito el slug y el término de búsqueda":
        "Missing data: need slug and search term",
    "  No hay nada guardado en la memoria todavía":
        "  Nothing saved in memory yet",
    "  No encontré nada semánticamente similar (threshold > 0.10)":
        "  No semantically similar results found (threshold > 0.10)",
    "  🔍 Búsqueda semántica: \"{query}\"":
        "  🔍 Semantic search: \"{query}\"",
    "          archivo: {e['file']}":
        "          file: {e['file']}",
    "  No encontré nada con ese término":
        "  Nothing found with that term",
    "  La memoria está vacía, no hay nada que limpiar":
        "  Memory is empty, nothing to clean",
    "  🧹 Memoria limpiada: {len(alive)} vigentes, {removed} vencido(s) eliminado(s)":
        "  🧹 Memory cleaned: {len(alive)} valid, {removed} expired removed",
    "  🧠 La memoria está vacía":
        "  🧠 Memory is empty",
    "  🧠 Memoria: {total} entrada(s) ({expired} vencida(s))":
        "  🧠 Memory: {total} entry(entries) ({expired} expired)",
    "(carga automática)":
        "(auto-load)",
    "(según contexto)":
        "(context-based)",
    "(bajo demanda)":
        "(on demand)",
    "  🟢 Sesión guardada (#{session_count + 1})":
        "  🟢 Session saved (#{session_count + 1})",
    "  📭 Sin sesiones registradas":
        "  📭 No registered sessions",
    "  🟢 Sesiones: {total} total · {active_sessions} activas (7d)":
        "  🟢 Sessions: {total} total · {active_sessions} active (7d)",
    "  🕐 Última: {hours_ago}h atrás":
        "  🕐 Last: {hours_ago}h ago",
    "Sistema de memoria — cómo usarlo:":
        "Memory system — how to use it:",
    "  {sys.argv[0]} save <slug> <tipo> <contenido> [archivo] [línea] [scope] [ttl]":
        "  {sys.argv[0]} save <slug> <type> <content> [file] [line] [scope] [ttl]",
    "  {sys.argv[0]} search [--semantic] <slug> <término> [filtro_tipo]":
        "  {sys.argv[0]} search [--semantic] <slug> <term> [type_filter]",
    "  {sys.argv[0]} context <slug> [filtro_scope]":
        "  {sys.argv[0]} context <slug> [scope_filter]",
    "  {sys.argv[0]} index <slug> [--force]":
        "  {sys.argv[0]} index <slug> [--force]",
    "  {sys.argv[0]} session save <slug> [--with-config]":
        "  {sys.argv[0]} session save <slug> [--with-config]",
    "  {sys.argv[0]} session status <slug>":
        "  {sys.argv[0]} session status <slug>",
    "  {sys.argv[0]} gc <slug>":
        "  {sys.argv[0]} gc <slug>",
    "  {sys.argv[0]} status <slug>":
        "  {sys.argv[0]} status <slug>",
    "Faltan datos: necesito subcomando (save|status) y slug":
        "Missing data: need subcommand (save|status) and slug",
    "No conozco el subcomando 'session {sub}'. Usá 'save' o 'status'.":
        "Unknown session subcommand '{sub}'. Use 'save' or 'status'.",
    "No conozco el comando '{cmd}'. Usá 'status', 'save', 'search', 'context', 'session', 'index' o 'gc'.":
        "Unknown command '{cmd}'. Use 'status', 'save', 'search', 'context', 'session', 'index' or 'gc'.",

    # ── guardian_web.py (HTML templates) ───────────────────────────
    "<h2>Configuración</h2>":
        "<h2>Configuration</h2>",
    "<h2>Auditoría (últimos {len(audit)})</h2>":
        "<h2>Audit (last {len(audit)})</h2>",
    "<tr><th>Timestamp</th><th>Tipo</th><th>Estado</th><th>Descripción</th></tr>":
        "<tr><th>Timestamp</th><th>Type</th><th>Status</th><th>Description</th></tr>",
    "<h2>Memoria (últimos {len(memory)})</h2>":
        "<h2>Memory (last {len(memory)})</h2>",
    "<tr><th>Timestamp</th><th>Tipo</th><th>Scope</th><th>Contenido</th></tr>":
        "<tr><th>Timestamp</th><th>Type</th><th>Scope</th><th>Content</th></tr>",
}


_EN_OVERRIDES = {
    '\n  Archivos más modificados:': '\n  Most modified files:',
    '\n  Detectando stack...': '\n  Detecting stack...',
    '\n  Hooks configurados: {len(hooks_config)}': '\n  Hooks configured: {len(hooks_config)}',
    '\n  Memoria relevante ({len(show_mem)}):': '\n  Relevant memory ({len(show_mem)}):',
    '\n  Últimos cambios:': '\n  Recent changes:',
    '\n  ⚠ Post-change completado con {issues} issue(s)': '\n  ⚠ Post-change completed with {issues} issue(s)',
    "\n  ✅ Guardian listo para '{slug}'": "\n  ✅ Guardian ready for '{slug}'",
    '\n  ✅ Post-change completado sin issues': '\n  ✅ Post-change completed with no issues',
    '\n  ✅ Pre-deploy: listo para desplegar': '\n  ✅ Pre-deploy: ready to deploy',
    "\n  ✅ Reporte generado para '{slug}'": "\n  ✅ Report generated for '{slug}'",
    "\n  ✓ Proyecto '{slug}' configurado en {MEMORY_DIR / slug / 'config.yaml'}": "\n  ✓ Project '{slug}' configured at {MEMORY_DIR / slug / 'config.yaml'}",
    '\n  ❌ Pre-deploy: {issues} issue(s) - corregí antes de desplegar': '\n  ❌ Pre-deploy: {issues} issue(s) - fix before deploying',
    "\n  🔥 Skills: {', '.join(skills['hot'][:5])}": "\n  🔥 Skills: {', '.join(skills['hot'][:5])}",
    "          archivo: {e['file']}": "          file: {e['file']}",
    '     Backup creado en: {dest}': '     Backup created at: {dest}',
    "     Config: {MEMORY_DIR / slug / 'config.yaml'}": "     Config: {MEMORY_DIR / slug / 'config.yaml'}",
    '     Frameworks: {fw_s}': '     Frameworks: {fw_s}',
    '     Herramientas: {tools_s}': '     Tools: {tools_s}',
    '     Lenguajes: {lang_s}': '     Languages: {lang_s}',
    '    ... y {len(items) - max_show} más': '    ... and {len(items) - max_show} more',
    '    Stack detectado: {stack_type} / {framework}': '    Stack detected: {stack_type} / {framework}',
    '  (contexto omitido para evitar repetición)': '  (context omitted to avoid repetition)',
    '  Activos:     {active}': '  Active:      {active}',
    '  Archivo:     {doc_file}': '  File:        {doc_file}',
    '  Archivos:': '  Files:',
    '  Auditoría: {len(audit)} entrada(s)': '  Audit: {len(audit)} entr(ies)',
    '  Cambios:        {changes}': '  Changes:       {changes}',
    "  Comando de lint [{detected.get('lint_cmd', '')}]: ": "  Lint command [{detected.get('lint_cmd', '')}]: ",
    "  Comando de tests [{detected.get('test_cmd', '')}]: ": "  Test command [{detected.get('test_cmd', '')}]: ",
    '  Doc scope:   {scope_filter} → {matched}': '  Doc scope:   {scope_filter} → {matched}',
    '  Docs activos: {avail_str}': '  Active docs: {avail_str}',
    "  Docs:        {', '.join(avail)}": "  Docs:        {', '.join(avail)}",
    "  Ejecutá 'guardian setup' para crear uno nuevo.": "  Run 'guardian setup' to create a new one.",
    '  El slug especificado no es válido.': '  The specified slug is not valid.',
    "  Escribí 'revertir' para confirmar: ": "  Type 'revert' to confirm: ",
    "  Estado:      {status} {'existe' if exists else 'no encontrado'}": "  Status:      {status} {'exists' if exists else 'not found'}",
    '  Historial:': '  History:',
    '  Hot skills:  {total_hot}': '  Hot skills:  {total_hot}',
    '  La memoria está vacía': '  Memory is empty',
    '  La memoria está vacía, no hay nada que limpiar': '  Memory is empty, nothing to clean',
    '  Match:       (ninguno)': '  Match:       (none)',
    '  Mejores 5 por relevancia:': '  Top 5 by relevance:',
    '  Memoria:     {total_mem} entrada(s)': '  Memory:      {total_mem} entr(ies)',
    '  Memoria: {len(mem)} entrada(s)': '  Memory: {len(mem)} entr(ies)',
    '  No encontré nada con ese término': '  Nothing found with that term',
    '  No encontré nada semánticamente similar (threshold > 0.10)': '  Nothing semantically similar found (threshold > 0.10)',
    "  No hay auditoría para '{slug}'.": "  No audit log for '{slug}'.",
    '  No hay cambios desde la última consulta.': '  No changes since last query.',
    '  No hay cambios sin commit.': '  No uncommitted changes.',
    '  No hay git ni snapshots disponibles.': '  No git or snapshots available.',
    '  No hay nada guardado en la memoria todavía': '  Nothing saved in memory yet',
    '  No hay proyectos registrados.': '  No registered projects.',
    "  No hay rutas de docs configuradas. Ejecutá 'guardian docs scan {slug}'.": "  No doc routes configured. Run 'guardian docs scan {slug}'.",
    "  No hay skills escaneados todavía. Ejecutá 'scan' primero.": "  No skills scanned yet. Run 'scan' first.",
    "  No hay skills escaneados. Ejecutá 'guardian absorb scan' primero.": "  No scanned skills. Run 'guardian absorb scan' first.",
    '  No se detectó ningún proyecto registrado en este directorio.': '  No registered project detected in this directory.',
    "  No se pudo detectar el proyecto. Especificá un slug o ejecutá 'guardian setup'.": "  Could not detect project. Specify a slug or run 'guardian setup'.",
    '  Nombre del proyecto [{default_slug}]: ': '  Project name [{default_slug}]: ',
    "  Paso actual:     {state.get('step', '—')}": "  Current step:   {state.get('step', '—')}",
    '  Paths protegidos ({len(protected)}):': '  Protected paths ({len(protected)}):',
    '  Paths protegidos: {len(protected)}': '  Protected paths: {len(protected)}',
    '  Proyecto {slug}: {len(rel)} relevantes, {len(hot)} hot': '  Project {slug}: {len(rel)} relevant, {len(hot)} hot',
    '  Proyecto:    {slug}': '  Project:     {slug}',
    '  Proyecto: {slug}': '  Project: {slug}',
    "  Próximo paso:    {state.get('next_step', 'identify')}": "  Next step:      {state.get('next_step', 'identify')}",
    '  Reglas activas ({len(rules)}):': '  Active rules ({len(rules)}):',
    '  Reglas:      {len(rules)}': '  Rules:       {len(rules)}',
    '  Ruta del proyecto [{Path.cwd()}]: ': '  Project path [{Path.cwd()}]: ',
    '  Ruta:        {root}': '  Path:        {root}',
    '  Ruta: {root}': '  Path: {root}',
    '  Skills:      {total_skills} relevante(s)': '  Skills:      {total_skills} relevant',
    "  Skills: {len(skills.get('relevant', []))} relevante(s)": "  Skills: {len(skills.get('relevant', []))} relevant",
    '  Snapshots disponibles ({len(snapshots)}):': '  Available snapshots ({len(snapshots)}):',
    '  Snapshots:      {snapshots}': '  Snapshots:      {snapshots}',
    '  Stack:       {detected} / {framework}': '  Stack:       {detected} / {framework}',
    '  Stack: {detected} / {framework}': '  Stack: {detected} / {framework}',
    '  Todavía no hay skills matcheados. Primero ejecutá: guardian_absorb.py match <slug>': '  No matched skills yet. First run: guardian_absorb.py match <slug>',
    '  Total eventos:  {total}': '  Total events:   {total}',
    '  Total:       {len(projects)}': '  Total:       {len(projects)}',
    '  check [slug]                 Verificar reglas y paths protegidos': '  check [slug]                 Verify rules & protected paths',
    '  context [opts] [slug]        Contexto del proyecto para AI': '  context [opts] [slug]        Project context for AI',
    '  detect                       Detectar proyecto actual': '  detect                       Detect current project',
    '  diff [path] [slug]           Mostrar diff (git o snapshot)': '  diff [path] [slug]           Show diff (git or snapshot)',
    '  docs route <path> [slug]     Ver qué doc se sirve para un path': '  docs route <path> [slug]     Check doc for a path',
    '  docs scan [slug]             Generar docs desde templates': '  docs scan [slug]             Generate docs from templates',
    '  hooks [slug]                 Estado de hooks': '  hooks [slug]                 Hook status',
    '  issue <sub> [args]           GitHub Issues integration': '  issue <sub> [args]           GitHub Issues integration',
    '  pr <sub> [args]              GitHub PR integration': '  pr <sub> [args]              GitHub PR integration',
    '  projects <sub> [args]        Gestión multi-proyecto': '  projects <sub> [args]        Multi-project management',
    '  protect <path> [slug]        Proteger un path': '  protect <path> [slug]        Protect a path',
    '  report [slug]                Violaciones, tendencias, cumplimiento': '  report [slug]                Violations, trends, compliance',
    '  rollback [slug]              Revertir último cambio': '  rollback [slug]              Revert last change',
    '  setup [slug]                 Configurar proyecto': '  setup [slug]                 Configure project',
    '  snapshot <path> [slug]       Backup de archivo': '  snapshot <path> [slug]       Backup a file',
    '  status [slug]                Dashboard del proyecto': '  status [slug]                Project dashboard',
    '  {icon} {title}:': '  {icon} {title}:',
    '  {icon} {title}: (ninguno)': '  {icon} {title}: (none)',
    '  {len(hot)} skill(s) en hot list — se cargan solos en cada sesión': '  {len(hot)} skill(s) in hot list — auto-loaded each session',
    '  {slug}: {last_line[:80]}': '  {slug}: {last_line[:80]}',
    '  {sys.argv[0]} context <slug> [filtro_scope]': '  {sys.argv[0]} context <slug> [scope_filter]',
    '  {sys.argv[0]} gc <slug>': '  {sys.argv[0]} gc <slug>',
    '  {sys.argv[0]} index <slug> [--force]': '  {sys.argv[0]} index <slug> [--force]',
    '  {sys.argv[0]} save <slug> <tipo> <contenido> [archivo] [línea] [scope] [ttl]': '  {sys.argv[0]} save <slug> <type> <content> [file] [line] [scope] [ttl]',
    '  {sys.argv[0]} search [--semantic] <slug> <término> [filtro_tipo]': '  {sys.argv[0]} search [--semantic] <slug> <term> [type_filter]',
    '  {sys.argv[0]} session save <slug> [--with-config]': '  {sys.argv[0]} session save <slug> [--with-config]',
    '  {sys.argv[0]} session status <slug>': '  {sys.argv[0]} session status <slug>',
    '  {sys.argv[0]} status <slug>': '  {sys.argv[0]} status <slug>',
    "  ¿Modificar '{p}' de todas formas?": "  Modify '{p}' anyway?",
    '  Último scan docs: {last_scan[:19]}': '  Last docs scan: {last_scan[:19]}',
    "  Último scope:    {state.get('last_scope', '—')}": "  Last scope:     {state.get('last_scope', '—')}",
    '  • Lint omitido': '  • Lint skipped',
    '  • Sin URL ni comando de deploy configurados': '  • No URL or deploy command configured',
    '  • Sin comando de build configurado': '  • No build command configured',
    '  • Sin comando de lint configurado': '  • No lint command configured',
    '  • Sin comando de tests configurado': '  • No test command configured',
    '  • Sin paths protegidos': '  • No protected paths',
    '  • Sin reglas': '  • No rules',
    '  • Tests omitidos': '  • Tests skipped',
    "  ⚠ Atención: estás yendo de '{last_step}' a '{step}' (retrocediendo en el workflow)": "  ⚠ Note: you're going from '{last_step}' to '{step}' (moving backwards in workflow)",
    '  ⚠ Comando no encontrado: {deploy_cmd}': '  ⚠ Command not found: {deploy_cmd}',
    '  ⚠ Comando no encontrado: {lint_cmd}': '  ⚠ Command not found: {lint_cmd}',
    '  ⚠ Comando no encontrado: {test_cmd}': '  ⚠ Command not found: {test_cmd}',
    '  ⚠ Docs desactualizados: {age} días desde último scan': '  ⚠ Docs outdated: {age} days since last scan',
    '  ⚠ Error en scan/match: {e}': '  ⚠ Error in scan/match: {e}',
    '  ⚠ Lint encontró problemas (código: {result.returncode})': '  ⚠ Lint found issues (code: {result.returncode})',
    '  ⚠ Lint excedió tiempo límite': '  ⚠ Lint timed out',
    '  ⚠ No existe: {f}': '  ⚠ Does not exist: {f}',
    '  ⚠ No existe: {p}': '  ⚠ Does not exist: {p}',
    "  ⚠ Sin skills — ejecutá 'guardian absorb match {slug}'": "  ⚠ No skills — run 'guardian absorb match {slug}'",
    '  ⚠ Smoke test excedió tiempo límite': '  ⚠ Smoke test timed out',
    '  ⚠ Tests excedieron tiempo límite': '  ⚠ Tests timed out',
    '  ⚠ Violaciones:  {violations}': '  ⚠ Violations:  {violations}',
    '  ⚠ {expired}/{len(mem)} entradas de memoria vencidas': '  ⚠ {expired}/{len(mem)} memory entries expired',
    '  ⚠ {issues} problema(s) encontrado(s)': '  ⚠ {issues} issue(s) found',
    '  ⚠ {slug}: {e}': '  ⚠ {slug}: {e}',
    '  ⚡ {cmd}': '  ⚡ {cmd}',
    '  ✅ Build exitoso': '  ✅ Build successful',
    '  ✅ Cambio revertido.': '  ✅ Change reverted.',
    '  ✅ Comentario agregado a PR #{number}': '  ✅ Comment added to PR #{number}',
    '  ✅ Comentario agregado a issue #{number}': '  ✅ Comment added to issue #{number}',
    '  ✅ Issue #{number} cerrado': '  ✅ Issue #{number} closed',
    '  ✅ Issue creado: {url}': '  ✅ Issue created: {url}',
    '  ✅ Lint pasó': '  ✅ Lint passed',
    '  ✅ PR #{number} aprobado': '  ✅ PR #{number} approved',
    '  ✅ PR #{number} checkout realizado': '  ✅ PR #{number} checked out',
    '  ✅ PR #{number} mergeado': '  ✅ PR #{number} merged',
    '  ✅ PR creado: {url}': '  ✅ PR created: {url}',
    '  ✅ Pre-change completado': '  ✅ Pre-change completed',
    '  ✅ Tests pasaron': '  ✅ Tests passed',
    "  ✅ Todo en orden para '{slug}'": "  ✅ All good for '{slug}'",
    '  ✓ Docs: {avail_count}/4 disponibles': '  ✓ Docs: {avail_count}/4 available',
    '  ✓ Protegido: {p}': '  ✓ Protected: {p}',
    '  ✓ Reglas: {len(rules)} definidas': '  ✓ Rules: {len(rules)} defined',
    "  ✓ Skills cargados: {len(skills['hot'])} hot": "  ✓ Skills loaded: {len(skills['hot'])} hot",
    "  ✓ Skills: {len(skills.get('relevant', []))} relevante(s)": "  ✓ Skills: {len(skills.get('relevant', []))} relevant",
    '  ✓ {action} completado': '  ✓ {action} completed',
    '  ✗ Bloqueos:     {blocked}': '  ✗ Blocks:       {blocked}',
    '  ❌ Build excedió tiempo límite': '  ❌ Build timed out',
    '  ❌ Build falló (código: {result.returncode})': '  ❌ Build failed (code: {result.returncode})',
    '  ❌ Comando no encontrado: {build_cmd}': '  ❌ Command not found: {build_cmd}',
    '  ❌ Project root no encontrado: {root}': '  ❌ Project root not found: {root}',
    "  ❌ Proyecto '{slug}' no encontrado.": "  ❌ Project '{slug}' not found.",
    '  ❌ Tests fallaron (código: {result.returncode})': '  ❌ Tests failed (code: {result.returncode})',
    '  ❌ {action} falló (código: {result.returncode})': '  ❌ {action} failed (code: {result.returncode})',
    '  ❗ Esta acción es destructiva: los cambios se perderán.': '  ❗ This action is destructive: changes will be lost.',
    '  📁 Analizando: {root}': '  📁 Analyzing: {root}',
    '  📄 Documentos generados ({len(generated)}):': '  📄 Documents generated ({len(generated)}):',
    '  📈 {skillname}: {action_label} (x{hits})': '  📈 {skillname}: {action_label} (x{hits})',
    '  📊 Total: {len(hot)} hot · {len(warm)} warm · {len(cold)} cold': '  📊 Total: {len(hot)} hot · {len(warm)} warm · {len(cold)} cold',
    '  📚 Skills recomendados para {slug}': '  📚 Recommended skills for {slug}',
    '  📦 Skills catalogados: {total}   (último escaneo: {last})': '  📦 Skills cataloged: {total}   (last scan: {last})',
    "  📦 Skills: {', '.join(parts)}": "  📦 Skills: {', '.join(parts)}",
    "  📦 Skills: {len(skills.get('relevant', []))} relevante(s)": "  📦 Skills: {len(skills.get('relevant', []))} relevant",
    '  📦 {len(relevant)} skills relevantes para {slug}': '  📦 {len(relevant)} skills relevant for {slug}',
    '  📭 Sin sesiones registradas': '  📭 No sessions recorded',
    '  📸 Snapshot: {dest.name}': '  📸 Snapshot: {dest.name}',
    '  🔍 Búsqueda semántica: "{query}"': '  🔍 Semantic search: "{query}"',
    '  🔍 Ejecutando lint: {lint_cmd}': '  🔍 Running lint: {lint_cmd}',
    '  🔒 Path protegido: {path}': '  🔒 Protected path: {path}',
    "  🔥 Hot — carga automática: {', '.join(hot[:5])}": "  🔥 Hot — auto-loaded: {', '.join(hot[:5])}",
    "  🔥 Skills hot: {', '.join(skills['hot'][:5])}": "  🔥 Hot skills: {', '.join(skills['hot'][:5])}",
    '  🔨 Build: {build_cmd}': '  🔨 Build: {build_cmd}',
    '  🔬 Clasificando skills para {slug}...': '  🔬 Classifying skills for {slug}...',
    '  🔬 Ejecutando tests: {test_cmd}': '  🔬 Running tests: {test_cmd}',
    '  🕐 Última: {hours_ago}h atrás': '  🕐 Last: {hours_ago}h ago',
    '  🛡️  Nexxoria Guardian — Configuración': '  🛡️  Nexxoria Guardian — Setup',
    "  🟡 Warm — disponibles: {', '.join(warm[:5])}": "  🟡 Warm — available: {', '.join(warm[:5])}",
    '  🟢 Sesiones: {total} total · {active_sessions} activas (7d)': '  🟢 Sessions: {total} total · {active_sessions} active (7d)',
    '  🟢 Sesión guardada (#{session_count + 1})': '  🟢 Session saved (#{session_count + 1})',
    '  🧠 La memoria está vacía': '  🧠 Memory is empty',
    '  🧠 Memoria: vacía': '  🧠 Memory: empty',
    '  🧠 Memoria: {len(mem)} entrada(s) [{type_str}]': '  🧠 Memory: {len(mem)} entry(ies) [{type_str}]',
    '  🧠 Memoria: {total} entrada(s) ({expired} vencida(s))': '  🧠 Memory: {total} entr(ies) ({expired} expired)',
    '  🧠 {action}: {type_}': '  🧠 {action}: {type_}',
    '  🧬 Índice semántico: {len(cached)} entrada(s) indexada(s) (usá --force para reindexar)': '  🧬 Semantic index: {len(cached)} entr(ies) indexed (use --force to reindex)',
    '  🧬 Índice semántico: {len(embeddings)}/{len(entries)} entrada(s) indexada(s) (TF-IDF, zero deps)': '  🧬 Semantic index: {len(embeddings)}/{len(entries)} entr(ies) indexed (TF-IDF, zero deps)',
    '  🧹 Memoria limpiada: {len(alive)} vigentes, {removed} vencido(s) eliminado(s)': '  🧹 Memory cleaned: {len(alive)} active, {removed} expired removed',
    "'{path}' ya está protegido.": "'{path}' is already protected.",
    '(\\d+) vencido': '(\\d+) expired',
    '(bajo demanda)': '(on demand)',
    '(carga automática)': '(auto-loaded)',
    '(ninguno)': '(none)',
    '(según contexto)': '(context-based)',
    '(sin descripción)': '(no description)',
    '<h2>Auditoría (últimos {len(audit)})</h2>': '<h2>Audit (last {len(audit)})</h2>',
    '<h2>Configuración</h2>': '<h2>Configuration</h2>',
    '<h2>Memoria (últimos {len(memory)})</h2>': '<h2>Memory (last {len(memory)})</h2>',
    '<tr><th>Timestamp</th><th>Tipo</th><th>Estado</th><th>Descripción</th></tr>': '<tr><th>Timestamp</th><th>Type</th><th>Status</th><th>Description</th></tr>',
    '<tr><th>Timestamp</th><th>Tipo</th><th>Scope</th><th>Contenido</th></tr>': '<tr><th>Timestamp</th><th>Type</th><th>Scope</th><th>Content</th></tr>',
    'Actualizado': 'Updated',
    'Approve excedió el tiempo de espera.': 'Approve timed out.',
    'Cambio aplicado: {content[:80]}': 'Change applied: {content[:80]}',
    'Cambios recientes': 'Recent changes',
    'Cancelado.': 'Canceled.',
    'Checkout excedió el tiempo de espera.': 'Checkout timed out.',
    'Cierre de issue excedió el tiempo de espera.': 'Issue close timed out.',
    'Cold (baja relevancia)': 'Cold (low relevance)',
    "Comando desconocido: '{cmd}'. Ejecutá 'guardian' sin argumentos para ver la ayuda.": "Unknown command: '{cmd}'. Run 'guardian' without arguments for help.",
    'Comentario excedió el tiempo de espera.': 'Comment timed out.',
    'Creación de PR excedió el tiempo de espera.': 'PR creation timed out.',
    'Creación de issue excedió el tiempo de espera.': 'Issue creation timed out.',
    'Diff excedió el tiempo de espera.': 'Diff timed out.',
    'Docs scan: {len(generated)} archivo(s)': 'Docs scan: {len(generated)} file(s)',
    'El archivo no existe: {path}': 'File does not exist: {path}',
    'El slug no es válido.': 'The slug is not valid.',
    "El tipo '{type_}' no es válido. Usá uno de: {', '.join(sorted(valid_types))}": "Type '{type_}' is not valid. Use one of: {', '.join(sorted(valid_types))}",
    'Error al aprobar': 'Error approving',
    'Error al cerrar issue': 'Error closing issue',
    'Error al checkout': 'Error during checkout',
    'Error al comentar': 'Error commenting',
    'Error al crear PR': 'Error creating PR',
    'Error al crear issue': 'Error creating issue',
    'Error al ejecutar {action}: {e}': 'Error running {action}: {e}',
    'Error al mergear': 'Error merging',
    'Error al revertir: {e}': 'Error reverting: {e}',
    'Error: {e}': 'Error: {e}',
    'Especificá un archivo para hacer snapshot.': 'Specify a file to snapshot.',
    'Especificá un path para proteger.': 'Specify a path to protect.',
    'Especificá un path para ruteo.': 'Specify a path to route.',
    'Falta el número de PR.': 'Missing PR number.',
    'Falta el número de issue.': 'Missing issue number.',
    'Falta el slug del proyecto': 'Missing project slug',
    'Falta el título del PR.': 'Missing PR title.',
    'Falta el título del issue.': 'Missing issue title.',
    'Faltan datos: necesito el slug y el término de búsqueda': 'Missing data: need slug and search term',
    'Faltan datos: necesito el slug, el tipo y el contenido': 'Missing data: need slug, type and content',
    'Faltan datos: necesito slug, skillname y acción': 'Missing data: need slug, skill name and action',
    'Faltan datos: necesito subcomando (save|status) y slug': 'Missing data: need subcommand (save|status) and slug',
    'Hot (carga automática)': 'Hot (auto-loaded)',
    'Listado de PRs excedió el tiempo de espera.': 'PR listing timed out.',
    'Listado de issues excedió el tiempo de espera.': 'Issue listing timed out.',
    'Merge excedió el tiempo de espera.': 'Merge timed out.',
    "No conozco el comando '{cmd}'. Usá 'status', 'save', 'search', 'context', 'session', 'index' o 'gc'.": "Unknown command '{cmd}'. Use 'status', 'save', 'search', 'context', 'session', 'index', or 'gc'.",
    "No conozco el comando '{cmd}'. Usá: scan, match, classify, learn, suggest o status.": "Unknown command '{cmd}'. Use: scan, match, classify, learn, suggest, or status.",
    "No conozco el subcomando 'session {sub}'. Usá 'save' o 'status'.": "Unknown subcommand 'session {sub}'. Use 'save' or 'status'.",
    'No hay cambios para revertir.': 'No changes to revert.',
    "No hay comando configurado para '{action}'. Usá 'guardian setup' para configurarlo.": "No command configured for '{action}'. Use 'guardian setup' to configure it.",
    'No se encontró: {ABSORB_SCRIPT}': 'Not found: {ABSORB_SCRIPT}',
    'No se encontró: {MEMORY_SCRIPT}': 'Not found: {MEMORY_SCRIPT}',
    'No se pudo revertir (git checkout falló).': 'Could not revert (git checkout failed).',
    "No se puede saltar de '{last_step}' a '{step}'. El siguiente paso debería ser '{expected}'. Usá --force para saltar esta verificación.": "Cannot skip from '{last_step}' to '{step}'. Next step should be '{expected}'. Use --force to skip this check.",
    "Operación bloqueada: '{p}' está protegido.": "Operation blocked: '{p}' is protected.",
    "Paso no válido: '{step}'. Usá: {', '.join(WORKFLOW_STEPS)}": "Invalid step: '{step}'. Use: {', '.join(WORKFLOW_STEPS)}",
    'Path protegido: {path}': 'Protected path: {path}',
    "Post-change: {', '.join(files) if files else 'cambios'} | issues: {issues}": "Post-change: {', '.join(files) if files else 'changes'} | issues: {issues}",
    'Pre-change completado': 'Pre-change completed',
    "Proyecto '{slug}' configurado": "Project '{slug}' configured",
    "Proyecto '{slug}' no encontrado.": "Project '{slug}' not found.",
    'Revertir excedió el tiempo de espera.': 'Revert timed out.',
    'Sin PRs activos.': 'No active PRs.',
    'Sin PRs.': 'No PRs.',
    'Sin issues.': 'No issues.',
    'Sin sesiones': 'No sessions',
    'Sistema de memoria — cómo usarlo:': 'Memory system — how to use it:',
    'Snapshot: {path}': 'Snapshot: {path}',
    'Status de PR excedió el tiempo de espera.': 'PR status timed out.',
    "Subcomando de PR no válido: '{subcmd}'. Usá: create, status, comment, approve, merge, list, checkout": "Invalid PR subcommand: '{subcmd}'. Use: create, status, comment, approve, merge, list, checkout",
    "Subcomando de issue no válido: '{subcmd}'. Usá: list, create, close, comment": "Invalid issue subcommand: '{subcmd}'. Use: list, create, close, comment",
    "Subcomando docs no válido: '{sub}'. Usá: scan, route": "Invalid docs subcommand: '{sub}'. Use: scan, route",
    "Subcomando no válido: '{subcmd}'. Usá: list, status, gc, absorb": "Invalid subcommand: '{subcmd}'. Use: list, status, gc, absorb",
    'Template no encontrado: {template_file}': 'Template not found: {template_file}',
    'Uso del sistema de absorb:': 'Absorb system usage:',
    'Uso: guardian <comando> [args...]': 'Usage: guardian <command> [args...]',
    'Uso: guardian absorb <scan|match|classify|learn|suggest|status> [args...]': 'Usage: guardian absorb <scan|match|classify|learn|suggest|status> [args...]',
    'Uso: guardian docs <scan|route> [args...]': 'Usage: guardian docs <scan|route> [args...]',
    'Uso: guardian docs route <path> [slug]': 'Usage: guardian docs route <path> [slug]',
    'Uso: guardian issue <list|create|close|comment> [args]': 'Usage: guardian issue <list|create|close|comment> [args]',
    'Uso: guardian issue comment <número> <cuerpo>': 'Usage: guardian issue comment <number> <body>',
    'Uso: guardian memory <save|search|context|gc|status|index|session> [args...]': 'Usage: guardian memory <save|search|context|gc|status|index|session> [args...]',
    'Uso: guardian pr <create|status|comment|approve|merge|list|checkout> [args]': 'Usage: guardian pr <create|status|comment|approve|merge|list|checkout> [args]',
    'Uso: guardian pr comment <número> <cuerpo>': 'Usage: guardian pr comment <number> <body>',
    'Uso: guardian projects <list|status|gc|absorb> [args]': 'Usage: guardian projects <list|status|gc|absorb> [args]',
    'Uso: guardian projects absorb match': 'Usage: guardian projects absorb match',
    'Uso: guardian prompt <paso> [--scope=...] [--type=...] [--files=...] [slug]': 'Usage: guardian prompt <step> [--scope=...] [--type=...] [--files=...] [slug]',
    'Uso: guardian protect <path> [slug]': 'Usage: guardian protect <path> [slug]',
    'Uso: guardian snapshot <path> [slug]': 'Usage: guardian snapshot <path> [slug]',
    'Warm (relevantes)': 'Warm (relevant)',
    'funcionó bien': 'worked well',
    'gh CLI no encontrado.': 'gh CLI not found.',
    'gh CLI no encontrado. Instalá GitHub CLI: https://cli.github.com/': 'gh CLI not found. Install GitHub CLI: https://cli.github.com/',
    'lo usaste': 'you used it',
    "no funcionó": "didn't work",
    '{action} excedió el tiempo de espera': '{action} timed out',
    "{changes['new']} nuevo(s)": "{changes['new']} new",
    "{changes['removed']} eliminado(s)": "{changes['removed']} removed",
    "{changes['updated']} actualizado(s)": "{changes['updated']} updated",
    '{prompt} [s/N] ': '{prompt} [y/N] ',
    '⏪ Revertir último cambio': '⏪ Revert last change',
    '✅ Post-deploy: {slug}': '✅ Post-deploy: {slug}',
    '📊 Proyectos — Estadísticas': '📊 Projects — Stats',
    '📋 Proyectos': '📋 Projects',
    '📋 Reporte: {slug}': '📋 Report: {slug}',
    '📋 Workflow: {slug}': '📋 Workflow: {slug}',
    '📌 Contexto: {slug}': '📌 Context: {slug}',
    '🔄 Post-change: {slug}': '🔄 Post-change: {slug}',
    '🔄 Pre-change: {slug}': '🔄 Pre-change: {slug}',
    '🔌 Hooks: {slug}': '🔌 Hooks: {slug}',
    '🔍 Verificando: {slug}': '🔍 Verifying: {slug}',
    '🗺️  Ruteo de docs: {slug}': '🗺️  Doc routing: {slug}',
    '🚀 Pre-deploy: {slug}': '🚀 Pre-deploy: {slug}',
}


def _resolve_positional(key: str) -> str | None:
    """If key has positional {} placeholders, try to match a named key in _EN_OVERRIDES
    and return the EN value with named placeholders replaced by {} too."""
    if '{}' not in key:
        return None
    import re
    for en_key, en_val in _EN_OVERRIDES.items():
        if '{}' in en_key:
            continue
        try:
            pattern = re.escape(en_key)
        except re.error:
            continue
        pattern = re.sub(r'\\\{[^}]+\\\}', '\\{\\}', pattern)
        pattern = '^' + pattern + '$'
        if re.match(pattern, key):
            en_val_pos = re.sub(r'\{[^}]+\}', '{}', en_val)
            return en_val_pos
    return None

def _(key: str, *args, **kwargs) -> str:
    if GUARDIAN_LANG == "en":
        s = _STRINGS["en"].get(key, None)
        if s is not None:
            return s.format(*args, **kwargs) if args or kwargs else s
        s = _EN_OVERRIDES.get(key, None)
        if s is not None:
            return s.format(*args, **kwargs) if args or kwargs else s
        if '{}' in key:
            s = _resolve_positional(key)
            if s is not None:
                return s.format(*args) if args else s
        return key.format(*args, **kwargs) if args or kwargs else key
    s = _STRINGS.get(GUARDIAN_LANG, _STRINGS.get("en", {})).get(key, None)
    if s is not None:
        return s.format(*args, **kwargs) if args or kwargs else s
    return key.format(*args, **kwargs) if args or kwargs else key


def set_lang(lang: str):
    global GUARDIAN_LANG
    GUARDIAN_LANG = lang


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ts_epoch(ts_str):
    try:
        dt = datetime.strptime(str(ts_str).replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z")
        return int(dt.timestamp())
    except (ValueError, AttributeError):
        try:
            dt = datetime.fromisoformat(str(ts_str).replace("Z", ""))
            return int(dt.timestamp())
        except (ValueError, AttributeError):
            return 0


def hash_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except (OSError, FileNotFoundError):
        return None


def hash_dict(data: dict) -> str:
    serialized = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


# ── Staleness check ────────────────────────────────────

def is_stale(last_ts: str | None, max_age_days: int = 7) -> bool:
    if not last_ts:
        return True
    last_epoch = ts_epoch(last_ts)
    if last_epoch == 0:
        return True
    now_epoch = int(datetime.now(timezone.utc).timestamp())
    age_days = (now_epoch - last_epoch) // 86400
    return age_days > max_age_days


def project_exists(slug: str) -> bool:
    return (MEMORY_DIR / slug / "config.yaml").exists()


def discover_projects():
    if not MEMORY_DIR.exists():
        return []
    return sorted(d.name for d in MEMORY_DIR.iterdir()
                  if d.is_dir() and (d / "config.yaml").exists())


def read_config(slug: str):
    p = project_dir(slug) / "config.yaml"
    if not p.exists():
        return {}
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8", errors="replace"))
        return _stringify_datetimes(data) if isinstance(data, dict) else {}
    except yaml.YAMLError:
        return {}


def _stringify_datetimes(value):
    if isinstance(value, dict):
        return {k: _stringify_datetimes(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_stringify_datetimes(v) for v in value]
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, date):
        return value.isoformat()
    return value


def write_config(slug: str, config: dict):
    p = project_dir(slug) / "config.yaml"
    data = _stringify_datetimes(config)
    p.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def read_audit(slug: str):
    data = read_json(project_dir(slug) / "audit.json", None)
    return data if isinstance(data, list) else []


def write_audit(slug: str, entries):
    p = project_dir(slug) / "audit.json"
    p.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


def read_skills_json(slug: str):
    data = read_json(project_dir(slug) / "skills.json", None)
    return data if data else {"relevant": [], "scores": {}, "hot": [], "last_match": None}


def write_skills_json(slug: str, data: dict):
    p = project_dir(slug) / "skills.json"
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_mode_state(slug: str):
    data = read_json(project_dir(slug) / "mode-state.json", None)
    if not isinstance(data, dict):
        data = {}
    data.setdefault("mode", DEFAULT_MODE)
    data.setdefault("updated", None)
    data.setdefault("history", [])
    if not isinstance(data["history"], list):
        data["history"] = []
    return data


def write_mode_state(slug: str, data: dict):
    p = project_dir(slug) / "mode-state.json"
    payload = dict(data)
    payload.setdefault("mode", DEFAULT_MODE)
    payload.setdefault("updated", ts())
    payload.setdefault("history", [])
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def append_mode_history(slug: str, mode: str, reason: str = ""):
    state = read_mode_state(slug)
    now = ts()
    state["mode"] = mode
    state["updated"] = now
    history = state.get("history", [])
    history.append({"ts": now, "mode": mode, "reason": reason})
    state["history"] = history[-20:]
    write_mode_state(slug, state)
    return state


def read_knowledge_index(slug: str):
    data = read_json(project_dir(slug) / "knowledge" / "index.json", None)
    if not isinstance(data, dict):
        data = {}
    data.setdefault("tomes", [])
    data.setdefault("updated", None)
    return data


def write_knowledge_index(slug: str, data: dict):
    p = project_dir(slug) / "knowledge" / "index.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_memory(slug: str):
    mf = project_dir(slug) / "brain" / "memory.jsonl"
    if not mf.exists() or mf.stat().st_size == 0:
        return []
    entries = []
    with open(mf, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def get_docs_routes(config):
    docs = config.get("docs", {})
    if not isinstance(docs, dict):
        return {}
    routes = {}
    doc_keys = {"mandatory", "frontend", "backend", "ui", "features", "last_scan", "available"}
    if "routes" in docs and isinstance(docs["routes"], dict):
        for k, v in docs["routes"].items():
            if not isinstance(v, dict):
                routes[k] = v
    for k, v in docs.items():
        if isinstance(v, dict) or k in doc_keys or k == "routes":
            continue
        if "/" in k or "*" in k:
            routes[k] = v
    return routes


def get_docs_available(config):
    docs = config.get("docs", {})
    if not isinstance(docs, dict):
        return {}
    available = {}
    for name in ["frontend", "backend", "ui", "features"]:
        val = docs.get(name)
        if isinstance(val, str):
            available[name] = val.lower() == "true"
        else:
            available[name] = bool(val)
    return available


def get_docs_last_scan(config):
    docs = config.get("docs", {})
    if not isinstance(docs, dict):
        return ""
    val = docs.get("last_scan", "")
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%dT%H:%M:%SZ")
    return val if isinstance(val, str) else str(val) if val else ""

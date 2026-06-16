import { execSync } from "child_process"
import type { Plugin, Permission } from "@opencode-ai/plugin"

const GUARDIAN = "/opt/nexxoria-guardian/guardian"
const BACKEND = "http://127.0.0.1:9787"
const CACHE_TTL = 300_000 // 5 min

let backendReady = false

async function ensureBackend(): Promise<boolean> {
  if (backendReady) return true
  try {
    const res = await fetch(`${BACKEND}/health`, { signal: AbortSignal.timeout(1000) })
    if (res.ok) { backendReady = true; return true }
  } catch { /* not running */ }
  // Start backend
  try {
    execSync(`${GUARDIAN} backend start`, { timeout: 5000, windowsHide: true })
    // Wait for it
    for (let i = 0; i < 10; i++) {
      await new Promise(r => setTimeout(r, 500))
      try {
        const r = await fetch(`${BACKEND}/health`, { signal: AbortSignal.timeout(500) })
        if (r.ok) { backendReady = true; return true }
      } catch { /* still starting */ }
    }
  } catch { /* failed to start */ }
  return false
}

function guardian(...args: string[]): string {
  try {
    return execSync(`${GUARDIAN} ${args.join(" ")}`, {
      encoding: "utf-8",
      timeout: 15000,
      windowsHide: true,
    }).trim()
  } catch {
    return ""
  }
}

function slugDir(dir: string): string {
  const name = dir.split("/").pop() || "unknown"
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")
}

// ── Permission cache ─────────────────────────────────────────

interface CacheEntry {
  allowed: boolean
  action: string
  ts: number
}

const permCache = new Map<string, CacheEntry>()
let currentMode = "plan"

function cacheKey(path: string, operation: string, mode: string): string {
  return `${mode}:${operation}:${path}`
}

function cacheGet(path: string, operation: string): CacheEntry | undefined {
  const key = cacheKey(path, operation, currentMode)
  const entry = permCache.get(key)
  if (!entry) return undefined
  if (Date.now() - entry.ts > CACHE_TTL) {
    permCache.delete(key)
    return undefined
  }
  return entry
}

function cacheSet(path: string, operation: string, entry: CacheEntry): void {
  const key = cacheKey(path, operation, currentMode)
  permCache.set(key, entry)
  if (permCache.size > 200) {
    const first = permCache.keys().next().value
    if (first) permCache.delete(first)
  }
}

function invalidateCache(): void {
  permCache.clear()
}

// ── Backend permission check ─────────────────────────────────

async function checkPermission(
  slug: string, path: string, operation: string
): Promise<CacheEntry> {
  const cached = cacheGet(path, operation)
  if (cached) return cached

  try {
    const controller = new AbortController()
    const id = setTimeout(() => controller.abort(), 1000)
    const res = await fetch(`${BACKEND}/permission/check`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slug, path, operation, mode: currentMode }),
      signal: controller.signal,
    })
    clearTimeout(id)
    if (!res.ok) throw new Error(`backend returned ${res.status}`)
    const data = await res.json()
    const entry: CacheEntry = {
      allowed: data.allowed === true,
      action: data.action || "investigate",
      ts: Date.now(),
    }
    cacheSet(path, operation, entry)
    return entry
  } catch {
    return { allowed: true, action: "assume", ts: Date.now() }
  }
}

// ── Path module matching ─────────────────────────────────────

interface ModuleRule {
  name: string
  guard: "blocked" | "readonly" | "conciencia" | "allowed"
  message: string
}

const MODULES: ModuleRule[] = [
  { name: "genome",       guard: "readonly",   message: "Genome is read-only. Mutations require creator." },
  { name: "core_lib",     guard: "readonly",   message: "Core library is read-only." },
  { name: "conciencia",   guard: "conciencia", message: "Consciousness module needs conciencia approval." },
  { name: "evolution",    guard: "conciencia", message: "Evolution params need conciencia approval." },
  { name: "memory",       guard: "conciencia", message: "Memory changes need conciencia approval." },
  { name: "rag",          guard: "conciencia", message: "RAG pipeline needs conciencia approval." },
  { name: "backend",      guard: "conciencia", message: "Backend changes need conciencia approval." },
  { name: "absorb",       guard: "conciencia", message: "Absorb changes need conciencia approval." },
  { name: "mcp",          guard: "conciencia", message: "MCP module needs conciencia approval." },
  { name: "forja",        guard: "conciencia", message: "Forja module needs conciencia approval." },
  { name: "config",       guard: "conciencia", message: "Config changes need conciencia approval." },
  { name: "plugin",       guard: "allowed",    message: "" },
  { name: "templates",    guard: "allowed",    message: "" },
  { name: "docs",         guard: "allowed",    message: "" },
]

function matchModule(path: string): ModuleRule | undefined {
  const normalized = path.replace(/\\/g, "/")
  for (const mod of MODULES) {
    if (normalized.includes(`/${mod.name}/`) || normalized.endsWith(`/${mod.name}`)) {
      return mod
    }
  }
  // Check for specific files
  if (normalized.endsWith("/identity.yaml") || normalized.includes("genome/")) return MODULES.find(m => m.name === "genome")
  if (normalized.includes("guardian_conciencia")) return MODULES.find(m => m.name === "conciencia")
  if (normalized.includes("guardian_evolution")) return MODULES.find(m => m.name === "evolution")
  if (normalized.includes("guardian_memory")) return MODULES.find(m => m.name === "memory")
  if (normalized.includes("guardian_rag")) return MODULES.find(m => m.name === "rag")
  if (normalized.includes("guardian_backend")) return MODULES.find(m => m.name === "backend")
  if (normalized.includes("guardian_absorb")) return MODULES.find(m => m.name === "absorb")
  if (normalized.includes("guardian_mcp")) return MODULES.find(m => m.name === "mcp")
  if (normalized.includes("guardian_forja")) return MODULES.find(m => m.name === "forja")
  if (normalized.includes("guardian.py") || normalized.includes("guardian_shared")) return MODULES.find(m => m.name === "core_lib")
  if (normalized.includes(".opencode/")) return MODULES.find(m => m.name === "plugin")
  if (normalized.includes("/templates/")) return MODULES.find(m => m.name === "templates")
  if (normalized.includes("/docs/")) return MODULES.find(m => m.name === "docs")
  return undefined
}

function isWriteOp(perm: Permission): boolean {
  return perm.type === "edit" || perm.type === "write" || perm.type === "delete"
}

function extractPath(perm: Permission): string {
  if (typeof perm.pattern === "string") return perm.pattern
  if (Array.isArray(perm.pattern)) return perm.pattern[0] || ""
  return perm.metadata?.path as string || perm.title || ""
}

// ── Module permission context description ───────────────────

function moduleContextLines(): string[] {
  const lines: string[] = []
  for (const mod of MODULES) {
    const icon =
      mod.guard === "blocked" ? "🚫" :
      mod.guard === "readonly" ? "🔒" :
      mod.guard === "conciencia" ? "🧠" :
      "✅"
    const label =
      mod.guard === "blocked" ? "BLOCKED" :
      mod.guard === "readonly" ? "READ ONLY" :
      mod.guard === "conciencia" ? "CONCIENCIA REQUIRED" :
      "ALLOWED"
    lines.push(`  ${icon} \`${mod.name}\` — ${label}`)
  }
  return lines
}

// ── Plugin export ────────────────────────────────────────────

export const GuardianPlugin: Plugin = async ({ project, client, $, directory, worktree }) => {
  const slug = slugDir(directory)

  // Refresh current mode on load
  try { currentMode = guardian("mode", slug, "status") || "plan" } catch { /* ignore */ }

  // Auto-start backend in background (don't block plugin init)
  ensureBackend().catch(() => {})

  return {
    tool: {
      guardian_status: {
        description: "Show Guardian genome, branch, and current mode status",
        args: {},
        async execute(_args: any, _ctx: any) {
          const out = guardian("mode", slug, "status")
          return { status: out || "plan (default)", slug }
        },
      },

      guardian_conciencia: {
        description: "Run a Guardian consciousness cycle (N1 perceive->decide->reflect + N2 meta)",
        args: {
          question: { type: "string", description: "Optional question to drive the cycle" },
          mode: { type: "string", enum: ["plan", "build"], description: "Override mode for the cycle" },
        },
        async execute(args: any) {
          const cmdArgs = ["conciencia", slug, "cycle"]
          if (args.question) cmdArgs.push(args.question)
          const result = guardian(...cmdArgs)
          invalidateCache()
          return { result }
        },
      },

      guardian_rag: {
        description: "Search Guardian RAG knowledge base (memory + tomes + docs)",
        args: {
          query: { type: "string", description: "Search query" },
          top_k: { type: "number", description: "Results count (default: 5)" },
        },
        async execute(args: any) {
          const cmdArgs = ["rag", args.query, "--slug", slug]
          if (args.top_k) cmdArgs.push("--top-k", String(args.top_k))
          const result = guardian(...cmdArgs)
          return { query: args.query, result }
        },
      },

      guardian_mode: {
        description: "Switch Guardian mode (read/plan/build/commit/review) or show current status",
        args: {
          mode: { type: "string", enum: ["read", "plan", "build", "commit", "review"], description: "Target mode" },
          reason: { type: "string", description: "Reason for switching" },
        },
        async execute(args: any) {
          if (!args.mode) {
            const out = guardian("mode", slug, "status")
            return { mode: out || "plan" }
          }
          const reason = args.reason || "via OpenCode plugin"
          guardian("mode", slug, args.mode, reason)
          currentMode = args.mode
          invalidateCache()
          return { mode: args.mode, switched: true, reason }
        },
      },

      guardian_check_permission: {
        description: "Check if an operation is allowed by Guardian conciencia",
        args: {
          path: { type: "string", description: "File path to check" },
          operation: { type: "string", enum: ["edit", "bash", "webfetch"], description: "Operation type" },
        },
        async execute(args: any) {
          const result = await checkPermission(slug, args.path || "", args.operation || "edit")
          const module = matchModule(args.path || "")
          return {
            allowed: result.allowed,
            action: result.action,
            module: module?.name || "unknown",
            module_guard: module?.guard || "allowed",
          }
        },
      },

      guardian_why_blocked: {
        description: "Explain why a path is blocked and how to unblock it",
        args: {
          path: { type: "string", description: "File path that is blocked" },
        },
        async execute(args: any) {
          const module = matchModule(args.path || "")
          if (!module || module.guard === "allowed") {
            return { blocked: false, message: "This path is not blocked by any module rule." }
          }
          const explanations: Record<string, string> = {
            blocked: "This module is permanently blocked.",
            readonly: "This module is read-only. You can read but not modify it.",
            conciencia: "This module requires conciencia approval. Run `guardian conciencia cycle` to seed the conciencia, and absorb relevant skills to improve confidence.",
          }
          const tips: Record<string, string> = {
            conciencia: "Absorb skills with `guardian absorb scan && guardian absorb match <slug>` then run `guardian conciencia cycle \"I want to modify this module\"`",
            readonly: "If you must modify this, switch to build mode and run `guardian conciencia cycle` explaining why.",
          }
          return {
            blocked: module.guard !== "allowed",
            module: module.name,
            guard: module.guard,
            message: explanations[module.guard] || module.message,
            tip: tips[module.guard] || "",
          }
        },
      },

      // ── v3 cognitive memory tools ───────────────────────────

      guardian_brain_read: {
        description: "Read GUARDIAN.md essential working memory (always-loaded)",
        args: {
          slug: { type: "string", description: "Project slug (default: current)" },
        },
        async execute(args: any) {
          const s = args.slug || slug
          const out = guardian("brain", "guardian", s)
          return { slug: s, guardian_md: out }
        },
      },

      guardian_brain_query: {
        description: "Vector search the project's cognitive memory (semantic/episodic/procedural/reflection)",
        args: {
          slug: { type: "string" },
          level: { type: "string", enum: ["semantic", "episodic", "procedural", "reflection"] },
          q: { type: "string" },
          top_k: { type: "number" },
        },
        async execute(args: any) {
          const s = args.slug || slug
          const k = args.top_k || 5
          const out = guardian("brain", "query", s, args.level, args.q, "--top-k", String(k))
          return { slug: s, level: args.level, q: args.q, result: out }
        },
      },

      guardian_brain_write: {
        description: "Write a node to the project's brain (passes through Governor)",
        args: {
          slug: { type: "string" },
          level: { type: "string", enum: ["semantic", "episodic", "procedural", "reflection"] },
          kind: { type: "string" },
          content: { type: "string" },
          importance: { type: "number" },
        },
        async execute(args: any) {
          const s = args.slug || slug
          const imp = args.importance ?? 0.6
          const out = guardian("brain", "write", s, args.level, args.kind, args.content, "--importance", String(imp))
          return { slug: s, result: out }
        },
      },

      guardian_brain_reflect: {
        description: "Trigger the Reflection Agent (post-session memory consolidation)",
        args: {
          slug: { type: "string" },
        },
        async execute(args: any) {
          const s = args.slug || slug
          const out = guardian("brain", "reflect", s)
          return { slug: s, result: out }
        },
      },

      guardian_session_end: {
        description: "End session: reflection + GUARDIAN.md regen + handoff",
        args: {
          slug: { type: "string" },
          reason: { type: "string" },
        },
        async execute(args: any) {
          const s = args.slug || slug
          const r = args.reason || "explicit"
          const out = guardian("session", s, "end", "--reason=" + r)
          return { slug: s, result: out }
        },
      },

      guardian_knowledge_research: {
        description: "Investigate a topic and return a research plan with TTL",
        args: {
          slug: { type: "string" },
          query: { type: "string" },
          depth: { type: "string", enum: ["quick", "deep"] },
        },
        async execute(args: any) {
          const s = args.slug || slug
          const d = args.depth || "quick"
          const out = guardian("knowledge", "research", s, args.query, "--depth", d)
          return { slug: s, query: args.query, result: out }
        },
      },

      guardian_specialization_enable: {
        description: "Activate a stack-aware specialization (odoo, nextjs, fastapi, postgres, python)",
        args: {
          slug: { type: "string" },
          name: { type: "string" },
        },
        async execute(args: any) {
          const s = args.slug || slug
          const out = guardian("specialization", "enable", s, args.name)
          return { slug: s, name: args.name, result: out }
        },
      },

      guardian_maintain: {
        description: "Run a complete project health report (drift, stale nodes, config issues)",
        args: {
          slug: { type: "string" },
        },
        async execute(args: any) {
          const s = args.slug || slug
          const out = guardian("maintain", s)
          return { slug: s, result: out }
        },
      },

      guardian_publish: {
        description: "Publish a project as a sanitized template",
        args: {
          slug: { type: "string" },
          version: { type: "string" },
          to: { type: "string", enum: ["template", "production"] },
        },
        async execute(args: any) {
          const s = args.slug || slug
          const v = args.version || "1.0.0"
          const t = args.to || "template"
          const out = guardian("publish", s, "--version=" + v, "--to=" + t)
          return { slug: s, result: out }
        },
      },

      guardian_clone: {
        description: "Create a new project from a template",
        args: {
          template: { type: "string" },
          new: { type: "string" },
        },
        async execute(args: any) {
          const out = guardian("clone", args.template, args.new)
          return { result: out }
        },
      },

      guardian_capability_status: {
        description: "Read the model card (success rate per task type)",
        args: {},
        async execute(_args: any) {
          const out = guardian("capability", "status")
          return { result: out }
        },
      },

      guardian_capability_routing: {
        description: "Decide whether to delegate a task to the LLM or answer from local memory",
        args: {
          task_type: { type: "string" },
          context_size: { type: "number" },
          complexity: { type: "string", enum: ["low", "medium", "high"] },
        },
        async execute(args: any) {
          const cx = args.context_size ?? 0
          const co = args.complexity ?? "medium"
          const out = guardian("capability", "routing", args.task_type, "--context-size", String(cx), "--complexity", co)
          return { result: out }
        },
      },

      guardian_compact_now: {
        description: "Trigger auto-compaction of the brain (Governor GC + archive)",
        args: {
          slug: { type: "string" },
        },
        async execute(args: any) {
          const s = args.slug || slug
          const out = guardian("brain", "auto-compact", s)
          return { slug: s, result: out }
        },
      },
    },

    // ── permission.ask: intercept and block guarded ops ───────

    "permission.ask": async (input: Permission, output: { status: "ask" | "deny" | "allow" }) => {
      try {
        const isWrite = isWriteOp(input)
        if (!isWrite && input.type !== "bash") return

        const path = extractPath(input)
        if (!path) return

        const module = matchModule(path)
        if (!module) return

        // Static guards first (fast path, no conciencia call)
        if (module.guard === "blocked") {
          output.status = "deny"
          return
        }
        if (module.guard === "readonly") {
          if (isWrite) {
            output.status = "deny"
            return
          }
          return // allow reads
        }
        if (module.guard === "allowed") {
          return // allow
        }

        // conciencia guard: check with backend
        const result = await checkPermission(slug, path, input.type)
        if (!result.allowed) {
          output.status = "deny"
          return
        }
        // allow — let it through
      } catch {
        // On error, fallback to default (ask user)
      }
    },

    "session.created": async (_input: any, output: any) => {
      try {
        currentMode = guardian("mode", slug, "status") || "plan"
        output.context = output.context || []

        // v4: Advisor builds dynamic context (5-15 lines vs 30 fixed)
        // Returns "" if nothing relevant: doesn't pollute the context window
        const advisorCtx = guardian(
          "brain", "advisor-context", slug, ""
        )
        if (advisorCtx) {
          output.context.push("## Guardian\n" + advisorCtx)
        }
        // Compact tools list (one line) so the LLM knows what exists
        output.context.push("Guardian tools: guardian_status, guardian_conciencia, guardian_rag, guardian_mode, guardian_brain_read, guardian_brain_query, guardian_brain_write, guardian_brain_reflect, guardian_session_end, guardian_query_smart, guardian_knowledge_research, guardian_specialization_enable, guardian_maintain, guardian_publish, guardian_capability_status, guardian_compact_now, guardian_check_permission, guardian_why_blocked")
      } catch {
        // silent
      }
    },

    // v4: chat.message hook — log user prompts
    "chat.message": async (input: any, _ctx: any) => {
      try {
        guardian("observer", "log-prompt", slug, input.content || "", "--mode=build")
      } catch {
        // silent
      }
    },

    // v4: tool.execute.before — advisor warns if action is risky
    "tool.execute.before": async (input: any, output: any) => {
      try {
        const warn = guardian(
          "advisor", "warn-action", slug,
          input.tool || "", input.args || "", input.file || ""
        )
        if (warn) {
          output.context = output.context || []
          output.context.push("⚠ " + warn)
        }
      } catch {
        // silent
      }
    },

    // v4: tool.execute.after — observer routes the event
    "tool.execute.after": async (input: any, _output: any) => {
      try {
        guardian("observer", "route", slug, input.tool || "",
                 JSON.stringify(input.args || {}), JSON.stringify(_output || {}))
      } catch {
        // silent
      }
    },

    "experimental.session.compacting": async (_input: any, output: any) => {
      try {
        currentMode = guardian("mode", slug, "status") || "plan"
        output.context = output.context || []
        output.context.push(
          `Guardian v2 active for \`${slug}\`. Mode: **${currentMode.trim()}**. ` +
          `Modules guarded by conciencia: ${MODULES.filter(m => m.guard === "conciencia").map(m => `\`${m.name}\``).join(", ")}.`
        )
      } catch {
        // silent
      }
    },

    "tui.prompt.append": async (input: any) => {
      if (!input.text) return
      const t = input.text.toLowerCase()
      const planKw = ["plan", "think", "analyze", "design", "architect", "explore", "investigate", "diseñar", "analizar", "explorar"]
      const buildKw = ["build", "implement", "fix", "add", "create", "make", "change", "write", "refactor", "construir", "implementar", "crear"]
      const planScore = planKw.filter(k => t.includes(k)).length
      const buildScore = buildKw.filter(k => t.includes(k)).length
      if (planScore > buildScore && planScore >= 2) {
        guardian("mode", slug, "plan", "auto: prompt keywords")
        currentMode = "plan"
        invalidateCache()
      } else if (buildScore > planScore && buildScore >= 2) {
        guardian("mode", slug, "build", "auto: prompt keywords")
        currentMode = "build"
        invalidateCache()
      }
    },

    "shell.env": async (_input: any, output: any) => {
      output.env = output.env || {}
      output.env.GUARDIAN_HOME = "/opt/nexxoria-guardian"
      output.env.GUARDIAN_DATA = "/var/guardian"
    },
  }
}

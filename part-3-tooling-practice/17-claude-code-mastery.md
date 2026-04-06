<!--
  CHAPTER: 17
  TITLE: Claude Code Mastery
  PART: III — Tooling & Practice
  PREREQS: Chapter 12 (basic CLI/Git skills)
  KEY_TOPICS: Claude Code, skills, plugins, hooks, MCP servers, agent teams, subagents, CLAUDE.md, plan mode, TDD workflow, CI integration
  DIFFICULTY: Beginner → Advanced
  UPDATED: 2026-03-24
-->

# Chapter 17: Claude Code Mastery

> **Part III — Tooling & Practice** | Prerequisites: Chapter 12 (basic CLI/Git skills) | Difficulty: Beginner → Advanced

Mastering Claude Code as a development multiplier — from basic usage to orchestrating multi-agent teams with custom skills, plugins, and MCP server integrations.

### In This Chapter
- Claude Code Fundamentals
- Advanced Claude Code Features
- Skills & Plugins
- Agent Teams & Orchestration
- Configuration & Customization
- Workflow Patterns for 100x Productivity
- Claude Code in Team Environments
- Tips & Tricks

### Related Chapters
- Chapter 14 (AI-powered engineering)
- Chapter 12 (developer tooling)
- Chapter 15 (team conventions/CI)
- Chapter 36 (Beast Mode — pushing Claude Code to its limits)

---

## 1. CLAUDE CODE FUNDAMENTALS

### 1.1 What Claude Code Is (And Why It Changes Everything)

Here is the thing nobody tells you when you first hear about AI coding assistants: most of them are glorified autocomplete. You paste code in, you get code back, you paste it into your editor. Back and forth, like some tedious relay race between your brain and a chatbot.

Claude Code is not that.

Claude Code is Anthropic's official CLI tool that puts a full AI coding agent directly in your terminal. It reads your files, writes code, runs commands, manages git, and executes multi-step tasks autonomously — the same way a senior engineer sitting next to you might. You describe what you need. It figures out the rest.

The mental model shift is real, and it matters: web-based AI is a conversation partner you bring information to. Claude Code is an agent you point at your codebase and tell what to do.

**How it differs from web-based AI:**

| Dimension | Web-based AI (ChatGPT, Claude.ai) | Claude Code (CLI) |
|---|---|---|
| File access | None — you paste code manually | Direct filesystem read/write |
| Command execution | None | Runs shell commands in your terminal |
| Git integration | None | Full git workflow (commit, branch, PR) |
| Context | Limited to what you paste | Reads your actual codebase |
| Multi-file edits | Manual copy-paste per file | Edits multiple files in one operation |
| Persistence | Chat history only | CLAUDE.md memory files across sessions |
| Tool use | Plugins/web browsing | MCP servers, custom hooks, shell tools |

Think of it this way: if web-based AI is a brilliant consultant you can call on the phone, Claude Code is that same person sitting in your office with full access to your system, reading your code as they talk to you, and actually making the changes themselves. That is a fundamentally different relationship.

If you have worked through Chapter 14's deep dive on AI-powered engineering, you already know the theoretical foundation — the right mental model for human-AI collaboration. This chapter is where theory becomes practice. This is where you build the suit.

### 1.2 Installation and Setup

**Install via npm:**

```bash
npm install -g @anthropic-ai/claude-code
```

**Or via Homebrew (macOS):**

```bash
brew install claude-code
```

**Authentication:**

```bash
# Authenticate with your Anthropic API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Or authenticate interactively
claude login
```

**First run:**

```bash
# Navigate to your project
cd ~/projects/my-app

# Start Claude Code
claude

# Or give it a task directly
claude "explain the architecture of this project"
```

**Verify installation:**

```bash
claude --version
claude --help
```

The first time you run `claude` in a project directory, take a minute to just ask it to explain the codebase. Not because you need the explanation — you wrote the code. Because watching it navigate your files, piece together the architecture, and synthesize a coherent overview in seconds is the moment it clicks that this thing is genuinely different.

### 1.3 The Conversation Model: How Context Works

**Context window basics:** Claude Code maintains a conversation context that includes everything discussed in the current session — your messages, Claude's responses, file contents that were read, command outputs, and tool results. This context has a finite size (the "context window").

Think of the context window like RAM. It is fast and immediately accessible, but finite. When it fills up, something has to give.

**What counts toward context:**

- Every message you send
- Every file Claude reads (the full content goes into context)
- Every command output
- Claude's own responses and reasoning
- Tool call inputs and outputs

**Context window management strategies:**

1. **Be surgical with file reads.** Instead of asking Claude to "look at the whole project," point it at specific files or directories. "Read src/lib/auth.ts and explain the token validation logic" is far more efficient than "explain authentication."

2. **Start fresh when context gets long.** If a session has been going for hundreds of messages, start a new one. Claude Code will tell you when context is getting full.

3. **Use CLAUDE.md for persistent context.** Instead of re-explaining your project every session, put key information in CLAUDE.md files (covered in Section 6). This is your persistent memory layer — the thing that makes Claude feel like it actually knows your project.

4. **Context compression.** Claude Code automatically summarizes older parts of the conversation when the context window fills up. You will see a message when this happens. Important details from early in the conversation may be lost — another reason to use CLAUDE.md for critical information.

```
# Signs you need to start a fresh session:
# - Claude starts forgetting earlier instructions
# - You see "context compressed" messages
# - Responses are getting slower
# - Claude is confused about the current state of files
```

The most common beginner mistake is treating Claude Code like a long-running conversation that you keep adding to indefinitely. Instead, think in terms of focused sessions with clear goals. Plan → Implement → Review → Commit → Start fresh. You will be more productive and Claude will be more coherent.

### 1.4 Permission Modes and Safety Model

Claude Code has a permission system that controls what actions it can take without asking you first. This is not bureaucracy — it is the safety harness that lets you actually trust an autonomous agent to work in your codebase.

**Permission levels:**

- **Read-only tools (always allowed):** Reading files, searching code, listing directories
- **Write tools (require approval):** Editing files, creating files, deleting files
- **Command execution (require approval):** Running shell commands
- **Dangerous operations:** Anything that could be destructive (force push, rm -rf, etc.)

**Approval modes:**

```bash
# Default: asks permission for writes and commands
claude

# Accept all edits but ask for commands
claude --accept-edits

# Accept everything (use with caution, appropriate for CI)
claude --accept-all

# Plan mode: Claude can only read and think, not write
claude --plan
```

**The permission prompt looks like this:**

```
Claude wants to edit src/api/handler.ts
  + import { validateInput } from './validators';
  +
    export async function handler(req: Request) {
  +   const validated = validateInput(req.body);
      // ...

Allow? (y)es / (n)o / (a)lways for this file / (A)lways for all files
```

The diff view here is intentional. You should be reading it. Every. Single. Time. At least until you have a feel for what Claude does in your specific codebase.

**Best practice:** Start with default permissions. Use `--accept-edits` once you trust Claude's edit patterns for a given task. Reserve `--accept-all` for CI pipelines and well-tested automation scripts — not for exploratory work where you are still figuring out the approach.

### 1.5 The /help Command and Built-in Commands

**Essential built-in commands:**

```
/help              Show all available commands and usage
/status            Show current session status (context usage, model, etc.)
/clear             Clear conversation history and start fresh
/compact           Compress the conversation to save context space
/model             Switch between models mid-session
/cost              Show token usage and cost for the current session
/quit or /exit     Exit Claude Code
```

One underrated habit: run `/status` periodically in long sessions. It tells you how much context you have consumed and helps you decide when to use `/compact` versus starting fresh. Context management is a skill, and `/status` gives you the data you need to get good at it.

---

## 2. ADVANCED CLAUDE CODE FEATURES

### 2.1 Slash Commands

Slash commands are built-in actions that trigger specific workflows. They are the shortcuts that turn Claude Code from a capable assistant into a streamlined dev tool.

**Core slash commands:**

```
/commit            Stage, commit with a generated message, and optionally push
/review            Review current changes (staged or unstaged)
/pr                Create a pull request with structured description
/help              List all commands
/clear             Clear context
/compact           Compress conversation
/model             Switch model
/cost              Show session costs
```

**Using /commit:**

```
> /commit

# Claude will:
# 1. Run git status and git diff
# 2. Analyze all changes
# 3. Generate a commit message following your repo's conventions
# 4. Show you the message for approval
# 5. Create the commit
```

Once you get used to `/commit`, writing your own commit messages starts to feel like manually calculating the tip on a restaurant bill. Technically you can do it. Why would you want to?

**Using /review:**

```
> /review

# Claude will:
# 1. Look at staged and unstaged changes
# 2. Analyze code quality, potential bugs, security issues
# 3. Provide structured feedback with specific line references
```

The `/review` command before every commit is the cheapest code review you will ever get. Use it every time, even when the change feels trivial. Especially when the change feels trivial.

### 2.2 Plan Mode: Writing and Executing Implementation Plans

Plan mode lets Claude analyze and plan without making any changes. This is essential for complex tasks where you want to understand the approach before committing to it.

There is a temptation with any powerful tool to just start using it. Point Claude at a complex problem, say "fix it," and see what happens. Sometimes this works great. Other times you end up with a three-hundred-line refactor that solves the wrong problem with an approach you never would have chosen.

Plan mode is the antidote.

**Starting in plan mode:**

```bash
# Start Claude Code in plan-only mode
claude --plan
```

**Or switch mid-conversation:**

```
> Switch to plan mode. Analyze what it would take to migrate our
  authentication from session-based to JWT tokens. Do not make any changes.
```

**The brainstorm-plan-implement pattern:**

```
# Step 1: Plan mode — understand the problem
> /plan Analyze our current auth system and propose a migration to JWT.
  Consider: backward compatibility, session invalidation, token refresh,
  and rollback strategy.

# Step 2: Review the plan, ask questions, refine
> What about existing active sessions during migration? Add a phased
  rollout approach.

# Step 3: Execute the plan
> Implement phase 1 of the plan: add JWT token generation alongside
  existing session auth.
```

**Why this matters:** Jumping straight to implementation on complex tasks leads to rework. The plan-first approach catches architectural issues before code is written — before Claude has touched fifty files and you have to unwind everything. A ten-minute plan conversation can save three hours of cleanup.

This workflow pairs naturally with the AI engineering principles in Chapter 14. The plan is your specification. The implementation is Claude executing against it. Your job is to be a sharp reviewer at both stages, not to write the code yourself.

### 2.3 Subagents: Dispatching Parallel Agents

**What subagents are:** Claude Code can spawn independent sub-conversations (subagents) to handle tasks in parallel. Each subagent has its own context and can work on a separate part of the problem.

This is where Claude Code starts feeling genuinely super-powered. You have not just one agent working for you — you have a whole team.

**When to use subagents:**

- Multiple independent files need changes that do not depend on each other
- You need to research several topics simultaneously
- Running tests in one agent while implementing in another
- Exploring multiple solution approaches in parallel

**How subagents work in practice:**

```
> I need to add input validation to all 5 API routes in src/api/.
  Each route is independent. Use parallel agents to handle them simultaneously.

# Claude dispatches subagents:
# Agent 1: src/api/users.ts
# Agent 2: src/api/orders.ts
# Agent 3: src/api/products.ts
# Agent 4: src/api/payments.ts
# Agent 5: src/api/inventory.ts
```

What would take you two hours of sequential work — context-switching between files, trying to remember where you were — takes Claude five minutes in parallel. All five routes get consistent validation patterns because they are all working from the same context. That is the multiplier.

**Subagent isolation:** Each subagent operates in its own context. They cannot see each other's work in progress. The orchestrator (main conversation) coordinates results. This isolation is a feature, not a limitation — it prevents agents from making decisions based on each other's half-finished work.

### 2.4 Git Worktrees for Isolated Feature Development

**What worktrees are:** Git worktrees let you check out multiple branches of the same repository simultaneously in different directories. Combined with Claude Code, this enables truly parallel feature development — not just parallel tasks within a single branch, but parallel features on parallel branches.

This is the closest thing to cloning yourself that software engineering currently offers.

**Setting up worktrees:**

```bash
# Create a worktree for a feature branch
git worktree add ../my-app-feature-auth feature/auth
git worktree add ../my-app-feature-billing feature/billing

# Now you have:
# ~/projects/my-app/                  (main branch)
# ~/projects/my-app-feature-auth/     (feature/auth branch)
# ~/projects/my-app-feature-billing/  (feature/billing branch)
```

**Running Claude Code in separate worktrees:**

```bash
# Terminal 1: Work on auth feature
cd ~/projects/my-app-feature-auth
claude "implement the JWT auth middleware"

# Terminal 2: Work on billing feature
cd ~/projects/my-app-feature-billing
claude "add Stripe webhook handlers"
```

**Why this matters:** Each Claude Code instance works in its own directory with its own branch. No merge conflicts during development, no stepping on each other's changes. One agent is deep in JWT middleware while another is wiring up Stripe webhooks — and they will never interfere with each other until you decide to merge.

See Chapter 36 (Beast Mode) for more advanced patterns around orchestrating multiple worktrees simultaneously at scale.

### 2.5 Background Tasks and Multi-Agent Workflows

**Background tasks:** You can run Claude Code tasks in the background and come back to check results later.

```bash
# Run a task in the background
claude --background "run all tests and fix any failures" &

# Check on running tasks
claude --status
```

**Multi-agent workflow example — full feature development:**

```bash
# Agent 1: Implement the feature
claude "implement the user invitation feature per the spec in docs/invite-spec.md"

# Agent 2 (after Agent 1 completes): Write tests
claude "write comprehensive tests for the invitation feature in src/features/invite/"

# Agent 3 (after Agent 2): Review everything
claude "review all changes for the invitation feature. Check for security issues, edge cases, and test coverage gaps"
```

Think of this as a pipeline. Each agent hands off to the next. You are the project manager — defining the stages, reviewing outputs, unblocking when something gets stuck. The agents are doing the engineering work.

### 2.6 Memory System: CLAUDE.md Files

**How Claude remembers across sessions:** Claude Code reads special markdown files called CLAUDE.md that contain instructions, context, and preferences. These files persist on disk and are automatically loaded at the start of every session.

This is your project's long-term memory. Without it, every session starts from zero — Claude has no idea what framework you use, what your conventions are, or where anything lives. With a well-written CLAUDE.md, Claude walks into your project like a senior engineer who has been on the team for months.

**CLAUDE.md file locations and hierarchy:**

```
~/.claude/CLAUDE.md                    # Global: applies to ALL projects
~/projects/my-app/CLAUDE.md            # Project root: applies to this project
~/projects/my-app/src/api/CLAUDE.md    # Sub-directory: applies when working in this area
```

**Example project-level CLAUDE.md:**

```markdown
# Project: Acme SaaS Platform

## Tech Stack
- Next.js 14 (App Router)
- TypeScript (strict mode)
- PostgreSQL via Prisma ORM
- Tailwind CSS
- Jest for unit tests, Playwright for E2E

## Code Conventions
- Use named exports, not default exports
- All API routes must validate input with zod schemas
- Database queries go in src/lib/db/ — never in route handlers directly
- Error handling: use the AppError class from src/lib/errors.ts
- All new features need tests before merging

## Architecture
- src/app/          — Next.js App Router pages and layouts
- src/components/   — React components (colocate with feature when possible)
- src/lib/          — Shared utilities, database, auth
- src/features/     — Feature modules (each has its own types, hooks, components)
- prisma/           — Database schema and migrations

## Testing Commands
- npm test                    — Run all unit tests
- npm run test:e2e            — Run Playwright E2E tests
- npm run test:coverage       — Run with coverage report

## Important Notes
- NEVER commit .env files
- Always run `npm run lint` before committing
- Database migrations must be backward-compatible (no dropping columns without a deprecation period)
- The CI pipeline runs on every PR — all checks must pass
```

**Example sub-directory CLAUDE.md (`src/api/CLAUDE.md`):**

```markdown
# API Route Conventions

## Every API route must:
1. Validate input with zod schema defined in the same file
2. Use the withAuth() wrapper for authenticated routes
3. Return consistent error shapes: { error: string, code: string, details?: unknown }
4. Log requests using the logger from src/lib/logger.ts

## Example pattern:
```typescript
import { z } from 'zod';
import { withAuth } from '@/lib/auth';
import { logger } from '@/lib/logger';

const CreateUserSchema = z.object({
  email: z.string().email(),
  name: z.string().min(1).max(100),
  role: z.enum(['admin', 'editor', 'viewer']),
});

export const POST = withAuth(async (req, { user }) => {
  const body = CreateUserSchema.parse(await req.json());
  logger.info('Creating user', { actor: user.id, email: body.email });
  // ...
});
```
```

The CLAUDE.md in a subdirectory is especially powerful in large codebases. When Claude is working in `src/api/`, it automatically loads the API-specific conventions without you having to mention them. Context-aware behavior without you doing anything.

### 2.7 Extended Thinking for Complex Problems

**What it is:** Extended thinking allows Claude to reason through complex problems step-by-step before responding. This uses more tokens but produces significantly better results for architectural decisions, complex debugging, and multi-step refactoring.

**When to use extended thinking:**

- Designing system architecture
- Debugging subtle race conditions or logic errors
- Planning large refactoring operations
- Analyzing security implications
- Any task where "think before you act" matters

**How to trigger it:**

```
> Think carefully about this: our payment processing has a race condition
  where two concurrent requests can double-charge a customer. Analyze the
  code in src/payments/ and propose a fix that handles all edge cases.
```

Using phrases like "think carefully," "think step by step," or "analyze thoroughly" signals Claude to engage deeper reasoning. For genuinely complex problems — the kind where a junior developer would hand it to a senior engineer — this is the difference between a mediocre solution and an elegant one.

---

## 3. SKILLS & PLUGINS

### 3.1 What Skills Are and How They Work

Here is where Claude Code stops being a smart terminal and starts being something you actually build.

Skills are reusable instruction sets that teach Claude Code how to perform specific tasks. They are markdown files with frontmatter that define when and how to activate. Write a skill once, and Claude automatically follows it every time you do that type of work — no re-explaining, no repeating yourself, no inconsistency.

Think of skills as the specialized subroutines in your Iron Man suit. The suit knows how to fly. It knows how to fire repulsors. You do not explain those things every time you need them. They are just... capabilities.

**Skill file anatomy:**

```markdown
---
name: "database-migration"
description: "Create and run database migrations safely"
triggers:
  - "migration"
  - "schema change"
  - "alter table"
globs:
  - "prisma/**"
  - "migrations/**"
---

# Database Migration Skill

When creating database migrations, follow these rules:

## Pre-migration checklist
1. Check if the migration is backward-compatible
2. Ensure no data loss occurs
3. Test the migration on a copy of production data

## Migration steps
1. Create the migration file: `npx prisma migrate dev --name <descriptive-name>`
2. Review the generated SQL in prisma/migrations/
3. Test rollback: verify the down migration works
4. Run lint: `npx prisma validate`

## Naming conventions
- Use snake_case: `add_user_email_index`
- Prefix with action: `add_`, `remove_`, `alter_`, `create_`

## Safety rules
- NEVER drop a column in the same release that stops writing to it
- ALWAYS add new columns as nullable first
- Create indexes CONCURRENTLY on large tables
```

**Triggers:** Skills activate automatically when your prompt matches the trigger keywords or when you work in files matching the glob patterns. You can also invoke them explicitly with slash commands.

The first time Claude automatically applies your migration safety rules without you asking — because you mentioned "schema change" and the skill kicked in — you will understand why this matters.

### 3.2 Creating Custom Skills

The real leverage comes from building skills for your specific workflow. Not generic "best practices" — your team's actual patterns, your codebase's specific conventions, your production environment's specific requirements.

**Step 1: Create the skill file.**

Skills live in your project's `.claude/skills/` directory or globally in `~/.claude/skills/`.

```bash
mkdir -p .claude/skills
```

**Step 2: Write the skill.**

`.claude/skills/api-endpoint.md`:

```markdown
---
name: "create-api-endpoint"
description: "Scaffold a new API endpoint following project conventions"
triggers:
  - "new endpoint"
  - "new api route"
  - "create route"
---

# API Endpoint Creation

When creating a new API endpoint:

## File structure
Create the following files:
- `src/app/api/<resource>/route.ts` — the route handler
- `src/app/api/<resource>/schema.ts` — zod validation schemas
- `src/app/api/<resource>/__tests__/route.test.ts` — tests

## Route handler template
Use the withAuth wrapper and validate all inputs:
- Parse request body with zod schema
- Return typed responses using the ApiResponse type
- Log all operations with structured metadata
- Handle errors with the AppError class

## Required test cases
Every endpoint needs tests for:
- Happy path (valid input, authorized user)
- Invalid input (schema validation failures)
- Unauthorized access (missing or invalid auth)
- Not found (requested resource does not exist)
- Edge cases specific to the business logic
```

One workflow that changed how I think about skill creation: when you catch yourself writing the same instructions in your prompts more than twice, that is a skill waiting to be written. Extract it. The third time you need it, it just works.

### 3.3 Plugin System

**Plugins** extend Claude Code with additional capabilities: custom agents, hooks, commands, and skills bundled together. If skills are individual capabilities, plugins are the full armor sets — everything you need for a particular workflow, packaged and shareable.

**Plugin structure:**

```
my-plugin/
├── plugin.json          # Plugin manifest
├── hooks/
│   ├── pre-commit.sh    # Hook scripts
│   └── lint-check.sh
├── skills/
│   └── deploy.md        # Skill files
└── commands/
    └── deploy.sh        # Custom commands
```

**Plugin manifest (`plugin.json`):**

```json
{
  "name": "acme-dev-tools",
  "version": "1.0.0",
  "description": "Development tools for the Acme platform",
  "hooks": {
    "PreToolUse": [
      {
        "tool": "Write",
        "command": "./hooks/lint-check.sh"
      }
    ],
    "PostToolUse": [
      {
        "tool": "Bash",
        "command": "./hooks/post-command.sh"
      }
    ]
  },
  "skills": [
    "./skills/deploy.md",
    "./skills/database.md"
  ],
  "commands": {
    "deploy": "./commands/deploy.sh"
  }
}
```

Plugins are how you share your Claude Code setup with your team. Your carefully tuned hooks, your battle-tested skills, your custom commands — bundled into one thing that anyone on the team can install and immediately benefit from.

### 3.4 Hook System

Hooks are where Claude Code goes from a useful tool to an enforcer of your standards. They let you run custom code at specific points in Claude Code's execution — before writes, after edits, when sessions start, when Claude finishes responding.

This is the automation layer. And it is more powerful than it sounds.

**Available hook types:**

| Hook | When it fires | Use case |
|---|---|---|
| `PreToolUse` | Before Claude uses a tool | Validate edits, block dangerous commands |
| `PostToolUse` | After Claude uses a tool | Auto-lint after edits, log actions |
| `SessionStart` | When a session begins | Load environment, check prerequisites |
| `Stop` | When Claude finishes responding | Run tests, format output |

**Configuring hooks in `settings.json`:**

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "tool": "Write",
        "command": "echo 'APPROVE' && npm run lint --fix $CLAUDE_FILE_PATH"
      },
      {
        "tool": "Bash",
        "command": "if echo \"$CLAUDE_TOOL_INPUT\" | grep -q 'rm -rf'; then echo 'REJECT: dangerous command blocked'; else echo 'APPROVE'; fi"
      }
    ],
    "PostToolUse": [
      {
        "tool": "Edit",
        "command": "npx prettier --write $CLAUDE_FILE_PATH 2>/dev/null; echo 'APPROVE'"
      }
    ],
    "SessionStart": [
      {
        "command": "echo 'Checking environment...' && node scripts/check-env.js"
      }
    ],
    "Stop": [
      {
        "command": "npm run typecheck 2>&1 | tail -20"
      }
    ]
  }
}
```

That `Stop` hook that runs typechecking after every Claude response is subtle but transformative. Claude writes some code. The hook immediately runs the type checker. If there are errors, Claude sees them and fixes them — before you even look at the output. By the time Claude says it is done, the types are clean.

**Hook environment variables available:**

- `$CLAUDE_FILE_PATH` — the file being read/written
- `$CLAUDE_TOOL_INPUT` — the raw input to the tool
- `$CLAUDE_TOOL_NAME` — the name of the tool being used
- `$CLAUDE_SESSION_ID` — current session identifier

**Practical hook example — auto-format on every file edit:**

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "tool": "Edit",
        "command": "npx prettier --write $CLAUDE_FILE_PATH && echo 'APPROVE'"
      },
      {
        "tool": "Write",
        "command": "npx prettier --write $CLAUDE_FILE_PATH && echo 'APPROVE'"
      }
    ]
  }
}
```

With this hook in place, every file Claude touches is automatically formatted. No more "Claude generated perfectly correct code but in the wrong style." It just comes out right.

The `REJECT` pattern in the PreToolUse hook is worth calling out specifically. When your hook outputs `REJECT:` followed by a message, Claude Code cancels the operation and tells Claude why it was blocked. You have built a guardrail directly into the tool's execution model. No prompting required.

### 3.5 MCP (Model Context Protocol) Server Integration

**What MCP is:** The Model Context Protocol is a standard for connecting AI assistants to external tools and data sources. MCP servers expose tools that Claude Code can use — databases, APIs, file systems, third-party services, and more.

**Why it matters:** MCP turns Claude Code from a code-only assistant into a full workflow automation tool. It can query your database, read your Linear tickets, send Slack messages, check your Figma designs, and deploy your application — all from the same conversation. The suit gains new capabilities with every MCP server you connect.

Consider what this means in practice: you are debugging a customer issue. You ask Claude to look at the error logs (filesystem MCP), query the user's account state (database MCP), check the relevant Linear ticket (Linear MCP), and read the Figma design for the affected feature (Figma MCP) — all without leaving the conversation. Everything in one place.

**Configuring MCP servers:**

MCP servers are configured in your Claude Code settings file (`.claude/settings.json` or `~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres"],
      "env": {
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/mydb"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    },
    "slack": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-server-slack"],
      "env": {
        "SLACK_BOT_TOKEN": "${SLACK_BOT_TOKEN}"
      }
    },
    "linear": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-server-linear"],
      "env": {
        "LINEAR_API_KEY": "${LINEAR_API_KEY}"
      }
    }
  }
}
```

### 3.6 Setting Up MCP Servers for External Tools

**Database access (PostgreSQL):**

```bash
# Install the MCP server
npm install -g @modelcontextprotocol/server-postgres

# Now Claude can run queries directly:
> What are the top 10 users by order count in the last 30 days?
# Claude uses the MCP server to query the database and returns results
```

The first time you ask Claude a data question in plain English and it runs the actual query against your actual database and gives you a real answer — in the same conversation where you were discussing the code — it feels like magic. It is not magic. It is MCP.

**Figma integration:**

```json
{
  "mcpServers": {
    "figma": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-server-figma"],
      "env": {
        "FIGMA_ACCESS_TOKEN": "${FIGMA_ACCESS_TOKEN}"
      }
    }
  }
}
```

```
> Look at this Figma design: https://figma.com/design/abc123/MyDesign?node-id=1:2
  and implement it as a React component using our existing design system.
```

Design-to-code in one command. Claude reads the Figma design, understands your design system from CLAUDE.md, and produces a component that looks right and follows your conventions. The gap between design and code — the thing that takes junior developers a week and senior developers an afternoon — starts to collapse.

**Custom MCP server (for your own internal APIs):**

You can build your own MCP server to expose any tool or API. This is where the real customization happens — connecting Claude to the systems that are unique to your organization.

```typescript
// my-mcp-server.ts
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const server = new Server({
  name: "my-internal-tools",
  version: "1.0.0",
}, {
  capabilities: { tools: {} },
});

server.setRequestHandler("tools/list", async () => ({
  tools: [{
    name: "get_feature_flags",
    description: "Get current feature flag configuration",
    inputSchema: {
      type: "object",
      properties: {
        environment: { type: "string", enum: ["dev", "staging", "prod"] }
      },
      required: ["environment"]
    }
  }]
}));

server.setRequestHandler("tools/call", async (request) => {
  if (request.params.name === "get_feature_flags") {
    const env = request.params.arguments.environment;
    const flags = await fetchFeatureFlags(env);
    return { content: [{ type: "text", text: JSON.stringify(flags, null, 2) }] };
  }
});

const transport = new StdioServerTransport();
await server.connect(transport);
```

Once you have built one custom MCP server — wrapping an internal API, your deployment system, your feature flag service — you will not stop. Every internal tool you connect multiplies Claude's effectiveness in your specific environment. This is how you build a suit that fits you, not a generic suit off the rack.

---

## 4. AGENT TEAMS & ORCHESTRATION

### 4.1 Designing Multi-Agent Workflows

Here is a thought experiment: if you could hire five brilliant engineers who all had perfect knowledge of your codebase and could work simultaneously without stepping on each other — what would you give them to do?

That is the question multi-agent orchestration asks you to answer. And the answer matters, because you can actually do it.

**The orchestrator-specialist pattern:** For complex tasks, use Claude Code as an orchestrator that dispatches specialist subagents for focused work.

```
┌─────────────────────────────────┐
│       ORCHESTRATOR AGENT        │
│  (understands the full picture) │
└──────────┬──────────────────────┘
           │
    ┌──────┴──────┬───────────┬──────────────┐
    ▼             ▼           ▼              ▼
┌────────┐ ┌──────────┐ ┌─────────┐ ┌────────────┐
│ Code   │ │ Test     │ │ Review  │ │ Deploy     │
│ Agent  │ │ Agent    │ │ Agent   │ │ Agent      │
│        │ │          │ │         │ │            │
│ Writes │ │ Writes   │ │ Reviews │ │ Handles    │
│ impl   │ │ tests    │ │ code &  │ │ CI/CD &    │
│ code   │ │ & fixes  │ │ finds   │ │ deployment │
│        │ │ failures │ │ issues  │ │            │
└────────┘ └──────────┘ └─────────┘ └────────────┘
```

**Example orchestration prompt:**

```
> I need to add a new "Teams" feature. Here is the spec:
  - Users can create teams
  - Teams have members with roles (owner, admin, member)
  - Teams can be associated with projects

  Please coordinate this as follows:
  1. First, create the database schema and migration
  2. Then, in parallel:
     a. Implement the API endpoints
     b. Implement the frontend components
  3. After both complete, write integration tests
  4. Finally, review all changes for issues
```

The Teams feature that would take a solo developer two weeks just became a structured multi-agent project with clear handoffs, parallel work, and built-in review. Your job is to write the spec, review the outputs, and unblock anything that gets stuck. The agents handle the execution.

### 4.2 When to Use Subagents vs Main Conversation

**Use the main conversation when:**

- Tasks are sequential and depend on each other
- You need to have an ongoing dialogue about approach
- The task requires seeing the full picture across multiple files
- You are debugging and need to follow a chain of causation

**Use subagents when:**

- Tasks are independent and can run in parallel
- Each task is self-contained (e.g., adding validation to separate routes)
- You want to explore multiple approaches simultaneously
- The work is spread across unrelated parts of the codebase

The intuition is simple: if the tasks are coupled, keep them in one conversation where Claude can see the full picture. If they are independent, fan them out. The constraint is context, not capability — keeping independent work in one conversation just burns context without adding value.

### 4.3 Parallel Agent Dispatch

**Pattern: Fan-out, fan-in.**

```
> I need to update our error handling across the codebase.
  The following modules are independent — handle them in parallel:

  1. src/api/ — Add structured error responses to all route handlers
  2. src/workers/ — Add retry logic with exponential backoff to all workers
  3. src/lib/database/ — Add connection retry and query timeout handling
  4. src/lib/external/ — Add circuit breaker pattern to all external API calls

  Each module should follow the error handling conventions in CLAUDE.md.
  After all agents complete, summarize what was changed.
```

The fan-out phase dispatches four agents simultaneously. The fan-in phase brings results together, compares them for consistency, and gives you a unified summary. A codebase-wide change that would have taken a whole sprint becomes an afternoon.

This is the workflow that will make you feel like you have hired a team. Because you have.

### 4.4 Agent Isolation with Worktrees

**The worktree-per-agent pattern** is the most robust approach for parallel development. It gives each agent complete isolation — not just context isolation, but filesystem isolation. Each agent works in its own directory on its own branch.

```bash
# Setup: create worktrees for each feature
git worktree add ../app-teams feature/teams
git worktree add ../app-billing feature/billing
git worktree add ../app-notifications feature/notifications

# Run agents in separate terminals (or background)
# Terminal 1
cd ../app-teams && claude "implement the Teams feature per the spec"

# Terminal 2
cd ../app-billing && claude "implement the billing dashboard"

# Terminal 3
cd ../app-notifications && claude "implement the notification system"
```

**Benefits:**

- Zero risk of agents stepping on each other's files
- Each agent has full autonomy to edit, test, and commit
- Merge conflicts are handled at PR review time, not during development
- You can review each feature independently

The first time you run three Claude Code instances in three worktrees simultaneously, look at your terminal layout for a moment. Three separate engineering streams, all running in parallel, all under your direction. That is an engineering team. That is the suit.

### 4.5 Communication Between Agents

Agents can communicate via the `SendMessage` mechanism — the orchestrator can send instructions and context to subagents, and subagents report back.

**Pattern: Pass context between agents via files.**

```
> Agent 1: Generate the database schema for the Teams feature and write
  it to docs/teams-schema.md when done.

> Agent 2: Read docs/teams-schema.md and implement the API endpoints
  that match the schema.

> Agent 3: Read docs/teams-schema.md and implement the frontend
  components with TypeScript types matching the schema.
```

This file-based communication pattern works because all agents share the same filesystem (or can share files between worktrees). The schema document becomes the contract that coordinates their work — no real-time communication needed, just well-defined intermediate artifacts.

### 4.6 Real-World Patterns

**Pattern 1: Code review agent.**

```
> Review the changes in this PR branch compared to main. For each file:
  1. Check for bugs, race conditions, and security issues
  2. Verify error handling is comprehensive
  3. Check that tests cover the new code paths
  4. Flag any performance concerns

  Format your review as GitHub PR comments with file:line references.
```

**Pattern 2: Test runner agent.**

```
> Run the test suite. For any failing tests:
  1. Determine if the test or the implementation is wrong
  2. If the implementation is wrong, fix it
  3. If the test is wrong (e.g., outdated assertion), fix the test
  4. Re-run until all tests pass
  5. Report what you changed and why
```

The test runner pattern changed how I handle test failures. Instead of the old cycle — run tests, see failures, read test output, figure out what broke, fix it, repeat — I just hand it to an agent. The agent runs the suite, reads the failures, traces the cause, fixes the issue, verifies the fix, and reports back. I review the changes and the summary. That loop closes in minutes instead of hours.

**Pattern 3: Deployment agent.**

```
> Prepare this branch for deployment:
  1. Run all tests — fix any failures
  2. Run the linter — fix any issues
  3. Run the type checker — fix any errors
  4. Update the CHANGELOG.md with the changes in this branch
  5. Create a commit with all fixes
  6. Create a PR with a structured description
```

---

## 5. CONFIGURATION & CUSTOMIZATION

### 5.1 settings.json Configuration

The `settings.json` file controls Claude Code's behavior. It can exist at multiple levels:

```
~/.claude/settings.json              # Global settings
~/projects/my-app/.claude/settings.json    # Project settings (override global)
```

Project settings override global settings, which lets you have different defaults for different types of projects — stricter permissions on production codebases, more permissive settings on personal experiments.

**Comprehensive settings.json example:**

```json
{
  "model": "claude-opus-4-0",
  "permissions": {
    "allow": [
      "Read",
      "Glob",
      "Grep",
      "LSP"
    ],
    "deny": [
      "Bash(rm -rf *)",
      "Bash(git push --force)"
    ]
  },
  "hooks": {
    "PostToolUse": [
      {
        "tool": "Edit",
        "command": "npx prettier --write $CLAUDE_FILE_PATH 2>/dev/null; echo 'APPROVE'"
      }
    ],
    "Stop": [
      {
        "command": "npm run typecheck --silent 2>&1 | tail -5"
      }
    ]
  },
  "mcpServers": {
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres"],
      "env": {
        "DATABASE_URL": "${DATABASE_URL}"
      }
    }
  },
  "env": {
    "NODE_ENV": "development",
    "DEBUG": "app:*"
  }
}
```

The `deny` list in permissions is where you add your hard guardrails. Force push and recursive delete are the classics. Add anything your organization would consider a firing offense if done accidentally.

### 5.2 CLAUDE.md Files: Project-Level Instructions

**Best practices for CLAUDE.md files:**

1. **Keep it concise.** CLAUDE.md is loaded into context every session. Every line costs tokens. Be ruthless about cutting anything that is not genuinely useful for Claude.
2. **Focus on what is non-obvious.** Do not document standard conventions (like "use const instead of let") — Claude already knows those. Document your project-specific decisions, the ones a new engineer would get wrong on their first week.
3. **Include the commands Claude needs.** Test commands, build commands, lint commands — anything Claude should run. Do not make Claude guess.
4. **Update it as the project evolves.** Treat CLAUDE.md like living documentation. When you add a new tool or change a convention, update it immediately.

**Anti-patterns:**

```markdown
# BAD: Too verbose, states the obvious
- Use TypeScript
- Write clean code
- Follow best practices
- Use meaningful variable names

# GOOD: Project-specific, actionable
- Use the AppError class for all error handling (src/lib/errors.ts)
- Database queries must go through the repository pattern in src/repos/
- All API responses use the envelope format: { data, error, meta }
- Run `make check` before committing — it runs lint, typecheck, and tests
```

The "obvious" test: if a competent engineer who had never seen your codebase would know it without being told, cut it. If they would have to read your code or ask a teammate to know it, keep it.

### 5.3 Per-Directory CLAUDE.md for Monorepos

In monorepos, each package or app can have its own CLAUDE.md:

```
monorepo/
├── CLAUDE.md                          # Root: shared conventions
├── packages/
│   ├── ui/
│   │   └── CLAUDE.md                  # UI library conventions
│   ├── api/
│   │   └── CLAUDE.md                  # API service conventions
│   └── shared/
│       └── CLAUDE.md                  # Shared utilities conventions
└── apps/
    ├── web/
    │   └── CLAUDE.md                  # Web app conventions
    └── mobile/
        └── CLAUDE.md                  # Mobile app conventions
```

**Root CLAUDE.md (shared):**

```markdown
# Acme Monorepo

## Structure
- packages/: Shared libraries
- apps/: Deployable applications
- All packages use TypeScript strict mode
- Package manager: pnpm
- Build system: Turborepo

## Commands
- pnpm install          — install all dependencies
- pnpm build            — build all packages
- pnpm test             — run all tests
- pnpm lint             — lint everything
- turbo run build --filter=@acme/api  — build specific package
```

**Package-level CLAUDE.md (`packages/ui/CLAUDE.md`):**

```markdown
# @acme/ui — Component Library

## Adding a new component
1. Create src/components/<ComponentName>/index.tsx
2. Create src/components/<ComponentName>/<ComponentName>.stories.tsx
3. Export from src/index.ts
4. All components must accept a className prop for style overrides
5. Use CVA (class-variance-authority) for variant management

## Testing
- pnpm --filter @acme/ui test
- pnpm --filter @acme/ui storybook  (visual testing)
```

In a large monorepo with multiple teams, per-directory CLAUDE.md files mean each team's conventions are automatically active when Claude works in their area. No need to remind Claude "by the way, the UI package does things differently from the API service." It just knows, because the file is right there.

### 5.4 Keybindings Customization

Claude Code supports customizing keybindings for common actions:

```json
// ~/.claude/keybindings.json
{
  "ctrl+k": "clear",
  "ctrl+p": "compact",
  "ctrl+r": "/review",
  "ctrl+s": "/commit"
}
```

`ctrl+s` for commit feels natural if you are used to saving files. `ctrl+r` for review is a natural extension. Customize these to match your muscle memory, not the defaults.

### 5.5 Model Selection: Opus, Sonnet, Haiku

**Choosing the right model:**

| Model | Speed | Cost | Best for |
|---|---|---|---|
| **Haiku** | Fastest | Lowest | Simple edits, file renames, formatting, boilerplate generation |
| **Sonnet** | Medium | Medium | Most daily coding tasks, test writing, debugging straightforward issues |
| **Opus** | Slowest | Highest | Architecture decisions, complex debugging, multi-file refactoring, security review |

Model selection is a skill in itself. The instinct is to always use the most capable model — why would you use a weaker one? But the cost-speed tradeoffs are real, and for routine tasks Haiku is genuinely fast enough. Spending Opus on adding a TypeScript interface is like hiring a principal engineer to write HTML labels.

**Switching models mid-session:**

```
> /model sonnet

# Or specify at start
claude --model claude-sonnet-4-20250514
```

**Cost-optimization strategy:**

1. Start complex tasks with Opus for planning and architecture
2. Switch to Sonnet for implementation
3. Use Haiku for repetitive tasks (formatting, renaming, boilerplate)

```
> /model opus
> Plan the architecture for migrating our monolith to microservices.

> /model sonnet
> Implement phase 1 of the migration plan.

> /model haiku
> Add TypeScript interfaces for all 20 API response types.
```

---

## 6. WORKFLOW PATTERNS FOR 100x PRODUCTIVITY

### 6.1 The Brainstorm-Plan-Implement-Review-Commit Cycle

This is the core workflow that turns Claude Code from a chatbot into a productive engineering partner. Not a shortcut — a discipline. The engineers who get the most out of Claude Code are the ones who internalize this cycle and run it consistently.

**Step 1: Brainstorm (5 minutes)**

```
> I need to add rate limiting to our API. What are the options?
  Consider: our infrastructure (Vercel + Redis), traffic patterns
  (~1000 req/s peak), and that we need per-user and global limits.
```

**Step 2: Plan (10 minutes)**

```
> Let us go with the sliding window approach using Redis.
  Create a detailed implementation plan. Include:
  - File changes needed
  - The rate limiting algorithm
  - How to handle distributed rate limiting across serverless functions
  - Configuration format
  - Testing strategy
```

**Step 3: Implement (Claude does this)**

```
> Implement the plan. Start with the core rate limiter, then the middleware,
  then the configuration. Run tests after each major piece.
```

**Step 4: Review**

```
> /review
> Also specifically check: Is the Redis connection handling correct for
  serverless? Are there race conditions in the sliding window calculation?
```

**Step 5: Commit**

```
> /commit
```

The temptation is to skip the brainstorm and plan steps and jump straight to implement. Resist it. The time you spend in Steps 1 and 2 is not overhead — it is the thing that makes Steps 3 and 4 actually work. A well-planned task implemented by Claude takes an hour. An unplanned task implemented by Claude takes an hour plus the time to fix all the wrong decisions it made without adequate guidance.

### 6.2 TDD with Claude: Tests First, Then Implementation

Test-driven development has always been slightly idealistic — in practice, writing tests before code requires discipline and time that teams often do not have. Claude Code changes the economics. Writing tests is now cheap. The hard part is writing the right tests, which is where your judgment still matters.

**The TDD workflow with Claude Code:**

```
> I need a function that validates email addresses according to RFC 5322.
  Write the tests first. Cover:
  - Valid simple emails
  - Valid emails with subdomains
  - Valid emails with special characters
  - Invalid emails (missing @, missing domain, etc.)
  - Edge cases (very long local parts, unicode, etc.)

  Do NOT write the implementation yet.
```

After reviewing the tests:

```
> Good tests. Now implement the validateEmail function to make all tests pass.
  Run the tests after implementation to verify.
```

**Why this works with Claude Code:** Claude can run the tests directly and iterate until they pass. You get to review the test cases — which define the behavior — before any implementation code exists. If the tests are wrong, you catch it before Claude spends time implementing the wrong thing. The tests become your specification.

The pattern that makes this sticky: you end up with tests that actually describe the intended behavior, not tests that were written to pass the already-written implementation. The quality difference is substantial.

### 6.3 Debugging Workflow

Debugging is the workflow where Claude Code's ability to read files, run commands, and make targeted changes really shines. No more context-switching between the terminal, your editor, and your browser. Everything happens in one place.

**Systematic debugging with Claude Code:**

```
> The /api/checkout endpoint is returning 500 errors intermittently.
  Debug this systematically:

  1. Read the route handler and all its dependencies
  2. Check the error logs (run: tail -100 logs/app.log)
  3. Identify potential failure points
  4. Add targeted logging to narrow down the issue
  5. Check for race conditions or state management issues
  6. Propose and implement a fix
  7. Add a test that reproduces the bug
  8. Verify the fix passes the new test
```

Notice the last two steps. The fix is not done when the error stops. The fix is done when there is a failing test that captures the bug and a passing test that verifies the fix. That is the only way to know you have actually fixed it and not just masked it.

**For production issues:**

```
> We are seeing increased latency on the /api/search endpoint.

  1. Read the search implementation
  2. Check if there are N+1 query issues
  3. Look at the database indexes for the search tables
  4. Check if any queries are missing indexes (run EXPLAIN on the main queries)
  5. Profile the endpoint: add timing logs around each major operation
  6. Propose optimizations ranked by expected impact
```

The "ranked by expected impact" at the end is important. You want a prioritized list, not a dump of every possible optimization. Make Claude do the prioritization work — it is good at it.

### 6.4 Code Review Workflow

The code review workflow is one of the highest-leverage things Claude Code can do for your team. A thorough review that would take a senior engineer forty-five minutes takes Claude two minutes.

**Requesting a review from Claude:**

```
> Review the changes I have made on this branch compared to main.
  Be thorough. Specifically check:

  1. Logic errors and edge cases
  2. Security vulnerabilities (injection, auth bypass, data exposure)
  3. Performance issues (N+1 queries, unnecessary re-renders, memory leaks)
  4. Error handling completeness
  5. Test coverage gaps
  6. Naming and readability

  For each issue found, rate severity (critical/warning/nit) and
  suggest a specific fix.
```

The severity rating is the key detail. Not all feedback is equal, and a flat list of issues makes it hard to prioritize. "Critical" means do not ship without fixing this. "Warning" means you should probably fix it but it is a judgment call. "Nit" means a suggestion if you have time.

**Reviewing someone else's PR:**

```
> Review PR #142 on GitHub. Read all changed files and provide a
  structured review. Focus on correctness and security — this PR
  modifies the authentication flow.
```

Use Claude review as a first pass before you read the PR yourself. It will catch the obvious stuff — the missing null checks, the off-by-one errors, the test gaps — so your human review time can focus on the judgment calls that actually require human judgment.

### 6.5 Large Refactoring: Plans + Parallel Agents

Large refactoring is where solo developers lose days and teams lose sprints. The problem is not knowing what needs to change — it is the sheer volume of coordinated work required, and the risk of getting halfway through and breaking things.

Claude Code changes the calculus on both fronts.

**Example: Migrating from REST to GraphQL.**

```
# Phase 1: Plan (use Opus)
> Analyze our REST API in src/api/ and create a migration plan to GraphQL.
  Map each REST endpoint to a GraphQL query/mutation. Identify shared
  types and resolvers. Plan the migration in phases where each phase
  is independently deployable.

# Phase 2: Scaffold (use Sonnet)
> Create the GraphQL schema based on the migration plan. Set up the
  Apollo Server configuration. Create type definitions for all entities.

# Phase 3: Parallel implementation (use subagents)
> Implement the following resolvers in parallel — they are independent:
  - User resolvers (queries + mutations)
  - Product resolvers (queries + mutations)
  - Order resolvers (queries + mutations)
  - Payment resolvers (queries + mutations)

# Phase 4: Integration (use main conversation)
> Wire up all resolvers. Add the GraphQL playground in development.
  Run the full test suite. Fix any integration issues.

# Phase 5: Review
> Review the entire GraphQL migration. Check for:
  - N+1 query issues in resolvers (need DataLoader?)
  - Authorization checks on every resolver
  - Input validation on every mutation
  - Consistent error handling
```

The "independently deployable phases" requirement in Phase 1 is not incidental. It is the constraint that keeps you safe during the migration. If each phase can be deployed without breaking anything, the refactoring is not a big-bang rewrite — it is an incremental replacement. Much safer. Much easier to review. Much easier to roll back if something goes wrong.

This is the pattern that turns a "we cannot refactor this, it is too risky" codebase into a "we migrated it over three sprints" success story.

### 6.6 PR Workflow

**The complete PR workflow:**

```
# 1. Commit changes
> /commit

# 2. Push and create PR
> Push this branch and create a PR. The PR should target main.
  Include a summary of changes, testing instructions, and any
  deployment considerations.

# Claude will:
# - Push the branch
# - Create a PR with structured title and body
# - Include a test plan
# - Return the PR URL
```

**Example of what Claude generates for a PR:**

```markdown
## Summary
- Add rate limiting middleware using Redis sliding window algorithm
- Support per-user and global rate limits with configurable thresholds
- Add rate limit headers (X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset)

## Test plan
- [ ] Unit tests pass: `npm test -- --grep "rate-limit"`
- [ ] Integration test with Redis: `npm run test:integration`
- [ ] Manual test: send 100+ requests rapidly and verify 429 responses
- [ ] Verify rate limit headers are present on all responses
- [ ] Test behavior when Redis is unavailable (should fail open)
```

The test plan is the underrated part. A Claude-generated PR has not just the code and the description — it has explicit, checkable verification steps for reviewers. That makes reviews faster, more thorough, and less likely to miss edge cases.

### 6.7 Codebase Exploration

The first session in an unfamiliar codebase is one of the highest-value uses of Claude Code. Instead of spending two days reading through directories and tracing data flows, you spend twenty minutes asking questions and getting structured answers.

**Understanding an unfamiliar codebase:**

```
> I just joined this project. Give me a high-level architecture overview:
  1. What framework and language is this?
  2. What is the directory structure and what does each top-level dir do?
  3. How does data flow from frontend to database?
  4. What external services does this integrate with?
  5. Where are the main business logic modules?
  6. How is authentication and authorization handled?
  7. What is the testing strategy?
```

**Deep-diving into a specific area:**

```
> I need to understand how the payment system works.
  Trace the flow from when a user clicks "Pay" to when the payment
  is confirmed. Show me every file involved and explain each step.
```

Two years ago, onboarding to a new codebase meant reading code for days, asking teammates questions they barely had time to answer, and still feeling lost for weeks. Now it means an hour with Claude, targeted follow-up questions, and a working mental model by lunchtime. This alone changes the economics of team transitions and knowledge transfer.

### 6.8 Documentation Generation

```
> Generate API documentation for all endpoints in src/app/api/.
  For each endpoint:
  - HTTP method and path
  - Description of what it does
  - Request body schema (with examples)
  - Response schema (with examples for success and error cases)
  - Authentication requirements
  - Rate limiting details

  Output as an OpenAPI 3.0 spec in docs/openapi.yaml.
```

Documentation is the thing that teams always say they will do and then do not because it takes time that could be spent shipping. Claude Code removes most of that friction. The code is the source of truth — Claude reads it and generates the documentation. The only thing you need to do is review it for accuracy.

---

## 7. CLAUDE CODE IN TEAM ENVIRONMENTS

### 7.1 Shared CLAUDE.md for Team Conventions

**The team CLAUDE.md should be committed to version control.** It serves as executable documentation that both humans and Claude follow. This is one of the highest-leverage things a team can do when adopting Claude Code — the configuration work you do once benefits everyone on the team in every session.

Think of it as the team's culture, written down in a format that both your engineers and your AI agent can act on.

**What to include in a team CLAUDE.md:**

```markdown
# Team Engineering Standards

## Git Workflow
- Branch naming: feature/, bugfix/, hotfix/, chore/
- Commit messages: conventional commits (feat:, fix:, chore:, docs:, test:)
- All PRs require at least one approval
- Squash merge to main

## Code Review Checklist
Before requesting review, verify:
- [ ] All tests pass (`npm test`)
- [ ] No lint errors (`npm run lint`)
- [ ] No type errors (`npm run typecheck`)
- [ ] New code has test coverage
- [ ] API changes are backward-compatible
- [ ] Database migrations are reversible

## Architecture Decision Records
- ADRs live in docs/adr/
- Use the template in docs/adr/template.md
- All significant architectural decisions must have an ADR

## Deployment
- main branch auto-deploys to staging
- Production deploys require manual approval via GitHub Actions
- Feature flags for all user-facing changes (see src/lib/flags.ts)
```

When the team CLAUDE.md is good, onboarding a new engineer means pointing them at it as much as it means onboarding them to Claude Code. The two are complementary. The conventions in the file apply whether a human is making a change or an agent is.

### 7.2 Hooks for Enforcing Standards

Hooks are how you move team standards from "things we agreed to do" to "things that happen automatically." You stop relying on individual discipline and start relying on the system.

**Auto-lint hook (runs after every edit):**

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "tool": "Edit",
        "command": "npx eslint --fix $CLAUDE_FILE_PATH 2>/dev/null; npx prettier --write $CLAUDE_FILE_PATH 2>/dev/null; echo 'APPROVE'"
      }
    ]
  }
}
```

**Pre-commit verification hook (runs before committing):**

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "tool": "Bash",
        "command": "if echo \"$CLAUDE_TOOL_INPUT\" | grep -q 'git commit'; then npm run lint && npm run typecheck && npm test -- --bail; fi; echo 'APPROVE'"
      }
    ]
  }
}
```

That pre-commit hook is doing something important: it ensures that before Claude can commit, the linter, type checker, and test suite all pass. Not as a reminder. As a hard gate. Claude cannot commit broken code even if it tries to. The standards are enforced at the tool level, not the social level.

This is how you get consistent quality without constant vigilance.

### 7.3 CI Integration: Running Claude Code in CI Pipelines

Claude Code is not just a developer tool — it is a CI tool. Running it in your pipelines gets you automated review, automated test fixing, and automated quality gates on every PR.

**GitHub Actions example:**

```yaml
# .github/workflows/ai-review.yml
name: AI Code Review
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  ai-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Install Claude Code
        run: npm install -g @anthropic-ai/claude-code

      - name: Run AI Review
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          claude --accept-all --model claude-sonnet-4-20250514 \
            "Review the changes in this PR compared to the base branch. \
             Output a structured review as a GitHub comment. \
             Focus on bugs, security issues, and test coverage gaps."
```

**Automated test fixing in CI:**

```yaml
  ai-fix-tests:
    runs-on: ubuntu-latest
    if: failure()
    needs: test
    steps:
      - uses: actions/checkout@v4
      - name: AI Fix Failing Tests
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          claude --accept-all --model claude-sonnet-4-20250514 \
            "Tests are failing. Read the test output, identify the failures, \
             fix the issues, and commit the fixes."
```

The automated test fixing pipeline is the one that generates the most interesting conversations when people see it. "Wait, if the CI fails, Claude just... fixes it?" Yes. On the next run, the tests pass. The developer gets a notification that their branch had failing tests and Claude fixed them, with a commit showing what changed. They review the commit and merge.

CI with Claude Code is not just faster feedback — it is feedback plus automatic remediation. You are building a self-healing pipeline.

See Chapter 14's section on AI in CI/CD pipelines for the deeper architectural context behind this pattern, and Chapter 36 for examples of teams running this at scale.

### 7.4 Best Practices for AI-Generated Code in Team Reviews

**For the developer using Claude Code:**

1. **Always review Claude's output before committing.** Claude is a collaborator, not a substitute for your judgment. The code might be functionally correct and still be wrong for your context.
2. **Run the full test suite.** Claude may introduce subtle regressions in files it did not directly modify.
3. **Check for hallucinated APIs.** Claude sometimes uses methods or libraries that do not exist or uses incorrect signatures. If a function call looks unfamiliar, verify it.
4. **Verify security-sensitive code manually.** Authentication, authorization, encryption, and input validation deserve human review every single time. No exceptions.

**For the team reviewing AI-assisted PRs:**

1. **Review as normal.** AI-generated code should meet the same standards as human-written code. If anything, hold it to a slightly higher bar because it tends to look confident even when it is subtly wrong.
2. **Pay extra attention to edge cases.** Claude handles happy paths extremely well. Edge cases, error conditions, and boundary behaviors are where to focus your review attention.
3. **Check for over-engineering.** Claude sometimes produces more abstraction than the problem requires. Simpler is usually better.
4. **Verify test assertions are meaningful.** Claude can write tests that pass but do not actually verify the right behavior. Read the assertions, not just the test names.

---

## 8. TIPS & TRICKS

### 8.1 How to Write Effective Prompts for Claude Code

The single biggest variable in Claude Code's output is the quality of your input. Claude Code is not autocomplete — you cannot just start typing and hope it figures out what you want. Think of it like briefing a very capable engineer. The better your brief, the better the result.

**Be specific about what you want:**

```
# BAD: vague
> Fix the bugs

# GOOD: specific
> The user registration endpoint in src/api/auth/register.ts returns
  a 500 error when the email already exists. It should return a 409
  with the message "Email already registered". Fix this and add a test.
```

**Provide context:**

```
# BAD: no context
> Add caching

# GOOD: context-rich
> Add Redis caching to the getProductById function in src/lib/products.ts.
  Cache for 5 minutes. Invalidate when a product is updated via the
  updateProduct function in the same file. We already have a Redis client
  configured in src/lib/redis.ts.
```

**Specify the output format:**

```
> Generate a migration to add a "teams" table. I need:
  1. The Prisma schema changes (in prisma/schema.prisma)
  2. Run prisma migrate dev --name add_teams
  3. A seed script that creates 3 test teams
```

**Use constraints to guide behavior:**

```
> Refactor the authentication middleware. Constraints:
  - Do not change the public API (function signatures must stay the same)
  - Do not add new dependencies
  - Keep backward compatibility with existing session tokens
  - All existing tests must still pass without modification
```

Constraints are the most underused tool in prompting. They narrow the solution space from "everything Claude might try" to "exactly what you need." They prevent the refactor that breaks the public API, the fix that adds a new dependency you did not want, the optimization that changes observable behavior.

### 8.2 When to Be Specific vs When to Let Claude Explore

**Be specific when:**

- You know exactly what you want (fix a specific bug, add a specific field)
- The change is in a critical path (auth, payments, data integrity)
- You have a clear mental model of the solution
- The task involves security-sensitive code

**Let Claude explore when:**

- You are starting on an unfamiliar codebase
- You want to understand trade-offs between approaches
- The problem is ambiguous ("our API is slow" — where exactly?)
- You want creative solutions to a design problem

```
# Exploration prompt (let Claude investigate)
> Our checkout flow has gotten slow. Users are complaining about
  3-4 second load times. Investigate the checkout code path,
  identify bottlenecks, and propose optimizations. Start by
  tracing the request flow and measuring where time is spent.
```

The exploration mode is underrated. When you do not know the answer, Claude often does — or can figure it out faster than you can, because it can read and synthesize a hundred files in the time it takes you to read ten. Use this. Do not force a specific approach when you are not sure what the right approach is.

### 8.3 Managing Long Sessions

**Signs a session is too long:**

- Claude starts repeating itself or forgetting earlier context
- You see context compression warnings
- Responses are noticeably slower
- Claude makes edits that conflict with earlier work in the session

**What to do:**

```
# Option 1: Compact the conversation
> /compact

# Option 2: Start fresh with a summary
> /clear
> Continuing work on the rate limiting feature. So far I have:
  - Implemented the sliding window algorithm in src/lib/rate-limit.ts
  - Added the middleware in src/middleware/rate-limit.ts
  - Tests are passing for the core algorithm
  Next: integrate the middleware into the API routes.

# Option 3: Start a completely new session
# (quit and restart claude in the same directory)
```

The manual summary approach in Option 2 is worth developing as a habit. Writing a two-paragraph summary of what has been done and what is next clarifies your own thinking as much as it helps Claude. If you cannot write a clear summary, that is a sign the session has gotten confused about its own state — which is itself a reason to start fresh.

**Proactive context management:**

- Break large tasks into sessions: planning in one, implementation in another
- Use CLAUDE.md to persist decisions so you do not need to re-explain
- After each major milestone, commit and start fresh

Think of commits not just as version control checkpoints, but as session boundaries. Commit, start a new session, and brief Claude on the current state. You will be more productive and Claude will be more focused.

### 8.4 Cost Management

**Token costs by model (approximate):**

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Typical session cost |
|---|---|---|---|
| Haiku | $0.25 | $1.25 | $0.01 - $0.10 |
| Sonnet | $3.00 | $15.00 | $0.10 - $1.00 |
| Opus | $15.00 | $75.00 | $0.50 - $5.00+ |

**Cost reduction strategies:**

1. **Use the right model for the job.** Do not use Opus for adding a console.log. Do not use Haiku for architectural design. Match the model to the complexity of the task.
2. **Keep CLAUDE.md concise.** Every token in CLAUDE.md is read every session. A bloated CLAUDE.md adds cost to every conversation.
3. **Be specific in prompts.** Vague prompts cause Claude to read more files and try more things. Precise prompts read fewer files and make fewer wrong turns.
4. **Use `/compact` in long sessions** to reduce context size without losing the thread.
5. **Avoid reading entire large files.** Point Claude at specific functions or line ranges when you can.
6. **Batch related changes.** One session that makes 5 related changes is cheaper than 5 separate sessions.

**Monitor costs:**

```
> /cost
# Shows tokens used and estimated cost for the current session
```

The `/cost` command is useful, but the bigger cost optimization is being thoughtful about what work you give to each model. A well-organized Claude Code workflow — Opus for planning, Sonnet for implementation, Haiku for boilerplate — often costs half as much as the same workflow with Opus for everything.

### 8.5 Common Pitfalls and How to Avoid Them

**Pitfall 1: Letting Claude run without review.**

```
# WRONG: fire and forget
claude --accept-all "refactor the entire authentication system"

# RIGHT: review each step
claude "plan a refactoring of the authentication system"
# Review the plan
claude "implement step 1 of the plan"
# Review the implementation
# ... continue
```

The "fire and forget" pattern is tempting because it sounds like maximum automation. It is actually maximum risk. You lose the ability to catch wrong decisions early, when they are cheap to fix. The value is not in having Claude do everything without you — it is in having Claude do everything while you stay in the loop on the decisions that matter.

**Pitfall 2: Not providing enough context.**

```
# WRONG: assumes Claude knows your conventions
> Add a new endpoint

# RIGHT: reference your conventions
> Add a new endpoint for listing user notifications.
  Follow the patterns in src/api/users/route.ts.
  Use the same auth middleware and error handling.
```

**Pitfall 3: Trusting Claude with security-critical code without review.**

Always manually review:
- Authentication and authorization logic
- Cryptographic operations
- SQL queries (especially dynamic ones)
- Input validation and sanitization
- Secret and credential handling

Claude is good at security. It is not infallible. And the cost of a security bug in production is orders of magnitude higher than the cost of reviewing twenty lines of auth code.

**Pitfall 4: Ignoring test failures.**

```
# WRONG
> The tests are failing but the code looks right, just skip them

# RIGHT
> The tests are failing. Read the test output, understand why,
  and fix either the tests or the implementation. Do not skip
  or delete failing tests.
```

Deleting or skipping failing tests is the engineering equivalent of covering the smoke detector because it keeps going off. The test is trying to tell you something. Listen to it.

**Pitfall 5: Overly large single prompts.**

```
# WRONG: everything at once
> Build me an entire e-commerce platform with auth, products,
  cart, checkout, payments, admin panel, and analytics

# RIGHT: incremental
> Let us build an e-commerce platform. Start with the product
  catalog: data model, API endpoints, and a basic listing page.
  We will add features incrementally.
```

Large single prompts lead to large, hard-to-review outputs. Incremental prompts lead to focused changes you can actually evaluate. The incremental approach is not slower — it is actually faster because you catch wrong directions before they propagate across fifty files.

**Pitfall 6: Not using CLAUDE.md.**

If you find yourself repeating the same instructions every session — "use pnpm, not npm", "tests go in `__tests__` directories", "use the AppError class" — put it in CLAUDE.md. That is exactly what it is for. Every repeated instruction is a CLAUDE.md entry waiting to be written.

The moment you realize you have explained your project's conventions to Claude five times, you will wish you had written a CLAUDE.md on day one. Write it on day one.

---

## Quick Reference Card

```
ESSENTIAL COMMANDS
  claude                     Start interactive session
  claude "task"              Start with a task
  claude --plan              Plan mode (read-only)
  claude --model <model>     Select model
  claude --accept-edits      Auto-approve file edits
  claude --accept-all        Auto-approve everything (CI mode)

SESSION COMMANDS
  /help                      Show all commands
  /clear                     Clear context
  /compact                   Compress conversation
  /cost                      Show token usage and cost
  /model <model>             Switch model
  /status                    Show context usage and session info
  /quit                      Exit

WORKFLOW COMMANDS
  /commit                    Stage and commit with generated message
  /review                    Review current changes
  /pr                        Create a pull request

CONFIGURATION FILES
  ~/.claude/settings.json           Global settings
  .claude/settings.json             Project settings
  CLAUDE.md                         Project instructions (any directory level)
  .claude/skills/*.md               Custom skills
  ~/.claude/keybindings.json        Custom keybindings

MODELS (fastest → most capable)
  haiku       Boilerplate, formatting, simple edits
  sonnet      Daily coding, tests, straightforward debugging
  opus        Architecture, complex debugging, security review

CROSS-REFERENCES
  Chapter 14  AI engineering principles — the theory behind the practice
  Chapter 36  Beast Mode — advanced orchestration at scale
```

---

## Try It Yourself

Want to put this into practice? The [TicketPulse course](../course/) has hands-on modules that build on these concepts:

- **[L3-M86: AI-Powered Engineering Workflow](../course/modules/loop-3/L3-M86-ai-powered-engineering.md)** — Integrate Claude Code into TicketPulse's development workflow and measure the impact on your throughput
- **[L3-M86a: AI-Native Spec-Driven Development](../course/modules/loop-3/L3-M86a-ai-native-spec-driven-development.md)** — Write a spec for a new TicketPulse feature and use Claude Code to implement it end-to-end from the spec

### Quick Exercises

1. **Write a `CLAUDE.md` file for your current project: include how to run tests, the code style rules Claude must follow, which files are off-limits, and the commands for your most common workflows.**
2. **Create one custom skill for a task you repeat weekly — a code review checklist, a migration generator, a test scaffolder — and run it three times to measure how much time it saves.**
3. **Set up one MCP server integration for your workflow: connect Claude Code to your issue tracker, your database, or your internal docs, then use it to answer a question you'd normally have to context-switch to answer.**

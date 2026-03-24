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

---

## 1. CLAUDE CODE FUNDAMENTALS

### 1.1 What Claude Code Is

**What it is:** Claude Code is Anthropic's official CLI tool that puts a full AI coding agent directly in your terminal. Unlike ChatGPT or web-based AI assistants where you copy-paste code back and forth, Claude Code operates directly on your filesystem -- reading files, writing code, running commands, managing git, and executing multi-step tasks autonomously.

**How it differs from web-based AI:**

| Dimension | Web-based AI (ChatGPT, Claude.ai) | Claude Code (CLI) |
|---|---|---|
| File access | None -- you paste code manually | Direct filesystem read/write |
| Command execution | None | Runs shell commands in your terminal |
| Git integration | None | Full git workflow (commit, branch, PR) |
| Context | Limited to what you paste | Reads your actual codebase |
| Multi-file edits | Manual copy-paste per file | Edits multiple files in one operation |
| Persistence | Chat history only | CLAUDE.md memory files across sessions |
| Tool use | Plugins/web browsing | MCP servers, custom hooks, shell tools |

**The key mental shift:** Web-based AI is a conversation partner you bring information to. Claude Code is an agent you point at your codebase and tell what to do.

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

### 1.3 The Conversation Model: How Context Works

**Context window basics:** Claude Code maintains a conversation context that includes everything discussed in the current session -- your messages, Claude's responses, file contents that were read, command outputs, and tool results. This context has a finite size (the "context window").

**What counts toward context:**

- Every message you send
- Every file Claude reads (the full content goes into context)
- Every command output
- Claude's own responses and reasoning
- Tool call inputs and outputs

**Context window management strategies:**

1. **Be surgical with file reads.** Instead of asking Claude to "look at the whole project," point it at specific files or directories.

2. **Start fresh when context gets long.** If a session has been going for hundreds of messages, start a new one. Claude Code will tell you when context is getting full.

3. **Use CLAUDE.md for persistent context.** Instead of re-explaining your project every session, put key information in CLAUDE.md files (covered in Section 6).

4. **Context compression.** Claude Code automatically summarizes older parts of the conversation when the context window fills up. You will see a message when this happens. Important details from early in the conversation may be lost -- another reason to use CLAUDE.md for critical information.

```
# Signs you need to start a fresh session:
# - Claude starts forgetting earlier instructions
# - You see "context compressed" messages
# - Responses are getting slower
# - Claude is confused about the current state of files
```

### 1.4 Permission Modes and Safety Model

Claude Code has a permission system that controls what actions it can take without asking you first.

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

**Best practice:** Start with default permissions. Use `--accept-edits` once you trust Claude's edit patterns for a given task. Reserve `--accept-all` for CI pipelines and well-tested automation scripts.

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

**Using /help effectively:** When you are unsure what Claude Code can do, `/help` is your starting point. It lists all available slash commands including any custom ones from skills and plugins.

---

## 2. ADVANCED CLAUDE CODE FEATURES

### 2.1 Slash Commands

Slash commands are built-in actions that trigger specific workflows.

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

**Using /review:**

```
> /review

# Claude will:
# 1. Look at staged and unstaged changes
# 2. Analyze code quality, potential bugs, security issues
# 3. Provide structured feedback with specific line references
```

### 2.2 Plan Mode: Writing and Executing Implementation Plans

Plan mode lets Claude analyze and plan without making any changes. This is essential for complex tasks where you want to understand the approach before committing to it.

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
# Step 1: Plan mode -- understand the problem
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

**Why this matters:** Jumping straight to implementation on complex tasks leads to rework. The plan-first approach catches architectural issues before code is written.

### 2.3 Subagents: Dispatching Parallel Agents

**What subagents are:** Claude Code can spawn independent sub-conversations (subagents) to handle tasks in parallel. Each subagent has its own context and can work on a separate part of the problem.

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

**Subagent isolation:** Each subagent operates in its own context. They cannot see each other's work in progress. The orchestrator (main conversation) coordinates results.

### 2.4 Git Worktrees for Isolated Feature Development

**What worktrees are:** Git worktrees let you check out multiple branches of the same repository simultaneously in different directories. Combined with Claude Code, this enables truly parallel feature development.

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

**Why this matters:** Each Claude Code instance works in its own directory with its own branch. No merge conflicts during development, no stepping on each other's changes.

### 2.5 Background Tasks and Multi-Agent Workflows

**Background tasks:** You can run Claude Code tasks in the background and come back to check results later.

```bash
# Run a task in the background
claude --background "run all tests and fix any failures" &

# Check on running tasks
claude --status
```

**Multi-agent workflow example -- full feature development:**

```bash
# Agent 1: Implement the feature
claude "implement the user invitation feature per the spec in docs/invite-spec.md"

# Agent 2 (after Agent 1 completes): Write tests
claude "write comprehensive tests for the invitation feature in src/features/invite/"

# Agent 3 (after Agent 2): Review everything
claude "review all changes for the invitation feature. Check for security issues, edge cases, and test coverage gaps"
```

### 2.6 Memory System: CLAUDE.md Files

**How Claude remembers across sessions:** Claude Code reads special markdown files called CLAUDE.md that contain instructions, context, and preferences. These files persist on disk and are automatically loaded at the start of every session.

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
- Database queries go in src/lib/db/ -- never in route handlers directly
- Error handling: use the AppError class from src/lib/errors.ts
- All new features need tests before merging

## Architecture
- src/app/          -- Next.js App Router pages and layouts
- src/components/   -- React components (colocate with feature when possible)
- src/lib/          -- Shared utilities, database, auth
- src/features/     -- Feature modules (each has its own types, hooks, components)
- prisma/           -- Database schema and migrations

## Testing Commands
- npm test                    -- Run all unit tests
- npm run test:e2e            -- Run Playwright E2E tests
- npm run test:coverage       -- Run with coverage report

## Important Notes
- NEVER commit .env files
- Always run `npm run lint` before committing
- Database migrations must be backward-compatible (no dropping columns without a deprecation period)
- The CI pipeline runs on every PR -- all checks must pass
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

Using phrases like "think carefully," "think step by step," or "analyze thoroughly" signals Claude to engage deeper reasoning.

---

## 3. SKILLS & PLUGINS

### 3.1 What Skills Are and How They Work

**Skills** are reusable instruction sets that teach Claude Code how to perform specific tasks. They are markdown files with frontmatter that define when and how to activate.

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

### 3.2 Creating Custom Skills

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
- `src/app/api/<resource>/route.ts` -- the route handler
- `src/app/api/<resource>/schema.ts` -- zod validation schemas
- `src/app/api/<resource>/__tests__/route.test.ts` -- tests

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

### 3.3 Plugin System

**Plugins** extend Claude Code with additional capabilities: custom agents, hooks, commands, and skills bundled together.

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

### 3.4 Hook System

Hooks let you run custom code at specific points in Claude Code's execution. They are the mechanism for enforcing standards and automating checks.

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

**Hook environment variables available:**

- `$CLAUDE_FILE_PATH` -- the file being read/written
- `$CLAUDE_TOOL_INPUT` -- the raw input to the tool
- `$CLAUDE_TOOL_NAME` -- the name of the tool being used
- `$CLAUDE_SESSION_ID` -- current session identifier

**Practical hook example -- auto-format on every file edit:**

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

### 3.5 MCP (Model Context Protocol) Server Integration

**What MCP is:** The Model Context Protocol is a standard for connecting AI assistants to external tools and data sources. MCP servers expose tools that Claude Code can use -- databases, APIs, file systems, third-party services, and more.

**Why it matters:** MCP turns Claude Code from a code-only assistant into a full workflow automation tool. It can query your database, read your Linear tickets, send Slack messages, check your Figma designs, and deploy your application -- all from the same conversation.

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

**Custom MCP server (for your own internal APIs):**

You can build your own MCP server to expose any tool or API:

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

---

## 4. AGENT TEAMS & ORCHESTRATION

### 4.1 Designing Multi-Agent Workflows

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

### 4.3 Parallel Agent Dispatch

**Pattern: Fan-out, fan-in.**

```
> I need to update our error handling across the codebase.
  The following modules are independent -- handle them in parallel:

  1. src/api/ -- Add structured error responses to all route handlers
  2. src/workers/ -- Add retry logic with exponential backoff to all workers
  3. src/lib/database/ -- Add connection retry and query timeout handling
  4. src/lib/external/ -- Add circuit breaker pattern to all external API calls

  Each module should follow the error handling conventions in CLAUDE.md.
  After all agents complete, summarize what was changed.
```

### 4.4 Agent Isolation with Worktrees

**The worktree-per-agent pattern** is the most robust approach for parallel development:

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

### 4.5 Communication Between Agents

Agents can communicate via the `SendMessage` mechanism -- the orchestrator can send instructions and context to subagents, and subagents report back.

**Pattern: Pass context between agents via files.**

```
> Agent 1: Generate the database schema for the Teams feature and write
  it to docs/teams-schema.md when done.

> Agent 2: Read docs/teams-schema.md and implement the API endpoints
  that match the schema.

> Agent 3: Read docs/teams-schema.md and implement the frontend
  components with TypeScript types matching the schema.
```

This file-based communication pattern works because all agents share the same filesystem (or can share files between worktrees).

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

**Pattern 3: Deployment agent.**

```
> Prepare this branch for deployment:
  1. Run all tests -- fix any failures
  2. Run the linter -- fix any issues
  3. Run the type checker -- fix any errors
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

### 5.2 CLAUDE.md Files: Project-Level Instructions

**Best practices for CLAUDE.md files:**

1. **Keep it concise.** CLAUDE.md is loaded into context every session. Every line costs tokens.
2. **Focus on what is non-obvious.** Do not document standard conventions (like "use const instead of let") -- Claude already knows those. Document your project-specific decisions.
3. **Include the commands Claude needs.** Test commands, build commands, lint commands -- anything Claude should run.
4. **Update it as the project evolves.** Treat CLAUDE.md like living documentation.

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
- Run `make check` before committing -- it runs lint, typecheck, and tests
```

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
- pnpm install          -- install all dependencies
- pnpm build            -- build all packages
- pnpm test             -- run all tests
- pnpm lint             -- lint everything
- turbo run build --filter=@acme/api  -- build specific package
```

**Package-level CLAUDE.md (`packages/ui/CLAUDE.md`):**

```markdown
# @acme/ui -- Component Library

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

### 5.5 Model Selection: Opus, Sonnet, Haiku

**Choosing the right model:**

| Model | Speed | Cost | Best for |
|---|---|---|---|
| **Haiku** | Fastest | Lowest | Simple edits, file renames, formatting, boilerplate generation |
| **Sonnet** | Medium | Medium | Most daily coding tasks, test writing, debugging straightforward issues |
| **Opus** | Slowest | Highest | Architecture decisions, complex debugging, multi-file refactoring, security review |

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

This is the core workflow that turns Claude Code from a chatbot into a productive engineering partner.

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

### 6.2 TDD with Claude: Tests First, Then Implementation

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

**Why this works with Claude Code:** Claude can run the tests directly and iterate until they pass. You get to review the test cases (which define the behavior) before any implementation code exists.

### 6.3 Debugging Workflow

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

### 6.4 Code Review Workflow

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

**Reviewing someone else's PR:**

```
> Review PR #142 on GitHub. Read all changed files and provide a
  structured review. Focus on correctness and security -- this PR
  modifies the authentication flow.
```

### 6.5 Large Refactoring: Plans + Parallel Agents

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
> Implement the following resolvers in parallel -- they are independent:
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

### 6.7 Codebase Exploration

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

---

## 7. CLAUDE CODE IN TEAM ENVIRONMENTS

### 7.1 Shared CLAUDE.md for Team Conventions

**The team CLAUDE.md should be committed to version control.** It serves as executable documentation that both humans and Claude follow.

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

### 7.2 Hooks for Enforcing Standards

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

### 7.3 CI Integration: Running Claude Code in CI Pipelines

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

### 7.4 Best Practices for AI-Generated Code in Team Reviews

**For the developer using Claude Code:**

1. **Always review Claude's output before committing.** Claude is a tool, not a substitute for your judgment.
2. **Run the full test suite.** Claude may introduce subtle regressions in files it did not directly modify.
3. **Check for hallucinated APIs.** Claude sometimes uses methods or libraries that do not exist or uses incorrect signatures.
4. **Verify security-sensitive code manually.** Authentication, authorization, encryption, and input validation deserve human review.

**For the team reviewing AI-assisted PRs:**

1. **Review as normal.** AI-generated code should meet the same standards as human-written code.
2. **Pay extra attention to edge cases.** AI tends to handle happy paths well but can miss subtle error conditions.
3. **Check for over-engineering.** AI sometimes produces more abstraction than necessary.
4. **Verify test assertions are meaningful.** AI can write tests that pass but do not actually verify the right behavior.

---

## 8. TIPS & TRICKS

### 8.1 How to Write Effective Prompts for Claude Code

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

### 8.2 When to Be Specific vs When to Let Claude Explore

**Be specific when:**

- You know exactly what you want (fix a specific bug, add a specific field)
- The change is in a critical path (auth, payments, data integrity)
- You have a clear mental model of the solution
- The task involves security-sensitive code

**Let Claude explore when:**

- You are starting on an unfamiliar codebase
- You want to understand trade-offs between approaches
- The problem is ambiguous ("our API is slow" -- where exactly?)
- You want creative solutions to a design problem

```
# Exploration prompt (let Claude investigate)
> Our checkout flow has gotten slow. Users are complaining about
  3-4 second load times. Investigate the checkout code path,
  identify bottlenecks, and propose optimizations. Start by
  tracing the request flow and measuring where time is spent.
```

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

**Proactive context management:**

- Break large tasks into sessions: planning in one, implementation in another
- Use CLAUDE.md to persist decisions so you do not need to re-explain
- After each major milestone, commit and start fresh

### 8.4 Cost Management

**Token costs by model (approximate):**

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Typical session cost |
|---|---|---|---|
| Haiku | $0.25 | $1.25 | $0.01 - $0.10 |
| Sonnet | $3.00 | $15.00 | $0.10 - $1.00 |
| Opus | $15.00 | $75.00 | $0.50 - $5.00+ |

**Cost reduction strategies:**

1. **Use the right model for the job.** Do not use Opus for adding a console.log.
2. **Keep CLAUDE.md concise.** Every token in CLAUDE.md is read every session.
3. **Be specific in prompts.** Vague prompts cause Claude to read more files and try more things.
4. **Use `/compact` in long sessions** to reduce context size.
5. **Avoid reading entire large files.** Point Claude at specific functions or line ranges.
6. **Batch related changes.** One session that makes 5 related changes is cheaper than 5 separate sessions.

**Monitor costs:**

```
> /cost
# Shows tokens used and estimated cost for the current session
```

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

**Pitfall 4: Ignoring test failures.**

```
# WRONG
> The tests are failing but the code looks right, just skip them

# RIGHT
> The tests are failing. Read the test output, understand why,
  and fix either the tests or the implementation. Do not skip
  or delete failing tests.
```

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

**Pitfall 6: Not using CLAUDE.md.**

If you find yourself repeating the same instructions every session ("use pnpm, not npm", "tests go in __tests__ directories", "use the AppError class"), put it in CLAUDE.md. That is exactly what it is for.

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

MODELS (fastest → most capable)
  haiku       Boilerplate, formatting, simple edits
  sonnet      Daily coding, tests, straightforward debugging
  opus        Architecture, complex debugging, security review
```

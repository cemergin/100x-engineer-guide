# L1-M02: Your Dev Environment

> **Loop 1 (Foundation)** | Section 1A: Tooling & Environment | ⏱️ 60 min | 🟢 Core | Prerequisites: L1-M01 (TicketPulse running locally), macOS or Linux terminal
>
> **Source:** Chapters 12, 21 of the 100x Engineer Guide

## What You'll Learn
- How to install and configure modern CLI tools that are 5-50x faster than their default counterparts
- How to set up a shell environment (zsh) that saves you hundreds of keystrokes per day
- How to search, navigate, and manipulate code at the speed of thought

## Why This Matters

Here is a truth that takes most engineers years to internalize: **the speed of your tools shapes the speed of your thinking**. When searching a codebase takes 5 seconds instead of 0.1 seconds, you search less. When navigating files requires typing full paths, you explore less. When your terminal doesn't have history search, you re-type commands instead of iterating on them.

The tools in this module are not nice-to-haves. They are the difference between an engineer who moves fluidly through a codebase and one who fights their environment all day. Every minute you spend setting these up pays for itself within a week — and then keeps paying for the rest of your career.

You're going to install these tools, use them on the TicketPulse codebase, and feel the difference immediately. Not tomorrow. Right now.

## Prereq Check

Can you open a terminal and run `brew --version` (macOS) or `apt --version` (Ubuntu/Debian)? You need a package manager. If you're on macOS without Homebrew, install it: `https://brew.sh`. If you're on Linux, your system package manager works fine.

Is TicketPulse cloned from M01? You'll use it as the test codebase. If not, `git clone https://github.com/100x-engineer/ticketpulse.git`.

---

## Part 1: The Modern CLI Toolkit (20 minutes)

We're going to replace the slow, clunky defaults with modern alternatives. Install all of them now — we'll use each one immediately after.

### 1.1 Install Everything

**macOS (Homebrew):**
```bash
brew install ripgrep fd fzf bat eza git-delta jq
```

**Ubuntu/Debian:**
```bash
sudo apt install -y ripgrep fd-find fzf bat jq
# Note: fd is 'fdfind' on Debian/Ubuntu, we'll alias it
# eza and delta need separate installation
cargo install eza    # or: brew install eza (if you have linuxbrew)
cargo install git-delta  # or download from https://github.com/dandavison/delta/releases
```

If any of those fail, don't stop — install what you can and move on. You can fix the stragglers later.

**Try It Now:** Verify the installations:

```bash
rg --version
fd --version    # or fdfind --version on Debian
fzf --version
bat --version   # or batcat on Debian
eza --version
delta --version
jq --version
```

Each of these should print a version number. If any say "command not found," install it individually. But don't spend more than 2 minutes debugging installation — the rest of the module is more valuable.

### 1.2 ripgrep (rg) — Search That Actually Flies

`grep -r` works, but it's slow. It searches binary files, `.git` directories, `node_modules`, and every other thing you don't care about. `ripgrep` is a drop-in replacement that's typically 5-10x faster, respects `.gitignore` by default, and has better output formatting.

**Try It Now:** `cd` into the TicketPulse directory and run these back to back:

```bash
cd ticketpulse

# Old way
time grep -r "event" --include="*.ts" .

# New way
time rg "event" --type ts
```

Notice the speed difference. On a small codebase like TicketPulse, both are fast. On a codebase with 100,000 files, `rg` will finish in under a second while `grep -r` is still thinking.

But the real power is in the features:

```bash
# Search for a function name across the codebase
rg "async function" --type ts

# Find all TODO comments
rg "TODO|FIXME|HACK" --type ts

# Find files that import a specific module
rg "from.*database" --type ts

# Count matches per file
rg "event" --type ts --count

# Only list filenames with matches
rg -l "redis" --type ts

# Search with context (3 lines before and after)
rg "error" --type ts -B 3 -A 3

# Search hidden files but skip .git
rg "DATABASE" --hidden -g '!.git'
```

**Insight:** `rg` respects your `.gitignore` automatically. This single behavior eliminates the most common annoyance with `grep`: accidentally searching `node_modules`, `.git`, build artifacts, and vendor directories. You never have to think about excluding them.

### 1.3 fd — Find Files Without the Headache

`find` is powerful but its syntax is a usability disaster. `fd` is a simpler, faster alternative:

```bash
# Old way: find all TypeScript files
find . -name "*.ts" -type f -not -path "*/node_modules/*"

# New way
fd -e ts

# That's it. fd ignores .git and node_modules automatically.
```

More examples on the TicketPulse codebase:

```bash
# Find all migration files
fd migration

# Find all test files
fd test --type f

# Find all configuration files
fd config --type f

# Find all directories named 'middleware'
fd middleware --type d

# Find files modified in the last hour
fd -e ts --changed-within 1h

# Find and count lines in all test files
fd -e test.ts --exec wc -l
```

**Try It Now:** How many TypeScript files does TicketPulse have?

```bash
fd -e ts | wc -l
```

How many of those are test files?

```bash
fd -e test.ts | wc -l
```

### 1.4 fzf — The Fuzzy Finder That Changes Everything

This is the single most impactful tool in this list. `fzf` is a fuzzy finder — it takes any list of items, lets you type a partial match, and shows you results instantly. It integrates with your shell in three powerful ways.

**Install the key bindings:**

```bash
# macOS
$(brew --prefix)/opt/fzf/install
# Say yes to key bindings and completion, no to updating shell config if you want to do it manually

# Or manually: add to ~/.zshrc
source <(fzf --zsh)
```

Open a new terminal tab (or `source ~/.zshrc`) and try the three core bindings:

**`Ctrl+R` — Fuzzy search command history:**

Press `Ctrl+R` and start typing. Instead of the default reverse-i-search (which matches from the beginning and is terrible), fzf shows you a live-filtered list of your entire history. Type any word from any part of the command.

```
# Press Ctrl+R, then type "curl"
# You'll see every curl command you've ever run
# Arrow keys to select, Enter to execute
```

**`Ctrl+T` — Fuzzy find files and insert the path:**

Start typing a command, then press `Ctrl+T`:

```bash
# Type: cat (then press Ctrl+T)
# A file finder appears — type "event" to filter
# Select a file, its path gets inserted into your command
# Result: cat src/routes/events.ts
```

**`Alt+C` (or `Esc` then `c` on some terminals) — Fuzzy find directories and cd:**

Press `Alt+C`, type a directory name fragment, and you're there.

**Try It Now:** Use `Ctrl+T` to find and open the `docker-compose.yml` file:

```bash
bat   # then press Ctrl+T, type "docker", select docker-compose.yml
```

**Try It Now:** Use `Ctrl+R` to find the curl command you ran in Module 1:

Press `Ctrl+R`, type "events", and you should see your `curl http://localhost:3000/api/events` command from earlier.

### 1.5 bat — cat With Wings

`cat` dumps file contents with no formatting. `bat` adds syntax highlighting, line numbers, and git change indicators:

```bash
# Old way
cat src/routes/events.ts

# New way
bat src/routes/events.ts
```

The difference is immediate and dramatic. Code becomes readable in the terminal.

```bash
# Show a specific line range
bat src/routes/events.ts --line-range 10:30

# Show git changes (modified/added/deleted lines)
bat --diff src/routes/events.ts

# Use bat as a pager for other commands
rg "event" --type ts | bat

# Plain mode (no line numbers, no header — good for piping)
bat -p src/routes/events.ts
```

### 1.6 eza — ls That Actually Helps

```bash
# Old way
ls -la

# New way
eza -la --git --icons
```

`eza` shows file permissions, sizes, dates, git status, and file type icons in a clean, colored format.

```bash
# Tree view of the project (2 levels deep)
eza --tree --level=2 --icons src/

# Show only directories
eza -D --icons src/

# Sort by modification time
eza -la --sort=modified src/

# Tree view, ignoring node_modules and .git
eza --tree --level=3 --icons --ignore-glob="node_modules|.git|dist"
```

**Try It Now:** Run this on the TicketPulse codebase:

```bash
eza --tree --level=2 --icons --ignore-glob="node_modules|.git" .
```

Compare that to `ls -R`. The tree view alone is worth the install.

### 1.7 delta — Git Diffs That Don't Hurt Your Eyes

Configure `delta` as your git pager:

```bash
git config --global core.pager delta
git config --global interactive.diffFilter "delta --color-only"
git config --global delta.navigate true
git config --global delta.side-by-side true
git config --global delta.line-numbers true
```

Now make a small change to any file and run:

```bash
# Edit something small in the TicketPulse codebase
echo "// test change" >> src/routes/health.ts

git diff
```

You'll see a beautifully formatted, side-by-side diff with syntax highlighting. This is what diffs should have always looked like.

Clean up your test change:

```bash
git checkout -- src/routes/health.ts
```

### 1.8 jq — JSON at the Command Line

You used this briefly in M01. Let's go deeper. `jq` is a command-line JSON processor — think of it as `sed` for JSON.

**Try It Now:** Hit the TicketPulse API and extract specific fields:

```bash
# Get all event titles
curl -s http://localhost:3000/api/events | jq '.events[].title'

# Get events with their remaining ticket count
curl -s http://localhost:3000/api/events | jq '.events[] | {title, tickets_remaining}'

# Get only events with more than 1000 tickets remaining
curl -s http://localhost:3000/api/events | jq '.events[] | select(.tickets_remaining > 1000) | .title'

# Get the total number of events
curl -s http://localhost:3000/api/events | jq '.total'

# Pretty-print raw JSON from any source
echo '{"compact":true,"useful":true}' | jq .
```

**Insight:** `jq` is not just for pretty-printing. In production, you'll use it to parse deployment outputs, filter log files, transform API responses in scripts, and extract values from configuration files. It is one of the most universally useful CLI tools that exists.

---

## Part 2: Shell Configuration (20 minutes)

### 2.1 Zsh Setup

If you're on macOS, you already have zsh as your default shell. Verify:

```bash
echo $SHELL
```

If it says `/bin/zsh` or `/usr/bin/zsh`, you're good. If not:

```bash
chsh -s $(which zsh)
```

### 2.2 Oh My Zsh (Optional but Popular)

```bash
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
```

Oh My Zsh gives you plugin infrastructure and themes. Even if you don't use it, install the two plugins that matter most:

```bash
# Autosuggestions — shows ghost text of commands you've run before
git clone https://github.com/zsh-users/zsh-autosuggestions ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-autosuggestions

# Syntax highlighting — colors your commands as you type (red = invalid, green = valid)
git clone https://github.com/zsh-users/zsh-syntax-highlighting ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-syntax-highlighting
```

### 2.3 Configure Your .zshrc

Open `~/.zshrc` in your editor. If you have Oh My Zsh, find the `plugins=()` line and update it:

```bash
plugins=(
    git
    z
    docker
    fzf
    zsh-autosuggestions
    zsh-syntax-highlighting
)
```

Below the plugins section, add fzf configuration:

```bash
# ── fzf configuration ──
export FZF_DEFAULT_COMMAND='fd --type f --hidden --exclude .git'
export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"
export FZF_ALT_C_COMMAND='fd --type d --hidden --exclude .git'
export FZF_DEFAULT_OPTS='--height 40% --layout=reverse --border'
```

**Try It Now:** Add these history settings to your `~/.zshrc`:

```bash
# ── History ──
HISTSIZE=100000
SAVEHIST=100000
HISTFILE=~/.zsh_history
setopt SHARE_HISTORY
setopt HIST_IGNORE_ALL_DUPS
setopt HIST_IGNORE_SPACE
setopt HIST_REDUCE_BLANKS
```

This means your last 100,000 commands are saved and shared across terminal sessions. Combined with `fzf`'s `Ctrl+R`, you effectively never lose a command.

### 2.4 Build Your Aliases

This is the exercise. You are going to create a `.zshrc` snippet with aliases that save you time every single day.

**Your Turn:** Add these aliases to your `~/.zshrc`. Read each one, understand what it does, then add the ones that match your workflow. Modify them to fit how you actually work.

```bash
# ── Navigation ──
alias ..="cd .."
alias ...="cd ../.."
alias ll="eza -la --git --icons"
alias lt="eza --tree --level=2 --icons"

# ── Git (the ones you'll use 50 times a day) ──
alias gs="git status -sb"
alias gc="git commit"
alias gd="git diff"
alias gds="git diff --staged"
alias gl="git log --oneline --graph --decorate -20"
alias gp="git push"
alias gpl="git pull --rebase"
alias gpf="git push --force-with-lease"    # Safe force push — NEVER use --force

# ── Docker ──
alias dc="docker compose"
alias dcu="docker compose up -d"
alias dcd="docker compose down"
alias dcl="docker compose logs -f"
alias dps="docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"

# ── Quick utilities ──
alias ports="lsof -iTCP -sTCP:LISTEN -n -P"  # What's using which port?
alias myip="curl -s ifconfig.me"               # Your public IP
alias weather="curl -s wttr.in/?format=3"      # Weather in your terminal

# ── Functions ──
# Create a directory and cd into it
mkcd() { mkdir -p "$1" && cd "$1"; }

# Quick HTTP server in current directory
serve() { python3 -m http.server "${1:-8000}"; }
```

After adding the aliases, reload your shell:

```bash
source ~/.zshrc
```

**Try It Now:** Test your new aliases on the TicketPulse codebase:

```bash
cd ticketpulse
gs          # git status, short format
ll          # list files with details
lt          # tree view
gl          # git log, visual
dps         # docker containers
```

Feel that? Each of those saved you 10-40 keystrokes. Multiply by the hundreds of times you run these per day.

### 2.5 Power Combo: fzf + Git

Add these to your `~/.zshrc` — they combine fzf with git for interactive workflows:

```bash
# Interactive git branch checkout
alias gbf='git branch -a | fzf --preview "git log --oneline --graph --decorate {}" | sed "s/remotes\/origin\///" | xargs git checkout'

# Interactive git log browser with diff preview
alias glf='git log --oneline --all | fzf --preview "git show --stat {+1}"'

# Open file in editor with preview
alias vf='fzf --preview "bat --color=always --line-range :50 {}" | xargs -r ${EDITOR:-code}'
```

**Try It Now:** Run `vf` in the TicketPulse directory. A file picker appears with a syntax-highlighted preview of each file. Type "event" to filter. Select a file to open it in your editor.

This is what "navigating code at the speed of thought" feels like.

---

## Part 3: Editor Essentials (15 minutes)

### 3.1 VS Code Shortcuts That Actually Matter

If you use VS Code (or a similar editor), these are the shortcuts that provide the most value. You don't need to memorize 200 shortcuts — these 15 cover 90% of daily editing.

**Navigation:**
| Shortcut | Action |
|----------|--------|
| `Cmd+P` (Mac) / `Ctrl+P` (Linux) | Quick open file by name (fuzzy match) |
| `Cmd+Shift+P` / `Ctrl+Shift+P` | Command palette (search any action) |
| `Cmd+Shift+F` / `Ctrl+Shift+F` | Search across all files |
| `Cmd+G` / `Ctrl+G` | Go to line number |
| `F12` | Go to definition |
| `Shift+F12` | Find all references |
| `Cmd+Shift+O` / `Ctrl+Shift+O` | Go to symbol in file |

**Editing:**
| Shortcut | Action |
|----------|--------|
| `Alt+Up/Down` | Move line up/down |
| `Shift+Alt+Up/Down` | Duplicate line up/down |
| `Cmd+D` / `Ctrl+D` | Select next occurrence of word (multi-cursor) |
| `Cmd+Shift+L` / `Ctrl+Shift+L` | Select ALL occurrences (multi-cursor) |
| `Cmd+/` / `Ctrl+/` | Toggle line comment |
| `Cmd+Shift+K` / `Ctrl+Shift+K` | Delete line |
| `Cmd+L` / `Ctrl+L` | Select entire line |
| `Cmd+[` / `Ctrl+[` | Indent/outdent line |

**Try It Now:** Open VS Code in the TicketPulse directory:

```bash
code ticketpulse
```

1. Press `Cmd+P`, type "events" — see how fast it finds `src/routes/events.ts`
2. Open that file, click on a function name, press `F12` — jump to its definition
3. Press `Cmd+Shift+F`, search for "TODO" — see all TODOs across the codebase
4. In any file, hold `Cmd` and click a variable name — go to its definition
5. Select a word, press `Cmd+D` three times — you now have 3 cursors on every occurrence

### 3.2 VS Code Settings That Matter

Open VS Code settings (`Cmd+,`) and consider these:

```json
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "editor.minimap.enabled": false,
  "editor.renderWhitespace": "boundary",
  "editor.bracketPairColorization.enabled": true,
  "editor.guides.bracketPairs": true,
  "editor.wordWrap": "on",
  "editor.inlineSuggest.enabled": true,
  "files.autoSave": "afterDelay",
  "files.autoSaveDelay": 1000,
  "terminal.integrated.defaultProfile.osx": "zsh"
}
```

The most impactful: `formatOnSave`. You never think about formatting again. It just happens.

### 3.3 Essential VS Code Extensions

These are worth installing immediately:

- **Prettier** — auto-format code on save
- **ESLint** — catch errors as you type
- **GitLens** — see who changed each line, when, and why
- **Error Lens** — show errors inline, right next to the code
- **Thunder Client** — test APIs without leaving the editor (like Postman, but in VS Code)
- **Docker** — manage containers from the sidebar

### 3.4 The Integrated Terminal

VS Code has a built-in terminal (`` Ctrl+` ``). This is where your aliases, fzf, and all your CLI tools come together with your editor. You can:

- Split terminals (`Cmd+\` in terminal)
- Name terminals (right-click the tab)
- Run tasks (`Cmd+Shift+B` for build tasks)
- Click file paths in terminal output to open them in the editor

**Insight:** The best engineers don't just know their tools — they've wired them together so that the output of one feeds naturally into the next. Terminal output links to editor files. Editor search uses the same fuzzy-find as shell history. Git operations are available everywhere. This integration compounds.

---

## Part 4: Feel the Difference (5 minutes)

Let's do a rapid-fire exercise that uses everything you just set up. Time yourself.

### Challenge: Answer These Questions About the TicketPulse Codebase

Using your new tools, answer each question. Try to answer each one in under 10 seconds.

**1. Which files import the `redis` module?**
```bash
rg "from.*redis" --type ts -l
```

**2. How many TODO comments are in the codebase?**
```bash
rg "TODO" --type ts --count-matches
```

**3. What's the database table schema for events?**
```bash
bat src/db/migrations/002_create_events.sql
```

**4. What port does Redis run on in the Docker setup?**
```bash
rg "6379" docker-compose.yml
```

**5. Find and open the file that handles ticket validation:**
```bash
vf    # type "valid", select the file
```

**6. What was the last commit message?**
```bash
gl    # your alias for git log --oneline --graph --decorate -20
```

**Common Mistake:** Engineers install tools but never change their habits. You'll fall back to `grep`, `find`, and `cat` out of muscle memory for about a week. Push through it. Force yourself to use `rg`, `fd`, and `bat`. After a week, the old tools will feel unbearably slow. That's when you know the investment has paid off.

---


> **What did you notice?** Look back at what you just built. What surprised you? What felt harder than expected? That's where the real learning happened.

## Module Summary

- **ripgrep** (`rg`) replaces `grep` — 5-10x faster, respects `.gitignore`, better output
- **fd** replaces `find` — simpler syntax, faster, sane defaults
- **fzf** adds fuzzy finding everywhere — `Ctrl+R` for history, `Ctrl+T` for files, `Alt+C` for directories
- **bat** replaces `cat` — syntax highlighting, line numbers, git integration
- **eza** replaces `ls` — tree views, git status, icons
- **delta** makes git diffs readable — side-by-side, syntax highlighting
- **jq** processes JSON on the command line — extract, filter, transform
- **Shell aliases** compress common commands — `gs` instead of `git status -sb`
- **The tools compound**: `fzf` + `rg` + `bat` + your aliases create a workflow that's qualitatively different from the defaults

## What's Next

You have a fast environment and a running codebase. In Module 3, you'll learn the Git skills that separate professionals from amateurs — interactive rebase, bisect, and the reflog safety net. You'll practice these directly on TicketPulse feature branches with intentionally messy history, and you'll learn to recover from every Git disaster you'll ever encounter.

## Key Terms

| Term | Definition |
|------|-----------|
| **Shell** | A command-line interpreter that executes user commands and scripts (e.g., Bash, Zsh). |
| **Alias** | A shortcut that maps a short command name to a longer or more complex command. |
| **Fuzzy finder** | A tool (such as fzf) that lets you search and select items interactively using approximate string matching. |
| **Terminal multiplexer** | Software (like tmux) that allows multiple terminal sessions within a single window, with split panes and session persistence. |
| **Dotfiles** | Hidden configuration files (prefixed with a dot) that customize your shell, editor, and development tools. |

## Further Reading

- [ripgrep user guide](https://github.com/BurntSushi/ripgrep/blob/master/GUIDE.md) — advanced patterns and config
- [fzf examples](https://github.com/junegunn/fzf/wiki/examples) — dozens of creative fzf integrations
- [jq manual](https://stedolan.github.io/jq/manual/) — the full language reference (jq is surprisingly powerful)

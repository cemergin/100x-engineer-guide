<!--
  CHAPTER: 12
  TITLE: Linux, Shell & Editors
  PART: III — Tooling & Practice
  PREREQS: None
  KEY_TOPICS: Linux commands, bash scripting, SSH, shell productivity, fzf, tmux, Vim/Neovim, VS Code
  DIFFICULTY: Beginner → Advanced
  UPDATED: 2026-03-24
-->

# Chapter 12: Linux, Shell & Editors

> **Part III — Tooling & Practice** | Prerequisites: None | Difficulty: Beginner to Advanced

The difference between a 10-minute task and a 10-second task is knowing your tools. This chapter covers the foundational developer skills that eliminate friction — Linux mastery, shell productivity, and editor efficiency that make you measurably faster every single day.

### In This Chapter
- Linux Mastery
- Shell Productivity
- Vim / Neovim
- VS Code Productivity

### Related Chapters
- Chapter 12b — Git, Docker, Terraform & Kubernetes (infrastructure CLIs)
- Chapter 7 — infrastructure concepts behind Docker/Terraform/K8s
- Chapter 17 — Claude Code as your AI co-pilot in the terminal
- Chapter 20 — environment management
- Chapter 15 — Git workflows in teams
- Chapter 36 — Beast Mode toolchain setup (putting it all together)

---

Here's something nobody tells you when you start programming: the tool is never just the tool. Every hour you invest learning your editor, your shell, your git workflow — that's not overhead. That's compounding interest on every hour of work you'll ever do afterward. The engineers who seem impossibly fast aren't smarter than you. They've just spent time with their tools that you haven't yet.

This chapter is that investment, accelerated. We're going to walk through the tools that actually matter — the ones that show up every single day — and get you past the "I know the basics" stage into the "I move like the computer is an extension of my hands" stage. That's the goal. Let's go.

---

## 1. LINUX MASTERY

Think of Linux as the operating system that respects you enough to show you everything. No hidden task managers, no opaque system processes, no black boxes. Every process, every file handle, every network connection is inspectable from the command line. Once you internalize this, debugging stops being guesswork and starts being archaeology — you dig until you find exactly what's happening, and then you fix it.

The commands in this section are your shovel.

### 1.1 Process Management

You will hit a moment where something is consuming your CPU, eating your RAM, or holding a port hostage. These are the commands you reach for. `htop` for interactive exploration, `ps` for scripting and automation, `kill` when it's time to be decisive.

```bash
# View processes
ps aux                          # All processes, full detail
ps aux | grep node              # Find specific processes
ps -eo pid,ppid,%cpu,%mem,cmd --sort=-%cpu | head -20  # Top CPU consumers

# Interactive monitoring
top -o %CPU                     # Sort by CPU (press 'c' for full command, 'k' to kill)
htop                            # Better top: tree view, mouse support, filtering
  # F4 = filter, F5 = tree view, F6 = sort, F9 = kill

# Kill processes
kill <pid>                      # Graceful (SIGTERM, 15)
kill -9 <pid>                   # Force (SIGKILL) — last resort, no cleanup
kill -HUP <pid>                 # Reload config (SIGHUP)
killall node                    # Kill all processes by name
pkill -f "node server.js"      # Kill by pattern match on full command

# Priority
nice -n 10 ./heavy-task.sh     # Start with lower priority (range: -20 highest to 19 lowest)
renice -n 5 -p <pid>           # Change running process priority
```

### 1.2 Disk & File System

Disk space problems are always urgent and always discovered at the worst time. Have these commands ready before you need them.

```bash
# Disk usage
df -h                           # Filesystem usage, human-readable
df -i                           # Inode usage (can run out before disk space)
du -sh /var/log/*               # Size of each item in a directory
du -sh . --max-depth=1 | sort -hr  # Biggest directories, sorted
ncdu /                          # Interactive disk usage explorer (install: apt/brew install ncdu)

# Open files
lsof -i :3000                  # What process is using port 3000?
lsof -p <pid>                  # All files opened by a process
lsof +D /var/log               # All open files in a directory

# Disk I/O
iostat -x 1                    # Extended disk stats every second
iotop                          # Top-like I/O monitor (needs root)
```

### 1.3 Networking

The gap between "I think there's a network issue" and "here is exactly what is wrong" comes down to knowing these commands. `ss` replaced `netstat`, `mtr` replaced `traceroute`, and `curl -v` is still the fastest way to see what's actually happening at the HTTP layer.

```bash
# Connection inspection
ss -tlnp                       # Listening TCP sockets with process info (replaces netstat)
ss -s                          # Socket statistics summary
netstat -tlnp                  # Legacy equivalent of ss -tlnp

# HTTP requests
curl -s https://api.example.com/health | jq .          # GET with JSON formatting
curl -X POST -H "Content-Type: application/json" \
  -d '{"key":"value"}' https://api.example.com/data    # POST JSON
curl -o /dev/null -s -w "%{http_code} %{time_total}s\n" https://example.com  # Response code + timing
curl -v https://example.com 2>&1 | grep -E "^[<>]"     # See request/response headers
curl -L --max-redirs 5 https://example.com              # Follow redirects
wget -r -np -nd -A "*.csv" https://example.com/data/    # Recursive download, specific file types

# DNS
dig example.com                 # DNS lookup (detailed)
dig +short example.com A        # Just the IP
dig @8.8.8.8 example.com       # Query specific DNS server
nslookup example.com           # Simpler DNS lookup
host example.com               # Simplest DNS lookup

# Path tracing
traceroute example.com         # Show network hops
mtr example.com                # Continuous traceroute with stats (combines ping + traceroute)

# Packet capture
tcpdump -i any port 443 -c 50        # Capture 50 packets on port 443
tcpdump -i eth0 -A 'port 80'         # Show ASCII content of HTTP traffic
tcpdump -w capture.pcap -i any       # Write to file for Wireshark analysis
```

### 1.4 Text Processing

This is where Linux becomes a superpower. These compose together via pipes, and that composition is where the magic happens. A senior engineer with `grep`, `awk`, `sed`, and `jq` can extract insights from a million-line log file in under a minute. These tools are not old — they are timeless.

```bash
# grep — search content
grep -r "TODO" --include="*.py" .           # Recursive search in Python files
grep -n "error" /var/log/app.log            # Show line numbers
grep -c "500" access.log                    # Count matches
grep -B3 -A3 "Exception" app.log           # 3 lines before/after each match
grep -v "^#" config.conf                   # Exclude comment lines
grep -P "\d{3}-\d{4}" contacts.txt         # Perl regex (PCRE)
grep -l "secret" *.env                     # List only filenames with matches

# sed — stream editor (find and replace)
sed 's/old/new/g' file.txt                 # Replace all occurrences (prints to stdout)
sed -i 's/old/new/g' file.txt              # In-place replace
sed -i.bak 's/old/new/g' file.txt         # In-place with backup
sed -n '10,20p' file.txt                   # Print lines 10-20
sed '/^$/d' file.txt                       # Delete blank lines
sed 's/^[ \t]*//' file.txt                 # Strip leading whitespace

# awk — column-oriented processing
awk '{print $1, $4}' access.log            # Print columns 1 and 4
awk -F',' '{print $2}' data.csv            # CSV: print second column
awk '$3 > 500 {print $0}' data.txt         # Filter rows where col 3 > 500
awk '{sum+=$1} END {print sum}' nums.txt   # Sum a column
awk '{count[$1]++} END {for (k in count) print count[k], k}' log | sort -rn  # Frequency count
awk -F: '{print $1, $3}' /etc/passwd       # Parse /etc/passwd

# cut, sort, uniq — quick data wrangling
cut -d',' -f2,4 data.csv                  # Extract CSV columns 2 and 4
cut -d' ' -f1 access.log | sort | uniq -c | sort -rn | head -20  # Top 20 IPs in access log
sort -t',' -k3 -n data.csv                # Sort CSV by column 3, numeric
sort -u file.txt                           # Sort and deduplicate

# xargs — build commands from stdin
find . -name "*.log" -mtime +30 | xargs rm       # Delete logs older than 30 days
cat urls.txt | xargs -P 4 -I {} curl -s {}       # Parallel curl, 4 at a time
git branch --merged | grep -v main | xargs git branch -d  # Delete merged branches

# jq — JSON processing (essential for APIs)
curl -s https://api.github.com/users/torvalds | jq '.name, .public_repos'
echo '{"users":[{"name":"a","age":30},{"name":"b","age":25}]}' | jq '.users[] | select(.age > 28)'
jq -r '.items[].name' response.json        # Raw output (no quotes)
jq '.[] | {name: .name, count: .stats.count}' data.json  # Reshape objects
jq -s 'map(.price) | add' items.json       # Sum prices across array
```

### 1.5 File Operations

```bash
# find — locate files
find . -name "*.py" -type f                       # Find Python files
find . -name "*.log" -mtime +7 -delete            # Delete logs older than 7 days
find . -size +100M -type f                         # Files larger than 100MB
find . -name "*.js" -not -path "*/node_modules/*"  # Exclude directories
find . -type f -name "*.go" -exec grep -l "TODO" {} \;  # Find Go files containing TODO
find . -newer reference_file -type f               # Files modified after reference_file
find . -perm 777 -type f                           # Find world-writable files (security audit)

# Permissions
chmod 755 script.sh            # rwxr-xr-x (owner: all, group+others: read+execute)
chmod 600 .env                 # rw------- (owner read+write only — use for secrets)
chmod +x deploy.sh             # Add execute permission
chmod -R g+w shared/           # Recursively add group write
chown -R app:app /var/www      # Change owner recursively
chown --reference=ref.txt target.txt  # Match permissions of another file

# Links
ln -s /path/to/original link_name    # Symbolic link (shortcut)
ln /path/to/original hard_link       # Hard link (same inode, survives original deletion)

# Archives
tar czf archive.tar.gz directory/    # Create gzipped tar
tar xzf archive.tar.gz               # Extract gzipped tar
tar xzf archive.tar.gz -C /target/   # Extract to specific directory
tar tzf archive.tar.gz               # List contents without extracting
tar czf backup-$(date +%Y%m%d).tar.gz --exclude='node_modules' --exclude='.git' project/
```

### 1.6 Bash Scripting Essentials

Every bash script you write for production should start with this single line. It's the difference between a script that fails loudly and one that silently eats errors while mutating your data. The rest follows from there.

```bash
#!/usr/bin/env bash
set -euo pipefail  # THE most important line in any bash script
# -e: Exit on any error
# -u: Error on undefined variables
# -o pipefail: Pipeline fails if ANY command in the pipe fails

# Variables
readonly APP_NAME="myservice"          # Constants with readonly
DB_HOST="${DB_HOST:-localhost}"         # Default value if not set
TIMESTAMP=$(date +%Y%m%d_%H%M%S)      # Command substitution

# Functions
deploy() {
    local env="${1:?Error: environment required}"  # Required parameter with error message
    local version="${2:-latest}"                   # Optional parameter with default
    echo "Deploying ${APP_NAME} v${version} to ${env}"
}

# Conditionals
if [[ -f "/etc/app.conf" ]]; then
    source /etc/app.conf
elif [[ -f "./app.conf" ]]; then
    source ./app.conf
else
    echo "No config found" >&2    # Write errors to stderr
    exit 1
fi

# String comparisons (always use [[ ]] over [ ])
[[ "$ENV" == "production" ]]       # Equality
[[ "$version" =~ ^[0-9]+\. ]]     # Regex match
[[ -z "$VAR" ]]                    # Empty check
[[ -n "$VAR" ]]                    # Non-empty check

# Loops
for service in api worker scheduler; do
    systemctl restart "$service"
done

for file in /var/log/*.log; do
    gzip "$file"
done

while IFS= read -r line; do         # Read file line by line (safe with spaces)
    process "$line"
done < input.txt

# Error handling with trap
cleanup() {
    rm -f "$TMPFILE"
    echo "Cleaned up temp files"
}
trap cleanup EXIT                   # Run cleanup on ANY exit (success or failure)
trap 'echo "Error on line $LINENO"; exit 1' ERR  # Catch errors with line number

TMPFILE=$(mktemp)                   # Create safe temp file

# Useful patterns
# Retry with backoff
retry() {
    local max_attempts="${1}"; shift
    local delay="${1}"; shift
    local attempt=1
    while (( attempt <= max_attempts )); do
        "$@" && return 0
        echo "Attempt $attempt/$max_attempts failed. Retrying in ${delay}s..."
        sleep "$delay"
        (( attempt++ ))
        (( delay *= 2 ))
    done
    return 1
}
retry 3 2 curl -f https://api.example.com/health

# Parallel execution
pids=()
for host in server1 server2 server3; do
    ssh "$host" "sudo apt update && sudo apt upgrade -y" &
    pids+=($!)
done
for pid in "${pids[@]}"; do wait "$pid"; done
```

### 1.7 Process Management (systemd, jobs, sessions)

```bash
# systemd — managing services
systemctl status nginx                  # Check service status
systemctl start/stop/restart nginx      # Control service
systemctl enable nginx                  # Start on boot
systemctl list-units --failed           # See what's broken
systemctl list-timers                   # See scheduled timers

# journalctl — reading systemd logs
journalctl -u nginx -f                  # Follow logs for a service
journalctl -u nginx --since "1 hour ago"
journalctl -u nginx --since "2024-01-15 10:00" --until "2024-01-15 12:00"
journalctl -p err -b                    # Errors from current boot
journalctl --disk-usage                 # How much space logs are using
journalctl --vacuum-size=500M           # Trim logs to 500MB

# Background jobs
long_task &                             # Run in background
jobs                                    # List background jobs
fg %1                                   # Bring job 1 to foreground
bg %1                                   # Resume stopped job in background
disown %1                               # Detach job from shell (survives logout)
nohup ./script.sh > output.log 2>&1 &  # Survive logout + redirect output

# screen / tmux (persistent sessions — see section 2.5 for tmux deep dive)
screen -S deploy                        # Create named session
screen -r deploy                        # Reattach
screen -ls                              # List sessions
```

### 1.8 SSH Mastery

Here's the SSH secret most developers learn too late: `~/.ssh/config` is a superpower hiding in plain sight. Instead of typing `ssh -i ~/.ssh/prod_ed25519 -p 2222 deploy@10.0.1.50` every time, you type `ssh prod`. Twelve keystrokes instead of fifty. More importantly, it eliminates the mental overhead of remembering host details, so your brain is free to think about what you're actually doing on that server.

```bash
# ~/.ssh/config — the single most impactful SSH optimization
Host prod
    HostName 10.0.1.50
    User deploy
    IdentityFile ~/.ssh/prod_ed25519
    Port 2222

Host staging
    HostName 10.0.2.50
    User deploy
    ProxyJump bastion              # Jump through bastion host automatically

Host bastion
    HostName bastion.example.com
    User admin
    IdentityFile ~/.ssh/bastion_key

Host *
    ServerAliveInterval 60         # Keep connections alive
    ServerAliveCountMax 3
    AddKeysToAgent yes             # Auto-add keys to agent
    IdentitiesOnly yes             # Only use specified keys
    ControlMaster auto             # Connection multiplexing (reuse connections)
    ControlPath ~/.ssh/sockets/%r@%h-%p
    ControlPersist 600             # Keep master connection for 10 min
```

```bash
# Now you just type:
ssh prod                                    # Instead of: ssh -i ~/.ssh/key -p 2222 deploy@10.0.1.50
scp file.tar.gz prod:/opt/app/              # SCP uses the same config

# Tunneling
ssh -L 5432:db.internal:5432 bastion       # Local: access remote DB on localhost:5432
ssh -R 8080:localhost:3000 prod             # Remote: expose local dev server on prod:8080
ssh -D 1080 bastion                         # SOCKS proxy through bastion

# Agent forwarding (use your local keys on remote machines)
ssh -A bastion                              # Forward SSH agent
# On bastion, you can now: git clone git@github.com:org/repo.git

# Key management
ssh-keygen -t ed25519 -C "user@machine"    # Generate key (ed25519 > RSA)
ssh-copy-id prod                           # Copy public key to server
ssh-add -l                                 # List loaded keys
ssh-add ~/.ssh/prod_ed25519                # Add key to agent
```

### 1.9 Performance Debugging

When something is slow or broken and you don't know why, these tools let you see inside a running process. `strace` is particularly mind-bending the first time you use it — you can literally watch a process open files, make network calls, allocate memory, all in real time. It's like X-ray vision for your programs.

```bash
# strace — trace system calls (the "printf debugging" of Linux)
strace -p <pid>                            # Attach to running process
strace -p <pid> -e trace=network           # Only network calls
strace -c -p <pid>                         # Summary: count/time per syscall
strace -f -e trace=open,read ./app         # Trace child processes too
strace -e trace=write -s 1024 -p <pid>     # See what a process is writing

# /proc filesystem — live kernel data
cat /proc/<pid>/status                     # Process info (memory, threads, state)
cat /proc/<pid>/fd                         # Open file descriptors
cat /proc/<pid>/cmdline | tr '\0' ' '      # Full command line
cat /proc/meminfo                          # System memory breakdown
cat /proc/loadavg                          # Load average (1, 5, 15 min)
cat /proc/cpuinfo | grep "model name" | head -1  # CPU info

# System performance
vmstat 1 5                                 # Virtual memory stats every 1s, 5 times
                                           # Columns: procs, memory, swap, io, system, cpu
mpstat -P ALL 1                            # Per-CPU utilization
sar -u 1 5                                 # CPU utilization history
sar -r 1 5                                 # Memory utilization
sar -n DEV 1 5                             # Network stats

# perf — CPU profiling
perf top                                   # Live function-level CPU profiling
perf record -g ./my_app                    # Record profile with call graphs
perf report                                # Analyze recorded profile
perf stat ./my_app                         # Execution statistics

# dmesg — kernel messages
dmesg -T | tail -50                        # Recent kernel messages with timestamps
dmesg -T | grep -i "oom"                   # Check for Out-Of-Memory kills
dmesg -T | grep -i "error"                 # Hardware/driver errors
```

### 1.10 Cron Jobs

```bash
# crontab format: minute hour day-of-month month day-of-week command
# Edit with: crontab -e
# List with: crontab -l

# Examples
0 * * * *     /opt/scripts/health-check.sh          # Every hour
*/5 * * * *   /opt/scripts/collect-metrics.sh        # Every 5 minutes
0 2 * * *     /opt/scripts/db-backup.sh              # Daily at 2am
0 3 * * 0     /opt/scripts/weekly-report.sh          # Sundays at 3am
0 0 1 * *     /opt/scripts/monthly-cleanup.sh        # 1st of each month

# Best practices
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
MAILTO=ops@example.com           # Email on failure

# Always redirect output and use flock to prevent overlap
*/5 * * * * flock -n /tmp/collect.lock /opt/scripts/collect-metrics.sh >> /var/log/collect.log 2>&1
```

### 1.11 File Permissions Deep Dive

```bash
# Numeric permissions: read(4) + write(2) + execute(1)
# 755 = rwxr-xr-x  (executables, directories)
# 644 = rw-r--r--  (regular files)
# 600 = rw-------  (secrets, private keys)
# 700 = rwx------  (private directories, scripts)

# umask — default permission mask
umask 022      # New files: 644, new dirs: 755 (most common)
umask 077      # New files: 600, new dirs: 700 (paranoid)

# Special bits
chmod u+s binary        # setuid: runs as file owner (e.g., /usr/bin/passwd)
chmod g+s directory     # setgid: new files inherit group
chmod +t /tmp           # sticky bit: only owner can delete their files

# ACLs — granular permissions beyond owner/group/other
setfacl -m u:deploy:rwx /var/www           # Grant user 'deploy' full access
setfacl -m g:developers:rx /opt/app        # Grant group read+execute
getfacl /var/www                            # View ACLs
setfacl -R -m u:deploy:rwx /var/www        # Recursive
```

---

## 2. SHELL PRODUCTIVITY

Your shell is where you spend your life as an engineer. Every second you spend navigating history the slow way, typing out long file paths, or waiting to remember a command you've run a hundred times — that's friction. Friction accumulates. The engineers who feel impossibly fast have mostly just eliminated friction at this level.

The good news: a well-configured shell is a one-time investment with a lifetime payoff. Spend a weekend getting this right and you'll benefit for years. Chapter 36 (Beast Mode toolchain) covers the full setup; here we focus on the tools themselves.

### 2.1 Zsh + Prompt Configuration

```bash
# Install Oh My Zsh
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"

# Essential Oh My Zsh plugins (~/.zshrc)
plugins=(
    git                 # git aliases (gst, gco, gp, gl, etc.)
    z                   # Jump to frecent directories: z myproject
    docker              # Docker completions
    kubectl             # Kubectl completions + aliases
    fzf                 # Fuzzy finder integration
    zsh-autosuggestions           # Fish-like suggestions (needs separate install)
    zsh-syntax-highlighting       # Syntax highlighting in terminal
)

# Install the two external plugins
git clone https://github.com/zsh-users/zsh-autosuggestions ${ZSH_CUSTOM}/plugins/zsh-autosuggestions
git clone https://github.com/zsh-users/zsh-syntax-highlighting ${ZSH_CUSTOM}/plugins/zsh-syntax-highlighting
```

**Starship prompt** (alternative to Oh My Zsh themes — faster, cross-shell):

```bash
# Install
curl -sS https://starship.rs/install.sh | sh

# Add to ~/.zshrc
eval "$(starship init zsh)"

# ~/.config/starship.toml — minimal, fast, informative
[character]
success_symbol = "[>](bold green)"
error_symbol = "[>](bold red)"

[git_branch]
format = "[$symbol$branch]($style) "

[git_status]
format = '([$all_status$ahead_behind]($style) )'

[nodejs]
format = "[$symbol($version)]($style) "
detect_files = ["package.json"]

[python]
format = "[$symbol$virtualenv]($style) "

[kubernetes]
disabled = false
format = '[$symbol$context( \($namespace\))]($style) '

[cmd_duration]
min_time = 2000  # Show execution time for commands > 2s
```

### 2.2 Shell Aliases & Functions

This is your personal CLI. Treat it like code — review it, refactor it, keep it in version control. Every alias here represents a command you will type thousands of times. Every function is a tiny program that solves a problem you have repeatedly. Add these to `~/.zshrc` or `~/.bashrc` and never type the long form again.

```bash
# ── Navigation ──
alias ..="cd .."
alias ...="cd ../.."
alias ....="cd ../../.."
alias ll="ls -la"
alias la="ls -A"

# ── Git (beyond oh-my-zsh defaults) ──
alias gs="git status -sb"
alias gc="git commit"
alias gca="git commit --amend"
alias gco="git checkout"
alias gcb="git checkout -b"
alias gd="git diff"
alias gds="git diff --staged"
alias gl="git log --oneline --graph --decorate -20"
alias gla="git log --oneline --graph --decorate --all"
alias gp="git push"
alias gpf="git push --force-with-lease"    # Safe force push
alias gpl="git pull --rebase"
alias grbi="git rebase -i"
alias gst="git stash"
alias gstp="git stash pop"
alias gwip="git add -A && git commit -m 'WIP [skip ci]'"  # Quick save
alias gunwip="git log -1 --format='%s' | grep -q 'WIP' && git reset HEAD~1"

# ── Docker ──
alias d="docker"
alias dc="docker compose"
alias dcu="docker compose up -d"
alias dcd="docker compose down"
alias dcl="docker compose logs -f"
alias dps="docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
alias dprune="docker system prune -af --volumes"
alias dex="docker exec -it"

# ── Kubernetes ──
alias k="kubectl"
alias kgp="kubectl get pods"
alias kgs="kubectl get svc"
alias kgd="kubectl get deployments"
alias kga="kubectl get all"
alias kdp="kubectl describe pod"
alias kl="kubectl logs -f"
alias kex="kubectl exec -it"
alias kpf="kubectl port-forward"
alias kctx="kubectx"
alias kns="kubens"
alias kwatch="watch -n1 kubectl get pods"

# ── Useful functions ──
# Create directory and cd into it
mkcd() { mkdir -p "$1" && cd "$1"; }

# Extract any archive
extract() {
    case "$1" in
        *.tar.bz2) tar xjf "$1" ;;
        *.tar.gz)  tar xzf "$1" ;;
        *.tar.xz)  tar xJf "$1" ;;
        *.bz2)     bunzip2 "$1" ;;
        *.gz)      gunzip "$1" ;;
        *.tar)     tar xf "$1" ;;
        *.zip)     unzip "$1" ;;
        *.7z)      7z x "$1" ;;
        *)         echo "'$1' unknown archive type" ;;
    esac
}

# Quick HTTP server in current directory
serve() { python3 -m http.server "${1:-8000}"; }

# Show top N largest files in current directory tree
biggest() { find . -type f -exec du -h {} + | sort -rh | head -"${1:-20}"; }

# Quick port check
listening() { lsof -iTCP -sTCP:LISTEN -n -P | grep -i "${1:-}"; }
```

### 2.3 fzf — Fuzzy Finder (Game Changer)

If there's one tool in this entire chapter that will make you immediately, visibly faster the first day you use it — it's fzf. Install it and then press `Ctrl+R` to search your command history. You'll never go back to the default reverse-search again.

`fzf` is the kind of tool that, once you understand what it actually does (pipe any list of things → interactive fuzzy filter → output selection), you start seeing applications for it everywhere. History search, file selection, git branch switching, process killing — all become interactive and blazing fast.

```bash
# Install
brew install fzf        # macOS
sudo apt install fzf    # Ubuntu
$(brew --prefix)/opt/fzf/install   # Install key bindings + completions

# The three core key bindings (after installation):
# Ctrl+R  — Fuzzy search command history (replaces default reverse search)
# Ctrl+T  — Fuzzy find files and insert path
# Alt+C   — Fuzzy find directories and cd into them

# Configure in ~/.zshrc
export FZF_DEFAULT_COMMAND='fd --type f --hidden --exclude .git'
export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"
export FZF_ALT_C_COMMAND='fd --type d --hidden --exclude .git'
export FZF_DEFAULT_OPTS='--height 40% --layout=reverse --border'

# Power combos
# Interactive git branch checkout
alias gbf='git branch -a | fzf | sed "s/remotes\/origin\///" | xargs git checkout'

# Interactive process kill
alias fkill='ps aux | fzf --multi | awk "{print \$2}" | xargs kill -9'

# Interactive git log browser
alias glf='git log --oneline | fzf --preview "git show {+1}" | awk "{print \$1}"'

# Open file in editor with preview
alias vf='fzf --preview "bat --color=always {}" | xargs -r nvim'

# Search environment variables
alias envf='env | fzf'

# Docker container selection
alias dsel='docker ps --format "{{.Names}}" | fzf | xargs docker exec -it'
```

### 2.4 Modern CLI Replacements

Think of these as the same tools you know, but rebuilt with everything the original authors would have done differently if they'd started today. `rg` is not just faster than `grep` — it's smarter (respects `.gitignore` automatically, shows context by default, handles binary files gracefully). `fd` is not just faster than `find` — it's got a sane syntax you can actually remember. These aren't experimental toys. They're production tools used daily by engineers who care about their time.

```bash
# ripgrep (rg) over grep — 5-10x faster, respects .gitignore
rg "TODO" --type py                     # Search Python files
rg "function.*export" -g "*.ts"         # Glob filter
rg "error" --count                      # Count per file
rg "password" --hidden -g '!.git'       # Include hidden, exclude .git
rg -l "deprecated"                      # List files only
rg "pattern" -A 5 -B 2                  # Context lines
rg --json "TODO" | jq                   # Machine-readable output

# fd over find — simpler syntax, faster, respects .gitignore
fd ".py$"                               # Find Python files
fd -e log -x rm                         # Find and delete log files
fd -e test.ts --exec wc -l              # Count lines in test files
fd -H -t f ".env"                       # Include hidden files
fd "migration" --type d                 # Find directories

# bat over cat — syntax highlighting, git changes, line numbers
bat src/main.rs                         # Highlighted output
bat -p src/main.rs                      # Plain (no line numbers/headers)
bat --diff src/main.rs                  # Show git changes
bat -l json < response.txt             # Force language

# eza (formerly exa) over ls
eza -la --git --icons                   # Long list with git status + icons
eza --tree --level=2 --icons            # Tree view
eza -la --sort=modified                 # Sort by modified time
eza --tree --ignore-glob="node_modules|.git"

# delta — better git diffs (set as git pager, see section 5.6)
# dust — better du (visual disk usage)
# procs — better ps
# bottom (btm) — better top/htop
# zoxide — smarter z/cd (learns your habits)
```

### 2.5 tmux Deep Dive

tmux is the tool that separates engineers who work on servers from engineers who work *with* servers. It gives you persistent terminal sessions that outlive your SSH connection, multiple panes for monitoring while you code, and named sessions you can attach and detach freely. Think of it as a window manager for your terminal.

The configuration below is battle-tested. The key remaps to `Ctrl+a` (instead of the default `Ctrl+b`) because `Ctrl+a` is on the home row and doesn't require moving your hand. The vim-style pane navigation means your muscle memory transfers. Set this up once and forget about it — it just works.

```bash
# Start/manage sessions
tmux new -s work                       # New named session
tmux ls                                # List sessions
tmux attach -t work                    # Reattach
tmux kill-session -t work              # Kill session

# Key bindings (prefix is Ctrl+b by default, most people remap to Ctrl+a)
# Sessions
# prefix + d       detach
# prefix + s       list sessions (interactive)
# prefix + $       rename session

# Windows (tabs)
# prefix + c       new window
# prefix + n/p     next/previous window
# prefix + 0-9     jump to window N
# prefix + ,       rename window
# prefix + &       close window

# Panes (splits)
# prefix + %       vertical split
# prefix + "       horizontal split
# prefix + arrow   navigate panes
# prefix + z       zoom pane (toggle fullscreen)
# prefix + x       close pane
# prefix + space   cycle pane layouts
# prefix + {/}     swap pane position
```

**~/.tmux.conf** (battle-tested config):

```bash
# Remap prefix to Ctrl+a
unbind C-b
set -g prefix C-a
bind C-a send-prefix

# Start windows and panes at 1, not 0
set -g base-index 1
setw -g pane-base-index 1

# Intuitive splits (and open in current path)
bind | split-window -h -c "#{pane_current_path}"
bind - split-window -v -c "#{pane_current_path}"

# Vim-style pane navigation
bind h select-pane -L
bind j select-pane -D
bind k select-pane -U
bind l select-pane -R

# Resize panes with Vim keys
bind -r H resize-pane -L 5
bind -r J resize-pane -D 5
bind -r K resize-pane -U 5
bind -r L resize-pane -R 5

# Mouse support
set -g mouse on

# Better colors
set -g default-terminal "tmux-256color"
set -ag terminal-overrides ",xterm-256color:RGB"

# Faster escape (for vim)
set -s escape-time 0

# Increase history
set -g history-limit 50000

# Reload config
bind r source-file ~/.tmux.conf \; display "Reloaded"

# Vi mode for copy
setw -g mode-keys vi
bind -T copy-mode-vi v send -X begin-selection
bind -T copy-mode-vi y send -X copy-pipe-and-cancel "pbcopy"  # macOS
# bind -T copy-mode-vi y send -X copy-pipe-and-cancel "xclip -selection clipboard"  # Linux

# Plugins (via TPM — tmux plugin manager)
set -g @plugin 'tmux-plugins/tpm'
set -g @plugin 'tmux-plugins/tmux-resurrect'    # Save/restore sessions across restarts
set -g @plugin 'tmux-plugins/tmux-continuum'    # Auto-save every 15 min
set -g @continuum-restore 'on'

run '~/.tmux/plugins/tpm/tpm'
```

### 2.6 direnv — Per-Project Environment Variables

Every project has different environment variables: different database URLs, different API keys, different AWS profiles. The naive solution is to manually export them every time you switch projects. The `direnv` solution is to define them in an `.envrc` file and have them load automatically when you `cd` into the project — and unload automatically when you leave.

This is surprisingly transformative. No more "why is my test database pointing at production" because you forgot to switch environments. No more environment variables leaking between projects. Each project gets its own clean environment.

```bash
# Install
brew install direnv      # macOS
sudo apt install direnv  # Ubuntu

# Add to ~/.zshrc
eval "$(direnv hook zsh)"

# Usage: create .envrc in project root
# ~/projects/api/.envrc
export DATABASE_URL="postgresql://localhost:5432/api_dev"
export REDIS_URL="redis://localhost:6379"
export AWS_PROFILE="api-dev"
export NODE_ENV="development"

# Approve the file (security feature — must explicitly allow)
cd ~/projects/api
direnv allow

# Now these vars are set when you cd into the project, unset when you leave
# .envrc supports anything bash supports:
source_env .env                      # Source a .env file
PATH_add bin                         # Add ./bin to PATH
layout python3                       # Auto-activate Python venv
use node                             # Auto-use .node-version
```

### 2.7 Shell History Tricks

Your shell history is a searchable log of everything you've ever done. Most engineers use maybe 10% of its power. These are the shortcuts that unlock the rest — the ones that feel like cheating once you know them.

```bash
!!                    # Repeat last command
sudo !!               # Re-run last command with sudo (the classic)
!$                    # Last argument of previous command
!^                    # First argument of previous command
!*                    # All arguments of previous command
!:2                   # Second argument of previous command
!grep                 # Last command starting with 'grep'
!grep:p               # Print (don't execute) last grep command
^old^new              # Replace 'old' with 'new' in last command and run

# In ~/.zshrc: increase history
HISTSIZE=100000
SAVEHIST=100000
HISTFILE=~/.zsh_history
setopt SHARE_HISTORY          # Share history between sessions
setopt HIST_IGNORE_ALL_DUPS   # No duplicates
setopt HIST_IGNORE_SPACE      # Commands starting with space are not recorded
setopt HIST_REDUCE_BLANKS     # Remove extra blanks

# Ctrl+R (enhanced with fzf) — the single most useful shell shortcut
```

---

## 3. VIM / NEOVIM

Let's address the elephant in the room: learning Vim feels slow at first. For a few days, you'll be slower than you were in your normal editor. This is completely normal and entirely worth pushing through.

Here's why Vim is worth it: Vim's commands compose. `d` deletes, `w` moves to the next word, `i` means "inner", and combining them gives you `diw` — delete inner word. Learn ten operators and ten motion commands and you have one hundred combinations. Every new motion or operator you learn multiplies what you already know. This is fundamentally different from memorizing keyboard shortcuts, where each shortcut does exactly one thing.

You don't have to go all-in on Vim as your primary editor. Even if you use VS Code, learning Vim motions (via the VSCodeVim extension) will make you faster in your editor. And when you're on a remote server with nothing but `vi` installed, you won't be helpless.

### 3.1 Essential Motions (The 20% That Matters)

Start here. Master these before touching anything else. Most Vim users are productive with exactly these motions — the rest is polish.

```
# Movement
h j k l          Left, Down, Up, Right
w / b            Forward/backward by word
e                End of word
0 / $            Start/end of line
^ / g_           First/last non-blank character
gg / G           Top/bottom of file
{ / }            Previous/next paragraph (blank line)
Ctrl+d / Ctrl+u  Half-page down/up
Ctrl+f / Ctrl+b  Full-page down/up
f{char} / F{char}  Jump to next/previous {char} on line
t{char} / T{char}  Jump to just before/after {char}
;                Repeat last f/F/t/T
%                Jump to matching bracket/paren
H / M / L        Top/middle/bottom of screen
*                Search for word under cursor (forward)
#                Search for word under cursor (backward)
```

### 3.2 The Verb-Noun Grammar (Vim's Superpower)

This is the moment Vim clicks. Once you understand the grammar, you stop memorizing commands and start *speaking* Vim. Operators are verbs (`d` = delete, `c` = change, `y` = yank). Text objects are nouns (`w` = word, `"` = inside quotes, `{` = inside braces). Modifiers connect them (`i` = inner, `a` = around).

Vim commands compose: **verb + modifier + noun**.

```
Verbs (operators):
  d   delete         c   change (delete + enter insert)
  y   yank (copy)    v   visual select
  >   indent         <   unindent
  =   auto-indent    g~  toggle case
  gu  lowercase      gU  uppercase

Modifiers:
  i   inner          a   around (includes delimiters)
  t   till (up to)   f   find (including char)

Nouns (text objects):
  w   word           W   WORD (whitespace-delimited)
  s   sentence       p   paragraph
  b   block (parens) B   Block (braces)
  t   tag (HTML/XML)
  "   double quotes  '   single quotes  `   backticks
  (   parentheses    {   braces         [   brackets

# Combinations (this is where it clicks):
diw     Delete inner word (cursor anywhere in word)
ci"     Change inside double quotes
da(     Delete around parentheses (includes the parens)
yi{     Yank inside braces
vip     Visual select inner paragraph
>i{     Indent inside braces
dit     Delete inside HTML tag
ca[     Change around brackets
gUiw    Uppercase inner word

# Real examples:
# Cursor on: function greet("hello world") {
ci"         → function greet("|") {           # Replace string content
da(         → function greet {                # Delete parens and content
di{         → function greet("hello world") { | }  # Empty the function body
```

### 3.3 Visual Mode

```
v       Character-wise visual (select characters)
V       Line-wise visual (select whole lines)
Ctrl+v  Block (column) visual selection

# Block select is incredibly powerful:
# 1. Ctrl+v to enter block mode
# 2. Select a column of text (j/k to extend)
# 3. I to insert at beginning of each line (Shift+I)
# 4. Type text, press Esc — applies to all lines
# 5. Or: d to delete the column, c to change it

# Example: Add "// " comment prefix to lines 10-20:
# Go to line 10: 10G
# Block select: Ctrl+v
# Go to line 20: 20G
# Insert at start: I
# Type: // (space)
# Press Esc — all lines are commented
```

### 3.4 Registers & Macros

Registers are Vim's 26+ clipboards. Most editors have one clipboard. Vim has one per letter of the alphabet, plus special-purpose registers for system clipboard, last yank, last search, and more. This sounds excessive until you're refactoring code and need to swap two things without the first paste overwriting what you copied.

Macros take this further: record any sequence of commands into a register, replay it any number of times. The classic use case is transforming a list of lines where each transformation is identical but too complex to do with a simple regex.

```
# Registers (vim has 26+ clipboards)
"ayy     Yank line into register 'a'
"ap      Paste from register 'a'
"+y      Yank to system clipboard
"+p      Paste from system clipboard
"0p      Paste last yanked text (not deleted text — very useful)
:reg     View all registers

# Macros — record and replay sequences
qq       Start recording macro into register 'q'
(do your edits)
q        Stop recording
@q       Replay macro
@@       Replay last macro
10@q     Replay macro 10 times
100@q    Replay 100 times (stops on error, so safe to overshoot)

# Example macro: Convert "key: value" lines to JSON
# Start: name: John
# Goal:  "name": "John",
# Record: qq 0 i" Esc ea" Esc f: la " Esc A", Esc j q
# Apply to next 50 lines: 50@q
```

### 3.5 Search & Replace

```
# Search
/pattern          Search forward
?pattern          Search backward
n / N             Next/previous match
* / #             Search word under cursor forward/backward

# Replace
:s/old/new/       Replace first on current line
:s/old/new/g      Replace all on current line
:%s/old/new/g     Replace all in file
:%s/old/new/gc    Replace all with confirmation (y/n each)
:10,20s/old/new/g Replace in line range

# Regex examples
:%s/\v(\w+)@(\w+)/\2: \1/g              # Swap parts: user@host → host: user
:%s/console\.log(.*)/\/\/ &/g            # Comment out all console.log lines
:%s/\s\+$//e                             # Remove trailing whitespace
:'<,'>s/\v^/  /                          # Indent visual selection (add 2 spaces)

# Search across files (with quickfix list)
:vimgrep /pattern/g **/*.py              # Search Python files
:copen                                   # Open results
:cnext / :cprev                          # Navigate results
```

### 3.6 Splits & Buffers

```
# Splits
:sp file          Horizontal split
:vsp file         Vertical split
Ctrl+w h/j/k/l   Navigate splits
Ctrl+w =          Equalize split sizes
Ctrl+w _          Maximize current split height
Ctrl+w |          Maximize current split width
Ctrl+w r          Rotate splits
Ctrl+w o          Close all other splits

# Buffers
:e file           Open file in buffer
:ls               List buffers
:bn / :bp         Next/previous buffer
:bd               Close buffer
:b partial_name   Switch to buffer by partial name match
Ctrl+^            Toggle between last two buffers
```

### 3.7 Must-Have Neovim Plugins

Modern Neovim with lazy.nvim, LSP, and Telescope is a legitimate alternative to VS Code — faster, more composable, runs in the terminal, and scriptable with Lua. If you're going to invest in Vim, invest in Neovim. This plugin setup gives you fuzzy file finding, full language intelligence, git integration, and completions — the features that make modern editors feel essential.

```lua
-- Modern Neovim plugin setup with lazy.nvim
-- ~/.config/nvim/init.lua

-- Bootstrap lazy.nvim (plugin manager)
local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not vim.loop.fs_stat(lazypath) then
  vim.fn.system({ "git", "clone", "--filter=blob:none",
    "https://github.com/folke/lazy.nvim.git", lazypath })
end
vim.opt.rtp:prepend(lazypath)

require("lazy").setup({
  -- Telescope: fuzzy finder for everything (files, grep, buffers, git)
  { "nvim-telescope/telescope.nvim", dependencies = { "nvim-lua/plenary.nvim" } },

  -- Treesitter: syntax highlighting, text objects, code navigation
  { "nvim-treesitter/nvim-treesitter", build = ":TSUpdate" },
  "nvim-treesitter/nvim-treesitter-textobjects",  -- Custom text objects (function, class, etc.)

  -- LSP: language intelligence (go-to-definition, references, rename, diagnostics)
  "neovim/nvim-lspconfig",
  "williamboman/mason.nvim",           -- Auto-install LSP servers
  "williamboman/mason-lspconfig.nvim",

  -- Autocompletion
  "hrsh7th/nvim-cmp",
  "hrsh7th/cmp-nvim-lsp",
  "hrsh7th/cmp-buffer",
  "hrsh7th/cmp-path",
  "L3MON4D3/LuaSnip",                 -- Snippets engine

  -- Git
  "tpope/vim-fugitive",               -- :Git blame, :Git diff, :Git log
  "lewis6991/gitsigns.nvim",          -- Git gutter signs, inline blame

  -- Quality of life
  "tpope/vim-surround",               -- cs"' (change surrounding " to ')
  "tpope/vim-commentary",             -- gcc to toggle comment
  "windwp/nvim-autopairs",            -- Auto close brackets
  "kyazdani42/nvim-tree.lua",         -- File explorer
})

-- Essential keymaps
vim.g.mapleader = " "  -- Space as leader key

-- Telescope
vim.keymap.set("n", "<leader>ff", "<cmd>Telescope find_files<cr>")    -- Find files
vim.keymap.set("n", "<leader>fg", "<cmd>Telescope live_grep<cr>")     -- Grep project
vim.keymap.set("n", "<leader>fb", "<cmd>Telescope buffers<cr>")       -- Switch buffer
vim.keymap.set("n", "<leader>fr", "<cmd>Telescope oldfiles<cr>")      -- Recent files
vim.keymap.set("n", "<leader>gs", "<cmd>Telescope git_status<cr>")    -- Git status

-- LSP keymaps (set when LSP attaches to buffer)
-- gd = go to definition, gr = find references, K = hover docs
-- <leader>rn = rename, <leader>ca = code action
```

### 3.8 .vimrc / init.lua Essentials

```lua
-- ~/.config/nvim/init.lua (core settings)
local opt = vim.opt

opt.number = true              -- Line numbers
opt.relativenumber = true      -- Relative line numbers (makes motions like 5j intuitive)
opt.expandtab = true           -- Spaces over tabs
opt.shiftwidth = 4             -- Indent size
opt.tabstop = 4                -- Tab display width
opt.smartindent = true         -- Auto-indent new lines
opt.wrap = false               -- No line wrapping
opt.cursorline = true          -- Highlight current line
opt.ignorecase = true          -- Case-insensitive search...
opt.smartcase = true           -- ...unless uppercase used
opt.hlsearch = false           -- Don't persist search highlight
opt.incsearch = true           -- Incremental search
opt.termguicolors = true       -- Full color support
opt.scrolloff = 8              -- Keep 8 lines visible above/below cursor
opt.signcolumn = "yes"         -- Always show sign column (prevents layout shift)
opt.updatetime = 50            -- Faster updates (default 4000ms)
opt.clipboard = "unnamedplus"  -- System clipboard integration
opt.undofile = true            -- Persistent undo (survives closing file)
opt.swapfile = false           -- No swap files

-- Fast escape from insert mode
vim.keymap.set("i", "jk", "<Esc>")

-- Move selected lines up/down in visual mode
vim.keymap.set("v", "J", ":m '>+1<CR>gv=gv")
vim.keymap.set("v", "K", ":m '<-2<CR>gv=gv")

-- Keep cursor centered when scrolling
vim.keymap.set("n", "<C-d>", "<C-d>zz")
vim.keymap.set("n", "<C-u>", "<C-u>zz")

-- Keep search results centered
vim.keymap.set("n", "n", "nzzzv")
vim.keymap.set("n", "N", "Nzzzv")

-- Quick save and quit
vim.keymap.set("n", "<leader>w", ":w<CR>")
vim.keymap.set("n", "<leader>q", ":q<CR>")
```

---

## 4. VS CODE PRODUCTIVITY

VS Code is where most engineers live, and most of them are using maybe 20% of what it can do. The gap between a developer who knows their editor and one who doesn't is visible in every pair programming session — one person is constantly reaching for the mouse, navigating menus, waiting for dialogs. The other is already done.

The shortcuts below are not trivia. They're the difference between editing that feels like thinking and editing that feels like fighting your tool. Learn the navigation shortcuts first — those have the highest daily leverage. Then multi-cursor. Then the rest.

If you're pairing Vim motions with VS Code (via the VSCodeVim extension), you get the best of both worlds: VS Code's ecosystem and Vim's editing efficiency. Chapter 17 covers how Claude Code integrates into this workflow as an AI co-pilot running directly in your terminal.

### 4.1 Essential Keyboard Shortcuts

These are the shortcuts that eliminate mouse usage. Learn 2-3 per week until they are muscle memory.

```
# Navigation
Ctrl+P (Cmd+P)              Quick Open file (type partial name)
Ctrl+Shift+P (Cmd+Shift+P) Command Palette (access every VS Code command)
Ctrl+G                      Go to line number
Ctrl+Shift+O               Go to symbol in file (functions, classes)
Ctrl+T                      Go to symbol in workspace
F12                         Go to definition
Alt+F12                     Peek definition (inline popup)
Shift+F12                   Find all references
Ctrl+Shift+\               Jump to matching bracket
Ctrl+Tab                    Cycle open editors
Alt+Left/Right              Navigate back/forward (breadcrumb history)
Ctrl+\                      Split editor

# Editing
Ctrl+D (Cmd+D)              Select next occurrence (multi-cursor on same word)
Ctrl+Shift+L (Cmd+Shift+L) Select ALL occurrences (refactor in place)
Alt+Click                   Add cursor at click position
Alt+Up/Down                 Move line up/down
Alt+Shift+Up/Down           Copy line up/down
Ctrl+Shift+K                Delete entire line
Ctrl+/ (Cmd+/)              Toggle line comment
Ctrl+Shift+A                Toggle block comment
Ctrl+[ / Ctrl+]             Indent / unindent line
Ctrl+Shift+[ / ]            Fold / unfold code block
Ctrl+L                      Select entire line
Ctrl+Shift+Enter            Insert line above
Ctrl+Enter                  Insert line below

# Search
Ctrl+F                      Find in file
Ctrl+H                      Find and replace in file
Ctrl+Shift+F (Cmd+Shift+F) Find in all files (global search)
Ctrl+Shift+H                Replace in all files

# Terminal
Ctrl+` (Ctrl+`)             Toggle integrated terminal
Ctrl+Shift+`                New terminal
Ctrl+Shift+5                Split terminal

# Sidebar
Ctrl+B                      Toggle sidebar
Ctrl+Shift+E                Explorer
Ctrl+Shift+G                Source Control
Ctrl+Shift+X                Extensions
Ctrl+Shift+D                Debug
```

### 4.2 Multi-Cursor Mastery

Multi-cursor is one of those features that, once you see an expert use it, you can't unsee. The technique: select a word, `Ctrl+D` to grab the next occurrence, repeat until you have all the ones you want, then type the replacement. Every cursor edits simultaneously. No find-and-replace dialog, no regex, just direct manipulation at multiple points at once.

```
# The workflow that replaces most find-and-replace:
# 1. Select a word
# 2. Ctrl+D repeatedly to select next occurrences
# 3. Type to replace all selected at once
# 4. Ctrl+K, Ctrl+D to skip an occurrence

# Column editing:
# 1. Alt+Shift+drag mouse for rectangular selection
# 2. Or: Ctrl+Shift+Up/Down to add cursors above/below
# 3. Home/End to align cursors to line start/end

# Advanced: Add cursors using regex
# 1. Ctrl+H to open replace
# 2. Enable regex mode (Alt+R)
# 3. Search for pattern
# 4. Ctrl+Shift+L to select all matches
# 5. Escape replace dialog — now you have cursors at every match
```

### 4.3 Essential Extensions

Extensions are where VS Code becomes your custom-built tool. The list below isn't a catalog — it's gear selection for a mission. `ErrorLens` alone might save you more time than anything else here; seeing errors inline without having to hover or check the Problems panel removes a small friction from every minute of coding. `GitLens` is like turning on x-ray vision for your codebase — every line shows you who wrote it, when, and why.

```json
// Must-install extensions (Extension ID for quick install)
{
    // Code intelligence
    "GitHub.copilot",                    // AI completion
    "GitHub.copilot-chat",              // AI chat in sidebar

    // Git
    "eamodio.gitlens",                  // Git blame, history, comparison
    // Inline blame on every line, file history, branch comparison

    // Error visibility
    "usernamehw.errorlens",             // Show errors INLINE (not just underline)
    // This single extension saves more time than any other

    // API testing
    "humao.rest-client",               // Send HTTP requests from .http files
    // Or: "rangav.vscode-thunder-client" for Postman-like UI

    // Docker
    "ms-azuretools.vscode-docker",     // Dockerfile syntax, compose, container management

    // Remote development
    "ms-vscode-remote.remote-ssh",      // Edit files on remote servers
    "ms-vscode-remote.remote-containers", // Dev inside containers
    "ms-vscode-remote.remote-wsl",      // WSL integration

    // Quality
    "dbaeumer.vscode-eslint",          // ESLint integration
    "esbenp.prettier-vscode",         // Prettier formatting

    // Productivity
    "christian-kohler.path-intellisense", // Autocomplete file paths
    "streetsidesoftware.code-spell-checker", // Catch typos in code
    "Gruntfuggly.todo-tree",          // Aggregate all TODO/FIXME/HACK comments
}
```

### 4.4 Workspace vs User Settings

The settings hierarchy is worth understanding: user settings apply globally to all your projects, workspace settings (`.vscode/settings.json`) override them per-project. Use workspace settings to enforce project conventions — tab size, formatter, language-specific rules — so everyone on the team gets the same experience regardless of their personal preferences.

```jsonc
// User settings (global): Ctrl+, → open settings.json
// ~/.config/Code/User/settings.json (Linux)
// ~/Library/Application Support/Code/User/settings.json (macOS)

{
    "editor.fontSize": 14,
    "editor.fontFamily": "'JetBrains Mono', 'Fira Code', monospace",
    "editor.fontLigatures": true,
    "editor.formatOnSave": true,
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.minimap.enabled": false,           // Minimap is wasted space
    "editor.bracketPairColorization.enabled": true,
    "editor.guides.bracketPairs": "active",
    "editor.stickyScroll.enabled": true,       // Shows current scope at top
    "editor.inlineSuggest.enabled": true,
    "editor.linkedEditing": true,              // Auto-rename HTML tags

    "workbench.colorTheme": "One Dark Pro",
    "workbench.startupEditor": "none",
    "workbench.editor.enablePreview": false,   // Clicking always opens (not preview)

    "files.autoSave": "onFocusChange",
    "files.trimTrailingWhitespace": true,
    "files.insertFinalNewline": true,

    "terminal.integrated.defaultProfile.linux": "zsh",
    "terminal.integrated.fontSize": 13,

    "explorer.confirmDelete": false,
    "explorer.confirmDragAndDrop": false,

    "search.exclude": {
        "**/node_modules": true,
        "**/dist": true,
        "**/build": true,
        "**/.git": true
    }
}

// Workspace settings (per-project): .vscode/settings.json
{
    "editor.tabSize": 2,                       // Override for this project
    "typescript.tsdk": "node_modules/typescript/lib",
    "eslint.workingDirectories": ["packages/*"],
    "[python]": {
        "editor.defaultFormatter": "ms-python.black-formatter",
        "editor.tabSize": 4
    }
}
```

### 4.5 Tasks & Launch Configurations

VS Code tasks and launch configs are the difference between "I have to switch terminals to run tests" and "I press one key and tests run in a dedicated panel." Set these up once per project and your entire team benefits. Commit them to `.vscode/` in source control.

```jsonc
// .vscode/tasks.json — automate build/test/lint
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "dev",
            "type": "shell",
            "command": "npm run dev",
            "isBackground": true,
            "problemMatcher": "$tsc-watch",
            "group": "build"
        },
        {
            "label": "test",
            "type": "shell",
            "command": "npm test -- --watchAll",
            "group": "test",
            "presentation": { "reveal": "always", "panel": "dedicated" }
        },
        {
            "label": "lint:fix",
            "type": "shell",
            "command": "npm run lint -- --fix",
            "problemMatcher": "$eslint-stylish"
        }
    ]
}

// .vscode/launch.json — debug configurations
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Debug Server",
            "type": "node",
            "request": "launch",
            "runtimeExecutable": "npm",
            "runtimeArgs": ["run", "dev"],
            "console": "integratedTerminal",
            "env": { "DEBUG": "*" }
        },
        {
            "name": "Debug Current Test",
            "type": "node",
            "request": "launch",
            "program": "${workspaceFolder}/node_modules/.bin/jest",
            "args": ["--runInBand", "--no-coverage", "${relativeFile}"],
            "console": "integratedTerminal"
        },
        {
            "name": "Attach to Process",
            "type": "node",
            "request": "attach",
            "port": 9229
        }
    ]
}
```

### 4.6 Custom Snippets

Snippets are tiny programs that eliminate boilerplate. The `rfc` snippet below generates a complete typed React component from two keystrokes. The `tca` snippet gives you a complete async try-catch block. Every time you type the same structural code, that's a snippet waiting to be created.

```jsonc
// Ctrl+Shift+P → "Configure User Snippets" → typescript.json
{
    "Console Log Variable": {
        "prefix": "clv",
        "body": "console.log('${1:variable}:', ${1:variable});",
        "description": "Console.log a variable with label"
    },
    "Try-Catch Async": {
        "prefix": "tca",
        "body": [
            "try {",
            "  const ${1:result} = await ${2:asyncCall}();",
            "  $0",
            "} catch (error) {",
            "  console.error('${2:asyncCall} failed:', error);",
            "  throw error;",
            "}"
        ]
    },
    "Express Route Handler": {
        "prefix": "route",
        "body": [
            "router.${1|get,post,put,delete|}('/${2:path}', async (req, res) => {",
            "  try {",
            "    $0",
            "    res.json({ success: true });",
            "  } catch (error) {",
            "    console.error('${2:path} error:', error);",
            "    res.status(500).json({ error: 'Internal server error' });",
            "  }",
            "});"
        ]
    },
    "React Functional Component": {
        "prefix": "rfc",
        "body": [
            "interface ${1:Component}Props {",
            "  $2",
            "}",
            "",
            "export function ${1:Component}({ $3 }: ${1:Component}Props) {",
            "  return (",
            "    <div>",
            "      $0",
            "    </div>",
            "  );",
            "}"
        ]
    }
}
```

---

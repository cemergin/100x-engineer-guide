<!--
  CHAPTER: 12
  TITLE: Practical Developer Tooling & Productivity
  PART: III — Tooling & Practice
  PREREQS: None
  KEY_TOPICS: Linux commands, bash scripting, SSH, shell productivity, fzf, tmux, Vim/Neovim, VS Code, Git advanced, Docker, Terraform, kubectl
  DIFFICULTY: Beginner → Advanced
  UPDATED: 2026-03-24
-->

# Chapter 12: Practical Developer Tooling & Productivity

> **Part III — Tooling & Practice** | Prerequisites: None | Difficulty: Beginner to Advanced

The practical hard skills that eliminate friction — Linux mastery, shell productivity, editor efficiency, Git wizardry, and infrastructure CLI tools that make you measurably faster every day.

### In This Chapter
- Linux Mastery
- Shell Productivity
- Vim / Neovim
- VS Code Productivity
- Git Mastery
- Docker for Daily Use
- Terraform Essentials
- Kubernetes CLI (kubectl)
- Quick Reference: The Commands You Will Use Daily

### Related Chapters
- Chapter 7 — infrastructure concepts behind Docker/Terraform/K8s
- Chapter 20 — environment management
- Chapter 15 — Git workflows in teams

---

## 1. LINUX MASTERY

### 1.1 Process Management

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

This is where Linux becomes a superpower. These compose together via pipes.

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

Add these to `~/.zshrc` or `~/.bashrc`:

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

### 3.1 Essential Motions (The 20% That Matters)

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

## 5. GIT MASTERY

### 5.1 Interactive Rebase (The Most Powerful Git Feature)

```bash
# Rewrite the last 5 commits
git rebase -i HEAD~5

# The editor opens with:
# pick abc1234 Add user model
# pick def5678 Fix typo in user model
# pick ghi9012 Add user service
# pick jkl3456 WIP debugging
# pick mno7890 Add user controller

# Change 'pick' to:
# pick   = keep commit as-is
# squash = merge into previous commit (combine messages)
# fixup  = merge into previous commit (discard this message)
# reword = keep commit, edit message
# edit   = pause here to amend
# drop   = delete commit

# Common rewrite: clean up before PR
# pick abc1234 Add user model
# fixup def5678 Fix typo in user model    ← fold into previous
# pick ghi9012 Add user service
# drop jkl3456 WIP debugging              ← remove entirely
# pick mno7890 Add user controller

# Autosquash workflow (the pro way):
git commit --fixup=abc1234               # Create fixup commit targeting abc1234
git commit --fixup=abc1234               # Another fixup
git rebase -i --autosquash HEAD~5        # Fixups auto-arranged next to their targets
```

### 5.2 Essential Advanced Commands

```bash
# Cherry-pick: grab specific commits from other branches
git cherry-pick abc1234                  # Apply single commit
git cherry-pick abc1234..def5678         # Apply range
git cherry-pick -n abc1234              # Apply without committing (stage only)

# Bisect: binary search for the commit that introduced a bug
git bisect start
git bisect bad                           # Current commit is broken
git bisect good v1.0.0                   # This tag was working
# Git checks out middle commit — test it, then:
git bisect good                          # or: git bisect bad
# Repeat until git identifies the exact commit
git bisect reset                         # Return to original branch

# Automated bisect (provide a test script):
git bisect start HEAD v1.0.0
git bisect run npm test                  # Runs tests at each step automatically

# Reflog: your safety net (every HEAD change is recorded for 90 days)
git reflog                               # See history of HEAD positions
git checkout HEAD@{5}                    # Go back to 5 moves ago
git branch recover-branch HEAD@{5}      # Create branch from old state

# Undo almost anything:
git reset --hard HEAD@{1}               # Undo last reset/rebase/merge
# "I accidentally force-pushed / rebased / deleted a branch" → reflog saves you
```

### 5.3 Branching Strategies

```
# Trunk-Based Development (recommended for most teams)
# - Everyone commits to main (or short-lived feature branches, < 2 days)
# - Feature flags for incomplete work
# - CI/CD deploys from main
# + Fast integration, less merge hell, encourages small PRs
# - Requires good CI, feature flags, and discipline

# GitHub Flow (good for open source, small teams)
# - main is always deployable
# - Feature branches → PR → review → merge to main
# - Deploy from main after merge
# + Simple, easy to understand
# - Can accumulate long-lived branches

# Git Flow (for versioned software releases)
# - main (production), develop (integration), feature/*, release/*, hotfix/*
# + Clear release process, good for versioned software
# - Complex, slow, merge conflicts between long-lived branches
# - Avoid unless you have explicit versioned releases

# Decision: Use trunk-based unless you have a specific reason not to.
```

### 5.4 Git Hooks with Husky + lint-staged

```bash
# Install
npm install -D husky lint-staged

# Initialize husky
npx husky init

# .husky/pre-commit
npx lint-staged

# .husky/commit-msg
npx commitlint --edit $1
```

```jsonc
// package.json
{
    "lint-staged": {
        "*.{ts,tsx}": ["eslint --fix", "prettier --write"],
        "*.{json,md,yml}": ["prettier --write"],
        "*.py": ["black", "ruff check --fix"]
    }
}

// commitlint.config.js — enforce Conventional Commits
module.exports = {
    extends: ['@commitlint/config-conventional'],
    // Enforces: type(scope): description
    // Types: feat, fix, docs, style, refactor, perf, test, chore, ci, build
};
```

### 5.5 Advanced Git Features

```bash
# Worktrees: multiple branches checked out simultaneously
git worktree add ../hotfix-branch hotfix/urgent-fix
cd ../hotfix-branch                      # Work on hotfix without stashing current work
git worktree remove ../hotfix-branch     # Clean up when done
git worktree list                        # See all worktrees

# Sparse checkout: only check out specific directories (huge monorepos)
git clone --sparse https://github.com/org/monorepo.git
cd monorepo
git sparse-checkout set packages/my-service shared/  # Only these directories

# Shallow clone: only recent history (faster CI)
git clone --depth 1 https://github.com/org/repo.git           # Latest commit only
git clone --depth 50 --single-branch https://github.com/org/repo.git  # 50 commits, one branch

# Partial clone: download objects on demand (huge repos)
git clone --filter=blob:none https://github.com/org/repo.git  # No file contents until needed

# Subtrees: embed another repo in a subdirectory (alternative to submodules)
git subtree add --prefix=lib/utils https://github.com/org/utils.git main --squash
git subtree pull --prefix=lib/utils https://github.com/org/utils.git main --squash
```

### 5.6 .gitconfig Optimizations

```ini
# ~/.gitconfig
[user]
    name = Your Name
    email = your@email.com

[core]
    editor = nvim
    pager = delta                           # Much better diff viewer (install: brew install git-delta)
    autocrlf = input                        # Normalize line endings
    excludesFile = ~/.gitignore_global

[interactive]
    diffFilter = delta --color-only

[delta]
    navigate = true
    side-by-side = true
    line-numbers = true
    syntax-theme = Dracula

[merge]
    conflictStyle = zdiff3                  # Shows base version in conflicts (massive help)

[diff]
    algorithm = histogram                   # Better diff algorithm than default Myers
    colorMoved = default                    # Highlight moved lines differently

[pull]
    rebase = true                           # pull --rebase by default (cleaner history)

[push]
    default = current                       # Push current branch to same-named remote
    autoSetupRemote = true                  # Auto set upstream on first push

[fetch]
    prune = true                            # Remove stale remote tracking branches

[rebase]
    autoSquash = true                       # Auto-arrange fixup! commits
    autoStash = true                        # Stash before rebase, pop after

[rerere]
    enabled = true                          # Remember conflict resolutions (REuse REcorded REsolution)

[init]
    defaultBranch = main

[alias]
    s = status -sb
    co = checkout
    cb = checkout -b
    cm = commit -m
    ca = commit --amend --no-edit
    unstage = reset HEAD --
    last = log -1 HEAD --format="%H"
    lg = log --oneline --graph --decorate --all -20
    branches = branch -a --sort=-committerdate --format='%(HEAD) %(color:yellow)%(refname:short)%(color:reset) - %(contents:subject) %(color:green)(%(committerdate:relative))%(color:reset)'
    cleanup = "!git branch --merged | grep -v '\\*\\|main\\|master\\|develop' | xargs -n 1 git branch -d"
    who = shortlog -sn --no-merges
    changed = diff --name-only HEAD~1
    undo = reset --soft HEAD~1             # Undo last commit, keep changes staged
    wip = "!git add -A && git commit -m 'WIP [skip ci]'"
```

### 5.7 Conventional Commits

```
# Format: <type>(<optional scope>): <description>
#
# Types:
# feat:     New feature (triggers MINOR version bump)
# fix:      Bug fix (triggers PATCH version bump)
# docs:     Documentation only
# style:    Formatting, semicolons, etc. (no code change)
# refactor: Code change that neither fixes nor adds feature
# perf:     Performance improvement
# test:     Adding/correcting tests
# chore:    Build process, deps, tooling
# ci:       CI/CD changes
# build:    Build system or external dependency changes
#
# Breaking changes:
# feat!: remove deprecated API    ← ! triggers MAJOR version bump
# Or add BREAKING CHANGE in footer

# Examples:
feat(auth): add OAuth2 PKCE flow
fix(api): handle null response from payment gateway
refactor(user): extract validation into shared module
perf(db): add composite index for user search query
docs(readme): add deployment instructions
chore(deps): upgrade express to 4.18.2
ci(github): add parallel test execution
feat(api)!: change response format for /users endpoint

BREAKING CHANGE: Response is now paginated. Clients must handle `next_cursor` field.
```

---

## 6. DOCKER FOR DAILY USE

### 6.1 Essential Commands

```bash
# Build & Run
docker build -t myapp:latest .                         # Build image
docker build -t myapp:latest --no-cache .               # Build without cache
docker build --target builder -t myapp:builder .        # Build specific stage
docker run -d -p 3000:3000 --name myapp myapp:latest    # Run detached with port mapping
docker run -it --rm myapp:latest /bin/sh                 # Interactive, auto-remove on exit
docker run -d --env-file .env -v $(pwd):/app myapp      # With env file and volume mount

# Inspect & Debug
docker ps                                                # Running containers
docker ps -a                                             # All containers (including stopped)
docker logs myapp -f --tail 100                          # Follow logs, last 100 lines
docker logs myapp --since 30m                            # Logs from last 30 minutes
docker exec -it myapp /bin/sh                            # Shell into running container
docker exec myapp cat /app/config.yml                    # Run single command
docker inspect myapp | jq '.[0].NetworkSettings'         # Inspect (JSON, pipe to jq)
docker stats                                             # Live resource usage
docker top myapp                                         # Processes in container

# Lifecycle
docker stop myapp                                        # Graceful stop (SIGTERM)
docker kill myapp                                        # Force stop (SIGKILL)
docker rm myapp                                          # Remove stopped container
docker rmi myapp:latest                                  # Remove image

# Cleanup (reclaim disk space)
docker system prune -af --volumes                        # Nuclear option: remove everything unused
docker image prune -a                                    # Remove unused images
docker volume prune                                      # Remove unused volumes
docker builder prune                                     # Clear build cache
docker system df                                         # Show Docker disk usage
```

### 6.2 Docker Compose for Local Development

```yaml
# docker-compose.yml — typical backend development setup
version: "3.8"

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: development                   # Multi-stage: use dev target
    ports:
      - "3000:3000"
      - "9229:9229"                          # Node.js debug port
    volumes:
      - .:/app                               # Mount source code
      - /app/node_modules                    # Except node_modules (use container's)
    environment:
      - NODE_ENV=development
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/myapp
      - REDIS_URL=redis://redis:6379
    depends_on:
      db:
        condition: service_healthy           # Wait for DB to be ready
      redis:
        condition: service_healthy
    command: npm run dev                      # Override CMD for development

  db:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: myapp
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql  # Seed data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    volumes:
      - redisdata:/data

  worker:
    build:
      context: .
      target: development
    volumes:
      - .:/app
      - /app/node_modules
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/myapp
      - REDIS_URL=redis://redis:6379
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: npm run worker:dev

volumes:
  pgdata:                                     # Named volumes persist across restarts
  redisdata:
```

```bash
# Compose commands
docker compose up -d                          # Start all services (detached)
docker compose up -d --build                  # Rebuild images before starting
docker compose down                           # Stop and remove containers
docker compose down -v                        # Also remove volumes (reset data)
docker compose logs -f api                    # Follow specific service logs
docker compose exec api sh                    # Shell into a service
docker compose ps                             # Status of services
docker compose restart api                    # Restart single service
docker compose run --rm api npm test          # Run one-off command
```

### 6.3 Multi-Stage Builds & Layer Caching

```dockerfile
# Dockerfile — production-optimized multi-stage build

# ── Stage 1: Dependencies ──
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --only=production                  # Install production deps only

# ── Stage 2: Build ──
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci                                    # Install ALL deps (including devDependencies)
COPY . .
RUN npm run build                             # Compile TypeScript, etc.

# ── Stage 3: Development (used by docker-compose target: development) ──
FROM node:20-alpine AS development
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
CMD ["npm", "run", "dev"]

# ── Stage 4: Production ──
FROM node:20-alpine AS production
WORKDIR /app
ENV NODE_ENV=production

# Non-root user (security)
RUN addgroup -g 1001 -S appgroup && adduser -S appuser -u 1001
USER appuser

COPY --from=deps /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY package.json .

EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1

CMD ["node", "dist/main.js"]
```

```
# .dockerignore — keep build context small (faster builds)
node_modules
.git
.gitignore
*.md
.env*
.vscode
coverage
dist
.nyc_output
docker-compose*.yml
Dockerfile
```

### 6.4 Docker Networking

```bash
# Default networks
docker network ls                              # List networks

# Bridge (default): containers on same bridge can communicate by container name
docker network create mynet
docker run -d --name api --network mynet myapp
docker run -d --name db --network mynet postgres
# Inside api container: curl http://db:5432 works

# Host mode: container shares host's network stack (no port mapping needed)
docker run -d --network host myapp             # App on host's port directly

# Debugging networking
docker network inspect mynet                   # See connected containers + IPs
docker exec api ping db                        # Test connectivity
docker exec api nslookup db                    # DNS resolution check
docker exec api wget -qO- http://db:5432      # HTTP check

# Port mapping
docker run -p 8080:3000 myapp                  # Host 8080 → Container 3000
docker run -p 127.0.0.1:3000:3000 myapp        # Bind to localhost only (more secure)
```

---

## 7. TERRAFORM ESSENTIALS

### 7.1 Core Workflow

```bash
# The 4-command lifecycle
terraform init      # Download providers, initialize backend, install modules
terraform plan      # Preview changes (ALWAYS review before apply)
terraform apply     # Apply changes (type 'yes' to confirm, or -auto-approve for CI)
terraform destroy   # Tear down all resources

# Plan to file (for CI/CD — ensures apply matches what was reviewed)
terraform plan -out=tfplan
terraform apply tfplan

# Targeted operations (use sparingly)
terraform plan -target=aws_instance.web         # Plan only specific resource
terraform apply -target=module.vpc              # Apply only specific module

# Formatting and validation
terraform fmt -recursive                         # Format all .tf files
terraform validate                               # Syntax and type checking
```

### 7.2 State Management

```hcl
# Remote backend (store state in S3 — never local in a team)
terraform {
  backend "s3" {
    bucket         = "mycompany-terraform-state"
    key            = "services/api/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"            # State locking (prevents concurrent applies)
    encrypt        = true
  }
}
```

```bash
# State operations
terraform state list                              # List all resources in state
terraform state show aws_instance.web             # Show details of a resource
terraform state mv aws_instance.web aws_instance.api  # Rename without destroy/recreate
terraform state rm aws_instance.legacy            # Remove from state (keeps real resource)

# Import existing resources into Terraform management
terraform import aws_instance.web i-1234567890abcdef0

# State troubleshooting
terraform state pull > state.json                 # Download state for inspection
terraform force-unlock <lock-id>                  # Break stuck lock (dangerous, coordinate with team)

# Refresh state from real infrastructure
terraform plan -refresh-only                      # See drift without changing anything
terraform apply -refresh-only                     # Update state to match reality
```

### 7.3 Modules

```hcl
# modules/vpc/main.tf — reusable VPC module
variable "name" { type = string }
variable "cidr" { type = string }
variable "azs" { type = list(string) }

resource "aws_vpc" "main" {
  cidr_block           = var.cidr
  enable_dns_hostnames = true
  tags = { Name = var.name }
}

resource "aws_subnet" "public" {
  count             = length(var.azs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.cidr, 8, count.index)
  availability_zone = var.azs[count.index]
  tags = { Name = "${var.name}-public-${var.azs[count.index]}" }
}

output "vpc_id" { value = aws_vpc.main.id }
output "public_subnet_ids" { value = aws_subnet.public[*.id] }
```

```hcl
# Using the module
module "vpc" {
  source = "./modules/vpc"        # Local module
  # source = "terraform-aws-modules/vpc/aws"   # Registry module
  # source = "git::https://github.com/org/modules.git//vpc?ref=v1.2.0"  # Git with version

  name = "production"
  cidr = "10.0.0.0/16"
  azs  = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

# Reference module outputs
resource "aws_instance" "web" {
  subnet_id = module.vpc.public_subnet_ids[0]
}
```

### 7.4 Workspaces

```bash
# Workspaces: same config, different state (good for dev/staging/prod)
terraform workspace list
terraform workspace new staging
terraform workspace new production
terraform workspace select staging
terraform workspace show                          # Current workspace
```

```hcl
# Use workspace name in configuration
locals {
  env = terraform.workspace

  instance_type = {
    dev        = "t3.micro"
    staging    = "t3.small"
    production = "t3.medium"
  }

  min_instances = {
    dev        = 1
    staging    = 2
    production = 3
  }
}

resource "aws_instance" "web" {
  instance_type = local.instance_type[local.env]
  tags = { Environment = local.env }
}
```

### 7.5 Common Patterns

```hcl
# Data sources — reference existing infrastructure
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]  # Canonical
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

# count — create N identical resources
resource "aws_instance" "web" {
  count         = var.instance_count
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.micro"
  tags = { Name = "web-${count.index}" }
}

# for_each — create resources from a map (preferred over count for non-identical resources)
variable "buckets" {
  default = {
    logs   = { versioning = true }
    assets = { versioning = false }
    backup = { versioning = true }
  }
}

resource "aws_s3_bucket" "this" {
  for_each = var.buckets
  bucket   = "${var.project}-${each.key}"
}

resource "aws_s3_bucket_versioning" "this" {
  for_each = { for k, v in var.buckets : k => v if v.versioning }
  bucket   = aws_s3_bucket.this[each.key].id
  versioning_configuration { status = "Enabled" }
}

# dynamic blocks — generate repeated nested blocks
resource "aws_security_group" "web" {
  name = "web-sg"

  dynamic "ingress" {
    for_each = var.ingress_rules
    content {
      from_port   = ingress.value.port
      to_port     = ingress.value.port
      protocol    = "tcp"
      cidr_blocks = ingress.value.cidr_blocks
    }
  }
}

# depends_on — explicit dependency (when Terraform cannot infer it)
resource "aws_instance" "web" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.micro"
  depends_on    = [aws_iam_role_policy_attachment.web]  # Ensure IAM is ready
}

# Lifecycle rules
resource "aws_instance" "web" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.micro"

  lifecycle {
    create_before_destroy = true   # Zero-downtime replacement
    prevent_destroy       = true   # Safety net for critical resources
    ignore_changes        = [tags] # Don't revert external tag changes
  }
}
```

### 7.6 Debugging

```bash
# Enable debug logging
TF_LOG=DEBUG terraform plan               # Full debug output
TF_LOG=TRACE terraform plan 2> debug.log  # Trace level to file
TF_LOG_CORE=DEBUG terraform plan          # Core only (not provider)
TF_LOG_PROVIDER=DEBUG terraform plan      # Provider only

# Console — interactive expression evaluator
terraform console
> cidrsubnet("10.0.0.0/16", 8, 1)
"10.0.1.0/24"
> length(var.azs)
3
> [for s in var.subnets : s.cidr if s.public]

# Dependency graph
terraform graph | dot -Tpng > graph.png   # Visualize resource dependencies
terraform graph -type=plan                # Show what will change
```

---

## 8. KUBERNETES CLI (kubectl)

### 8.1 Essential Commands

```bash
# Get resources
kubectl get pods                               # List pods in current namespace
kubectl get pods -A                            # All namespaces
kubectl get pods -o wide                       # Show node, IP, etc.
kubectl get pods -o yaml                       # Full YAML output
kubectl get pods -l app=api                    # Filter by label
kubectl get pods --sort-by='.status.startTime' # Sort by field
kubectl get all                                # Pods, services, deployments, etc.
kubectl get svc,deploy,pods                    # Multiple resource types

# Describe (detailed info + events — first place to look when debugging)
kubectl describe pod api-7d8f9b6c5-x2j4k
kubectl describe node worker-1
kubectl describe svc api-service

# Logs
kubectl logs api-7d8f9b6c5-x2j4k             # Pod logs
kubectl logs api-7d8f9b6c5-x2j4k -c sidecar  # Specific container
kubectl logs -f api-7d8f9b6c5-x2j4k          # Follow (tail -f)
kubectl logs -f -l app=api --all-containers   # All pods with label, all containers
kubectl logs api-7d8f9b6c5-x2j4k --previous  # Logs from crashed/previous container
kubectl logs api-7d8f9b6c5-x2j4k --since=1h  # Last hour

# Execute commands in pods
kubectl exec -it api-7d8f9b6c5-x2j4k -- /bin/sh         # Shell into pod
kubectl exec api-7d8f9b6c5-x2j4k -- env                  # Check environment
kubectl exec api-7d8f9b6c5-x2j4k -- cat /app/config.yml  # Read file
kubectl exec -it api-pod -- curl http://other-service:8080 # Test connectivity

# Port forwarding (access services locally)
kubectl port-forward svc/api-service 3000:80              # Service port forward
kubectl port-forward pod/api-7d8f9b6c5-x2j4k 3000:3000   # Pod port forward
kubectl port-forward deploy/api 3000:3000                 # Deployment port forward

# Apply and delete
kubectl apply -f deployment.yaml              # Create/update from file
kubectl apply -f k8s/                         # Apply all files in directory
kubectl apply -f https://raw.githubusercontent.com/org/repo/main/deploy.yaml  # From URL
kubectl delete -f deployment.yaml             # Delete resources defined in file
kubectl delete pod api-7d8f9b6c5-x2j4k       # Delete specific pod (will be recreated by deployment)

# Quick operations
kubectl scale deploy api --replicas=5         # Scale deployment
kubectl rollout restart deploy api            # Rolling restart (picks up configmap changes, etc.)
kubectl rollout status deploy api             # Watch rollout progress
kubectl rollout undo deploy api               # Rollback to previous version
kubectl rollout history deploy api            # See revision history

# Resource usage
kubectl top pods                               # CPU/memory per pod
kubectl top nodes                              # CPU/memory per node
kubectl top pods --sort-by=memory              # Sort by memory usage
```

### 8.2 Context & Namespace Management

```bash
# Without kubectx/kubens (built-in)
kubectl config get-contexts                    # List all contexts
kubectl config current-context                 # Show active context
kubectl config use-context production          # Switch context
kubectl config set-context --current --namespace=staging  # Set default namespace

# With kubectx/kubens (install: brew install kubectx)
kubectx                     # List contexts (interactive with fzf)
kubectx production          # Switch context
kubectx -                   # Switch to previous context

kubens                      # List namespaces (interactive with fzf)
kubens staging              # Switch namespace
kubens -                    # Switch to previous namespace
```

### 8.3 Debugging Pods

The systematic approach when a pod is not working:

```bash
# Step 1: Check pod status
kubectl get pods -l app=api
# STATUS tells you a lot:
# CrashLoopBackOff  → App crashing on start (check logs)
# ImagePullBackOff  → Cannot pull image (check image name/registry auth)
# Pending           → Cannot be scheduled (check resources/node availability)
# Init:0/1          → Init container stuck (check init container logs)
# Running (but not ready) → Readiness probe failing

# Step 2: Describe the pod (look at Events section at bottom)
kubectl describe pod api-7d8f9b6c5-x2j4k
# Events show: scheduling, pulling image, starting, probe failures, OOM kills

# Step 3: Check logs
kubectl logs api-7d8f9b6c5-x2j4k
kubectl logs api-7d8f9b6c5-x2j4k --previous    # If it crashed and restarted

# Step 4: Shell in and investigate (if pod is running)
kubectl exec -it api-7d8f9b6c5-x2j4k -- /bin/sh
# Inside: check env vars, test DNS, test connectivity
env | grep DATABASE
nslookup other-service
wget -qO- http://other-service:8080/health

# Step 5: Check events across namespace
kubectl get events --sort-by='.lastTimestamp' | tail -20
kubectl get events --field-selector reason=FailedScheduling

# Step 6: Check resource constraints
kubectl describe node <node-name>              # Check capacity vs allocated
kubectl top pods                                # Actual usage vs limits
```

### 8.4 kubectl Plugins & Tools

```bash
# krew — plugin manager for kubectl
kubectl krew install ctx ns neat stern         # Install plugins

# stern — multi-pod log tailing (essential for microservices)
brew install stern                              # Or: kubectl krew install stern
stern api                                       # Tail all pods matching "api"
stern api -n staging                            # In specific namespace
stern "api|worker" --since 5m                   # Multiple patterns, last 5 min
stern api -o json | jq                          # JSON output
stern api --exclude "health"                    # Exclude health check noise
stern api -c main                               # Specific container only

# k9s — terminal UI for Kubernetes (the best way to interact with k8s)
brew install k9s
k9s                                             # Launch TUI
k9s -n staging                                  # Start in specific namespace
k9s --context production                        # Start with specific context

# k9s shortcuts:
# :pods / :svc / :deploy / :ns     Navigate resource types
# / + pattern                      Filter
# d                                Describe
# l                                Logs
# s                                Shell into pod
# Ctrl+d                          Delete
# y                                YAML view

# kubectl neat — clean up verbose YAML output
kubectl get pod api-pod -o yaml | kubectl neat  # Remove managed fields, status, etc.

# Other useful plugins:
# kubectl tree                      Show resource ownership hierarchy
# kubectl images                    List all images in cluster
# kubectl sniff                     Start tcpdump on a pod
# kubectl who-can                   RBAC analysis
```

### 8.5 Quick Reference: Resource Shortnames

```bash
# Save keystrokes with short names
kubectl get po        # pods
kubectl get svc       # services
kubectl get deploy    # deployments
kubectl get rs        # replicasets
kubectl get ds        # daemonsets
kubectl get sts       # statefulsets
kubectl get cm        # configmaps
kubectl get secret    # secrets
kubectl get ns        # namespaces
kubectl get no        # nodes
kubectl get ing       # ingresses
kubectl get pv        # persistentvolumes
kubectl get pvc       # persistentvolumeclaims
kubectl get sa        # serviceaccounts
kubectl get ep        # endpoints
kubectl get hpa       # horizontalpodautoscalers
kubectl get cj        # cronjobs

# Custom output columns
kubectl get pods -o custom-columns=\
NAME:.metadata.name,\
STATUS:.status.phase,\
NODE:.spec.nodeName,\
IP:.status.podIP,\
RESTARTS:.status.containerStatuses[0].restartCount

# JSONPath queries
kubectl get pods -o jsonpath='{.items[*].metadata.name}'
kubectl get secret db-creds -o jsonpath='{.data.password}' | base64 -d
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.capacity.memory}{"\n"}{end}'
```

---

## QUICK REFERENCE: The Commands You Will Use Daily

| Task | Command |
|---|---|
| Find what is using a port | `lsof -i :3000` or `ss -tlnp \| grep 3000` |
| Search code fast | `rg "pattern" --type ts` |
| Find files | `fd "pattern"` |
| Fuzzy history search | `Ctrl+R` (with fzf installed) |
| Quick JSON formatting | `curl ... \| jq .` |
| Check disk space | `df -h` then `ncdu /` |
| Watch logs | `tail -f /var/log/app.log` or `journalctl -u app -f` |
| Docker cleanup | `docker system prune -af --volumes` |
| Git undo last commit | `git reset --soft HEAD~1` |
| Git find breaking commit | `git bisect start && git bisect bad && git bisect good v1.0` |
| K8s debug pod | `kubectl describe pod X` then `kubectl logs X --previous` |
| K8s multi-pod logs | `stern "api"` |
| SSH tunnel to DB | `ssh -L 5432:db.internal:5432 bastion` |
| Terraform preview | `terraform plan -out=tfplan` |
| Process tree | `ps auxf` or `htop` (F5 for tree) |

---

> **The meta-lesson:** Tools are multipliers. Spending 30 minutes learning a tool you use daily saves hundreds of hours per year. The commands in this chapter are not trivia — they are the difference between spending 10 minutes or 10 seconds on a task you do 20 times a day.

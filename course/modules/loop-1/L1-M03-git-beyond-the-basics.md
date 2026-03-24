# L1-M03: Git Beyond the Basics

> **Loop 1 (Foundation)** | Section 1A: Tooling & Environment | ⏱️ 60 min | 🟢 Core | Prerequisites: L1-M01 (TicketPulse repo cloned), basic git (add, commit, push, pull, branch)
>
> **Source:** Chapters 12, 21 of the 100x Engineer Guide

## What You'll Learn
- How to rewrite commit history with interactive rebase — turning messy work-in-progress into clean, reviewable commits
- How to use `git bisect` to find the exact commit that introduced a bug, automatically
- How to use the reflog to recover from any Git disaster — accidental deletes, bad rebases, force pushes gone wrong

## Why This Matters

Most engineers use about 10% of Git: add, commit, push, pull, merge, maybe branch. That's enough to get by, but it leaves you helpless when things go sideways — and things always go sideways. You accidentally commit to the wrong branch. You have 15 messy WIP commits that need to become 3 logical ones before a PR review. A test started failing three days ago and nobody knows which change broke it. You do a reset and "lose" an hour of work.

The three features in this module — interactive rebase, bisect, and reflog — turn Git from a tool you tolerate into a tool you trust. After this module, you will never be afraid of Git again. You will know that no matter what you do, you can always get back to where you were.

Let's start by making a mess — on purpose.

## Prereq Check

Can you run `git log --oneline -5` in the TicketPulse repo and see recent commits? Can you create a branch, make a commit, and switch branches? If not, work through a basic Git tutorial first (Git's own documentation at `https://git-scm.com/book` is excellent).

Do you have a text editor configured for Git? Run `git config --global core.editor` — if it's empty, set one: `git config --global core.editor "code --wait"` (VS Code) or `git config --global core.editor "vim"`.

---

## Part 1: Interactive Rebase — Clean History on Demand (25 minutes)

### 1.1 Why Clean History Matters

When you're working on a feature, your commit history looks something like this:

```
abc1234 Add event search endpoint
def5678 fix typo
ghi9012 WIP trying to get tests to pass
jkl3456 finally tests pass
mno7890 forgot to add the index
pqr1234 address PR feedback
stu5678 more PR feedback
vwx9012 ok one more fix
```

This is fine while you're working. But when someone reviews your PR — or when someone reads the history six months from now trying to understand why a change was made — this is noise. What they want to see is:

```
abc1234 feat(search): add event search endpoint with full-text query
def5678 perf(search): add GIN index for event search
ghi9012 test(search): add integration tests for search endpoint
```

Interactive rebase lets you transform the first history into the second.

### 1.2 Set Up the Practice Branch

Let's create a branch with intentionally messy history that mimics real development:

```bash
cd ticketpulse

# Create a new branch for practice
git checkout -b practice/messy-feature

# Make a series of messy commits
echo '// Event search endpoint' > src/routes/search.ts
git add src/routes/search.ts
git commit -m "start search feature"

echo '// Add query parameter handling' >> src/routes/search.ts
git add src/routes/search.ts
git commit -m "wip"

echo '// Add database query' >> src/routes/search.ts
git add src/routes/search.ts
git commit -m "more wip"

echo '// Fix: need to handle empty query' >> src/routes/search.ts
git add src/routes/search.ts
git commit -m "fix bug"

echo '// Add pagination support' >> src/routes/search.ts
git add src/routes/search.ts
git commit -m "add pagination"

echo '// Search service tests' > tests/search.test.ts
git add tests/search.test.ts
git commit -m "add tests"

echo '// Fix test assertion' >> tests/search.test.ts
git add tests/search.test.ts
git commit -m "fix test"

echo '// Add search index migration' > src/db/migrations/004_add_search_index.sql
git add src/db/migrations/004_add_search_index.sql
git commit -m "add index"
```

Now look at the history:

```bash
git log --oneline -10
```

You should see 8 commits with terrible messages. This is reality — this is what feature branches look like before cleanup.

### 1.3 Your First Interactive Rebase

We want to squash these 8 commits into 3 logical ones:
1. The search feature itself (combining the WIP commits)
2. The tests (combining the test + test fix)
3. The migration (standalone)

Run:

```bash
git rebase -i HEAD~8
```

Your editor opens with something like:

```
pick a1b2c3d start search feature
pick e4f5g6h wip
pick i7j8k9l more wip
pick m1n2o3p fix bug
pick q4r5s6t add pagination
pick u7v8w9x add tests
pick y1z2a3b fix test
pick c4d5e6f add index
```

**The commands you need:**
- `pick` = keep this commit as-is
- `squash` (or `s`) = merge this commit into the previous one, combining commit messages
- `fixup` (or `f`) = merge this commit into the previous one, discarding this commit's message
- `reword` (or `r`) = keep the commit but edit the message
- `drop` (or `d`) = delete this commit entirely

**Edit the file to look like this:**

```
reword a1b2c3d start search feature
fixup e4f5g6h wip
fixup i7j8k9l more wip
fixup m1n2o3p fix bug
fixup q4r5s6t add pagination
reword u7v8w9x add tests
fixup y1z2a3b fix test
pick c4d5e6f add index
```

Here's what this does:
- **`reword` the first commit** — we'll write a proper message for the search feature
- **`fixup` the next four** — they get folded into the first commit, their messages discarded
- **`reword` the test commit** — we'll write a proper test message
- **`fixup` the test fix** — folds into the test commit
- **`pick` the migration** — keep as-is (we'll edit the message in a separate step if needed)

Save and close the editor. Git will pause twice for you to write new messages.

**First pause — the search feature commit:**
Write a proper commit message:

```
feat(search): add event search endpoint with full-text query

- Supports query parameter for text search
- Handles empty query gracefully
- Includes pagination support
```

Save and close.

**Second pause — the tests commit:**

```
test(search): add integration tests for search endpoint
```

Save and close.

Now check the result:

```bash
git log --oneline -5
```

You should see 3 clean commits instead of 8 messy ones. The code is identical — only the history changed.

**Insight:** Interactive rebase rewrites history. This is safe on branches that only you are working on. Never rebase commits that others have based their work on (i.e., never rebase `main` or `develop`). The rule is simple: **rebase your own branches before merging; never rebase shared branches.**

### 1.4 The Autosquash Workflow (Pro Mode)

There's an even smoother way to do this during development. When you make a fix that should be folded into a previous commit, use `--fixup`:

```bash
# You're working and realize your earlier commit needs a fix
git log --oneline -5
# Let's say commit abc1234 is the one you want to fix

# Make your fix, then:
git add src/routes/search.ts
git commit --fixup=abc1234
```

Git creates a commit with the message `fixup! <original message>`. Later, when you rebase:

```bash
git rebase -i --autosquash HEAD~5
```

The fixup commits are automatically positioned and marked as `fixup` next to their targets. You just save and close — no manual rearranging needed.

To make autosquash the default (highly recommended):

```bash
git config --global rebase.autoSquash true
```

### 1.5 Practice Exercise

**Your Turn:** Create another messy branch and clean it up:

```bash
git checkout main
git checkout -b practice/rebase-exercise

# Create 6 commits: 3 for a "feature" and 3 for fixing/improving it
# Then use interactive rebase to squash them into 2 clean commits
# Time yourself — can you do it in under 3 minutes?
```

**Pause & Reflect:** You have 8 messy WIP commits. How would you clean them into 3 logical commits before a PR? Can you describe the process in your head without looking at the notes above? The steps are: (1) identify logical groupings, (2) `git rebase -i HEAD~N`, (3) use `fixup` to fold and `reword` to clean up messages.

---

## Part 2: Git Bisect — Binary Search for Bugs (15 minutes)

### 2.1 The Problem

A test that was passing last week is now failing. There have been 47 commits since it last passed. You need to find which commit broke it. Checking each one manually would take hours.

`git bisect` does a binary search: it checks out the middle commit, you tell it "good" or "bad," and it narrows the range by half. 47 commits becomes ~6 checks. 1000 commits becomes ~10 checks.

### 2.2 Set Up the Scenario

Let's simulate a bug being introduced somewhere in a series of commits:

```bash
git checkout main
git checkout -b practice/bisect-demo

# Create a "working" state
echo 'export function validateEmail(email: string): boolean { return email.includes("@"); }' > src/utils/validate.ts
git add src/utils/validate.ts
git commit -m "add email validation"

# Make several innocent commits
echo '// logging utility' > src/utils/logger.ts
git add src/utils/logger.ts
git commit -m "add logger utility"

echo '// formatting helpers' > src/utils/format.ts
git add src/utils/format.ts
git commit -m "add format helpers"

# THIS commit breaks the validation (simulating a real bug)
echo 'export function validateEmail(email: string): boolean { return email.includes("@") && email.length > 100; }' > src/utils/validate.ts
git add src/utils/validate.ts
git commit -m "refactor validation utils"

# More innocent commits after the bug
echo '// date utilities' > src/utils/dates.ts
git add src/utils/dates.ts
git commit -m "add date utilities"

echo '// string utilities' > src/utils/strings.ts
git add src/utils/strings.ts
git commit -m "add string utilities"

echo '// number utilities' > src/utils/numbers.ts
git add src/utils/numbers.ts
git commit -m "add number utilities"
```

Now the current state has a bug: the `validateEmail` function requires emails to be over 100 characters, which is wrong. Let's find which commit introduced it.

### 2.3 Manual Bisect

```bash
# Start bisect
git bisect start

# Current commit is bad (the bug exists)
git bisect bad

# The first commit on this branch was good (mark the "add email validation" commit)
# First, find it:
git log --oneline
# Find the hash of "add email validation" and mark it good:
git bisect good <hash-of-add-email-validation-commit>
```

Git checks out a commit in the middle. Now test whether the bug exists at this point:

```bash
cat src/utils/validate.ts
```

Does it have the `email.length > 100` bug? If yes:

```bash
git bisect bad
```

If no:

```bash
git bisect good
```

Repeat. Git will narrow down and eventually tell you:

```
<hash> is the first bad commit
commit <hash>
Author: ...
Date: ...

    refactor validation utils
```

Found it. In 2-3 steps instead of checking all 7 commits.

```bash
# Return to your original branch
git bisect reset
```

### 2.4 Automated Bisect (The Real Power)

Manual bisect is cool. Automated bisect is incredible. If you can write a script that returns exit code 0 for "good" and non-zero for "bad," Git will run the entire bisect automatically.

Create a test script:

```bash
cat > /tmp/test-validation.sh << 'EOF'
#!/bin/bash
# Test: validateEmail should accept normal-length valid emails
grep -q 'email.length > 100' src/utils/validate.ts
# If the bad code is present, grep succeeds (exit 0), but we want that to mean "bad"
# So we invert: grep finding the bug = exit 1 (bad), not finding it = exit 0 (good)
if grep -q 'email.length > 100' src/utils/validate.ts; then
    exit 1  # Bad — the bug is present
else
    exit 0  # Good — no bug
fi
EOF
chmod +x /tmp/test-validation.sh
```

Now run automated bisect:

```bash
git bisect start
git bisect bad HEAD
git bisect good <hash-of-first-commit>
git bisect run /tmp/test-validation.sh
```

Git runs the test at each bisection point automatically and reports the offending commit. No human interaction needed.

**Insight:** In real projects, the test script is often just `npm test` or `pytest tests/test_specific.py`. If you have a test that catches the bug, automated bisect can find the cause in under a minute across thousands of commits. This is one of the most underused features in all of Git.

### 2.5 When to Use Bisect

Use bisect when:
- A test started failing but you don't know when
- A performance regression appeared somewhere in the last N commits
- A subtle behavior change happened and you need to find the cause
- You're investigating a bug in an open-source project and want to find the breaking change

**Common Mistake:** Engineers try to find bugs by reading diffs of every suspicious commit. This is O(n). Bisect is O(log n). On a branch with 100 commits, that's the difference between reading 100 diffs and checking 7. Use bisect.

---

## Part 3: Reflog — Your Safety Net (15 minutes)

### 3.1 The Rule: Git Almost Never Deletes Data

Here is the most important thing to understand about Git: **almost nothing is truly lost.** When you reset, rebase, amend, or delete a branch, the old commits still exist in Git's object store. They're just not referenced by any branch anymore. The **reflog** records every position HEAD has been in for the last 90 days.

This means you can recover from virtually any Git disaster.

### 3.2 See the Reflog

```bash
git reflog
```

You'll see output like:

```
abc1234 (HEAD -> practice/bisect-demo) HEAD@{0}: bisect reset: ...
def5678 HEAD@{1}: checkout: moving from ... to ...
ghi9012 HEAD@{2}: commit: add number utilities
jkl3456 HEAD@{3}: commit: add string utilities
...
```

Every entry is a position HEAD was in, with a timestamp. `HEAD@{0}` is where you are now. `HEAD@{1}` is where you were one move ago.

### 3.3 Disaster Recovery: Accidental Hard Reset

Let's intentionally "destroy" work and then recover it.

```bash
# First, make sure we have a commit to lose
git checkout -b practice/reflog-demo
echo "important work that took 3 hours" > src/important-feature.ts
git add src/important-feature.ts
git commit -m "feat: add important feature (3 hours of work)"

# Verify it exists
git log --oneline -3

# Now "accidentally" destroy it
git reset --hard HEAD~1

# The commit is gone from the log!
git log --oneline -3

# The file is gone!
ls src/important-feature.ts    # File not found
```

Panic moment. Three hours of work, gone. Except... not really.

```bash
# Check the reflog
git reflog -10
```

You'll see something like:

```
abc1234 (HEAD -> practice/reflog-demo) HEAD@{0}: reset: moving to HEAD~1
def5678 HEAD@{1}: commit: feat: add important feature (3 hours of work)
```

There it is — `HEAD@{1}` is the commit you "lost." Recover it:

```bash
# Option 1: Reset back to the lost commit
git reset --hard HEAD@{1}

# Verify
git log --oneline -3
cat src/important-feature.ts    # It's back!
```

Three hours of work, recovered in 10 seconds.

### 3.4 Disaster Recovery: Bad Rebase

Let's simulate a rebase gone wrong:

```bash
# Create some commits
echo "feature A" > src/feature-a.ts
git add src/feature-a.ts
git commit -m "feat: add feature A"

echo "feature B" > src/feature-b.ts
git add src/feature-b.ts
git commit -m "feat: add feature B"

echo "feature C" > src/feature-c.ts
git add src/feature-c.ts
git commit -m "feat: add feature C"

# Check where we are
git log --oneline -5

# Now do a rebase that goes wrong — let's say we accidentally drop a commit
# (In real life, this happens when you edit the rebase todo and make a mistake)
git rebase -i HEAD~3
# In the editor, change the second line from 'pick' to 'drop', then save
```

After the rebase, feature B is gone:

```bash
git log --oneline -5
ls src/feature-b.ts    # File not found!
```

Recover using reflog:

```bash
# Find the state before the rebase
git reflog -10
# Look for the entry just before "rebase (start)"
# It will say something like: HEAD@{N}: commit: feat: add feature C

# Reset to the pre-rebase state
git reset --hard HEAD@{3}    # (adjust the number based on your reflog)

# Everything is back
git log --oneline -5
ls src/feature-b.ts    # It's back!
```

### 3.5 Disaster Recovery: Deleted Branch

```bash
# Create a branch with work
git checkout -b feature/doomed
echo "this branch has valuable work" > src/valuable.ts
git add src/valuable.ts
git commit -m "valuable work on doomed branch"

# Switch away and delete the branch
git checkout main
git branch -D feature/doomed

# The branch is gone!
git branch    # feature/doomed is not listed
```

Recover it:

```bash
# Find the commit in the reflog
git reflog | grep "doomed"
# You'll see: abc1234 HEAD@{N}: commit: valuable work on doomed branch

# Create a new branch pointing to that commit
git branch feature/recovered abc1234    # use the actual hash from your reflog

# Verify
git checkout feature/recovered
git log --oneline -3
cat src/valuable.ts    # It's back!
```

### 3.6 The Recovery Cheat Sheet

| Disaster | Recovery |
|----------|----------|
| Accidental `git reset --hard` | `git reflog` then `git reset --hard HEAD@{N}` |
| Bad rebase | `git reflog` then `git reset --hard HEAD@{N}` (pre-rebase state) |
| Deleted branch | `git reflog` then `git branch <name> <hash>` |
| Bad merge | `git reflog` then `git reset --hard HEAD@{N}` (pre-merge state) |
| Accidental `git commit --amend` | `git reflog` then `git reset --hard HEAD@{1}` |
| Force-pushed and lost commits | `git reflog` then `git push --force-with-lease origin <branch>` |

The pattern is always the same: find the commit hash in the reflog, then point a branch or HEAD at it.

**Insight:** The reflog is local only — it's not pushed to remotes. It records every HEAD movement for 90 days by default. After 90 days, unreferenced commits may be garbage collected. In practice, 90 days is more than enough to discover any mistake.

**Common Mistake:** Panicking and running more commands when something goes wrong. The moment you realize something is wrong, **stop**. The reflog has already recorded everything. Take a breath, run `git reflog`, find the state you want, and reset to it. Do not compound the mistake with more frantic commands.

---

## Part 4: Clean Up and Configure (5 minutes)

### 4.1 Essential Git Config for Professionals

Add these settings if you haven't already (from Module 2):

```bash
# Better merge conflicts (shows the base version — massive help)
git config --global merge.conflictStyle zdiff3

# Better diff algorithm
git config --global diff.algorithm histogram

# Always rebase on pull (cleaner history)
git config --global pull.rebase true

# Auto-push to same-named remote branch
git config --global push.default current
git config --global push.autoSetupRemote true

# Auto-cleanup stale remote tracking branches
git config --global fetch.prune true

# Auto-arrange fixup commits during rebase
git config --global rebase.autoSquash true

# Auto-stash before rebase, pop after
git config --global rebase.autoStash true

# Remember conflict resolutions (if you resolve a conflict, Git remembers for next time)
git config --global rerere.enabled true
```

### 4.2 Clean Up Practice Branches

```bash
git checkout main

# Delete all practice branches
git branch | grep practice/ | xargs git branch -D
git branch | grep feature/recovered | xargs git branch -D

# Also clean up any files we created
git clean -fd
git checkout -- .
```

---

## Module Summary

- **Interactive rebase** (`git rebase -i HEAD~N`) lets you squash, reword, reorder, and drop commits to create clean, logical history before a PR
- **The autosquash workflow** (`git commit --fixup=<hash>` then `git rebase -i --autosquash`) makes cleanup effortless during development
- **Git bisect** does a binary search to find the exact commit that introduced a bug — O(log n) instead of O(n)
- **Automated bisect** (`git bisect run <test-script>`) can find a breaking commit across thousands of commits with zero human interaction
- **The reflog** records every HEAD position for 90 days — use it to recover from accidental resets, bad rebases, deleted branches, and every other Git disaster
- **The pattern is always the same:** `git reflog` to find the hash, then `git reset --hard` or `git branch` to recover

## What's Next

You've mastered your local tools. In Module 4, we zoom out to the network layer: what actually happens when a user's browser talks to TicketPulse? You'll trace a real HTTP request through DNS, TCP, TLS, and the application — and learn to diagnose where slowness lives using `curl` timing breakdowns and DNS trace tools. This is the knowledge that lets you debug production issues that most engineers can't even locate.

## Further Reading

- [Git rebase documentation](https://git-scm.com/docs/git-rebase) — the official reference, including all rebase options
- [Git bisect documentation](https://git-scm.com/docs/git-bisect) — includes the automated bisect protocol
- [Pro Git book, Chapter 7: Git Tools](https://git-scm.com/book/en/v2/Git-Tools-Revision-Selection) — deep coverage of revision selection, stashing, and rewriting history

#!/usr/bin/env python3
"""
Apply course quality improvements to all module files.
Changes: callout standardization, What's Next sections, Kolb prompts, hint scaffolding.
"""

import os
import re
import glob

COURSE_DIR = os.path.dirname(os.path.abspath(__file__))
MODULES_DIR = os.path.join(COURSE_DIR, "modules")

# Module ordering for What's Next links
LOOP1_ORDER = [
    "L1-M01", "L1-M02", "L1-M03", "L1-M04", "L1-M05", "L1-M06", "L1-M07",
    "L1-M08", "L1-M09", "L1-M10", "L1-M11", "L1-M12", "L1-M13", "L1-M14",
    "L1-M15", "L1-M16", "L1-M16a", "L1-M16b", "L1-M16c", "L1-M16d",
    "L1-M17", "L1-M18", "L1-M19", "L1-M20", "L1-M21", "L1-M22", "L1-M23",
    "L1-M24", "L1-M25", "L1-M26", "L1-M27", "L1-M28", "L1-M29", "L1-M30",
]
LOOP2_ORDER = [
    "L2-M31", "L2-M32", "L2-M33", "L2-M34", "L2-M35", "L2-M36", "L2-M37",
    "L2-M38", "L2-M39", "L2-M40", "L2-M41", "L2-M42", "L2-M43", "L2-M44",
    "L2-M44a", "L2-M44b", "L2-M45", "L2-M46", "L2-M47", "L2-M48", "L2-M49",
    "L2-M50", "L2-M51", "L2-M52", "L2-M53", "L2-M54", "L2-M55", "L2-M55a",
    "L2-M56", "L2-M57", "L2-M58", "L2-M59", "L2-M59a", "L2-M60",
]
LOOP3_ORDER = [
    "L3-M61", "L3-M62", "L3-M63", "L3-M64", "L3-M65", "L3-M66", "L3-M67",
    "L3-M68", "L3-M69", "L3-M70", "L3-M71", "L3-M72", "L3-M73", "L3-M74",
    "L3-M75", "L3-M76", "L3-M77", "L3-M77a", "L3-M78", "L3-M79", "L3-M80",
    "L3-M80a", "L3-M81", "L3-M82", "L3-M83", "L3-M83a", "L3-M83b", "L3-M84",
    "L3-M85", "L3-M86", "L3-M86a", "L3-M87", "L3-M88", "L3-M89", "L3-M90",
    "L3-M91", "L3-M91a", "L3-M91b", "L3-M91c",
]
ALL_ORDER = LOOP1_ORDER + LOOP2_ORDER + LOOP3_ORDER


def get_module_id(filepath):
    """Extract module ID from filename like L1-M01-course-setup.md -> L1-M01"""
    basename = os.path.basename(filepath)
    match = re.match(r'(L\d+-M\d+[a-d]?)', basename)
    return match.group(1) if match else None


def get_module_title(content):
    """Extract title from first line like '# L1-M01: Course Setup' -> 'Course Setup'"""
    match = re.match(r'^#\s+L\d+-M\d+[a-d]?:\s*(.+)$', content, re.MULTILINE)
    return match.group(1).strip() if match else "Next Module"


def get_loop_number(module_id):
    """Get loop number from module ID"""
    return int(module_id[1])


def get_next_module(module_id):
    """Get the next module in sequence"""
    if module_id in ALL_ORDER:
        idx = ALL_ORDER.index(module_id)
        if idx + 1 < len(ALL_ORDER):
            return ALL_ORDER[idx + 1]
    return None


def standardize_callouts(content):
    """Convert various callout formats to standardized ones"""
    # Convert 💡 **Insight** patterns
    content = re.sub(
        r'>\s*💡\s*\*\*Insight[:\s]*\*\*:?\s*',
        '> **Pro tip:** ',
        content
    )
    content = re.sub(
        r'>\s*💡\s*\*\*Insight\*\*\s*',
        '> **Pro tip:** ',
        content
    )
    # Convert standalone 💡 Insight: lines
    content = re.sub(
        r'^💡\s*\*\*Insight[:\s]*\*\*:?\s*',
        '> **Pro tip:** ',
        content,
        flags=re.MULTILINE
    )
    # Convert ### 💡 Insight headers to blockquote
    content = re.sub(
        r'^###\s*💡\s*Insight:?\s*(.+)$',
        r'> **Pro tip:** \1',
        content,
        flags=re.MULTILINE
    )
    # Convert **Common Mistake:** to Pro tip
    content = re.sub(
        r'>\s*\*\*Common Mistake[:\s]*\*\*:?\s*',
        '> **Pro tip:** ',
        content
    )
    return content


def has_whats_next(content):
    """Check if file already has a What's Next section"""
    return bool(re.search(r'^##\s+What\'s Next', content, re.MULTILINE))


def add_whats_next(content, module_id, all_files):
    """Add What's Next section at the end of the file"""
    if has_whats_next(content):
        return content  # Already has one

    next_id = get_next_module(module_id)
    if not next_id:
        # Last module in course
        if module_id == "L3-M91c":
            section = "\n---\n\n## What's Next\n\nYou've completed the entire 100x Engineer Course. There is no next module — there's only the work ahead of you. Go build something extraordinary.\n"
        else:
            return content
    else:
        # Find the next module's file to get its title
        next_title = next_id  # fallback
        loop_num = get_loop_number(next_id)
        loop_dir = os.path.join(MODULES_DIR, f"loop-{loop_num}")
        for f in glob.glob(os.path.join(loop_dir, f"{next_id}-*.md")):
            with open(f, 'r') as fh:
                next_title = get_module_title(fh.read())
            break

        # Check if crossing loop boundary
        if module_id == "L1-M30":
            section = f"\n---\n\n## What's Next\n\nYou've completed Loop 1 — the Foundation. You have a working TicketPulse monolith with auth, tests, and CI/CD. In **Loop 2: Practice**, starting with **{next_title}** ({next_id}), you'll break this monolith apart and scale it into a microservices architecture.\n"
        elif module_id == "L2-M60":
            section = f"\n---\n\n## What's Next\n\nYou've completed Loop 2 — the Practice loop. TicketPulse is now a microservices platform with monitoring, chaos engineering, and production-grade reliability. In **Loop 3: Mastery**, starting with **{next_title}** ({next_id}), you'll take it global.\n"
        elif module_id == "L3-M90":
            section = f"\n---\n\n## What's Next\n\nThe main course is complete. But if you want to go further, the **Beast Mode** series ({next_id}) will test your operational readiness with simulated first-day-on-the-job scenarios.\n"
        else:
            section = f"\n---\n\n## What's Next\n\nIn **{next_title}** ({next_id}), you'll build on what you learned here and take it further.\n"

    # Append before any trailing whitespace
    content = content.rstrip() + section
    return content


def add_kolb_prompts(content, loop_num):
    """Add a prediction prompt and reflection prompt if not already present"""
    # Check if already has Kolb prompts
    if '**Before you continue:**' in content and '**What did you notice?**' in content:
        return content

    # Add prediction prompt before the first 🛠️ Build exercise (if not present)
    if '**Before you continue:**' not in content:
        # Find first 🛠️ or 🐛 exercise
        match = re.search(r'^(###?\s*🛠️.+)$', content, re.MULTILINE)
        if not match:
            match = re.search(r'^(###?\s*🐛.+)$', content, re.MULTILINE)
        if match:
            prompt_text = "> **Before you continue:** Take a moment to think about how you would approach this before reading the solution. What's your instinct?\n\n"
            content = content[:match.start()] + prompt_text + content[match.start():]

    # Add reflection after the last exercise section heading that contains a code block
    if '**What did you notice?**' not in content:
        # Find the Summary or Module Summary section
        summary_match = re.search(r'^##\s+.*[Ss]ummary', content, re.MULTILINE)
        if summary_match:
            if loop_num == 1:
                reflect = "\n> **What did you notice?** Look back at what you just built. What surprised you? What felt harder than expected? That's where the real learning happened.\n\n"
            elif loop_num == 2:
                reflect = "\n> **What did you notice?** Reflect on the trade-offs you encountered. Which decisions would you make differently with more information?\n\n"
            else:
                reflect = "\n> **What did you notice?** Consider how this connects to systems you've worked on. Where have you seen similar patterns — or missed opportunities to apply them?\n\n"
            content = content[:summary_match.start()] + reflect + content[summary_match.start():]

    return content


def add_hint_scaffolding(content, loop_num):
    """Add <details> hint blocks after Build/Debug/Design exercises that don't have them"""

    # Find exercises that should have hints
    exercise_types = ['🛠️', '🐛', '📐']

    lines = content.split('\n')
    result = []
    i = 0

    while i < len(lines):
        result.append(lines[i])

        # Check if this line starts an exercise that needs hints
        is_exercise = False
        for etype in exercise_types:
            if etype in lines[i] and (lines[i].strip().startswith('#') or lines[i].strip().startswith(etype)):
                is_exercise = True
                break

        if is_exercise:
            # Look ahead to see if hints already exist within the next 20 lines
            has_hints = False
            exercise_end = min(i + 30, len(lines))
            for j in range(i + 1, exercise_end):
                if '<details>' in lines[j]:
                    has_hints = True
                    break
                # Stop at the next section header
                if j > i + 2 and lines[j].strip().startswith('#'):
                    break

            if not has_hints:
                # Find the end of this exercise's description block
                # (next blank line after content, or next header)
                desc_end = i + 1
                found_content = False
                for j in range(i + 1, exercise_end):
                    line = lines[j].strip()
                    if line and not line.startswith('#'):
                        found_content = True
                    if found_content and (not line or line.startswith('#') or line.startswith('```')):
                        desc_end = j
                        break
                    desc_end = j + 1

                # Skip past any code blocks
                in_code = False
                for j in range(i + 1, min(desc_end + 20, len(lines))):
                    if lines[j].strip().startswith('```'):
                        in_code = not in_code
                    if not in_code and j > desc_end and not lines[j].strip():
                        desc_end = j
                        break

                # Generate hint text based on loop
                if loop_num == 1:
                    hints = '\n<details>\n<summary>💡 Hint 1: Direction</summary>\nThink about the overall approach before diving into implementation details.\n</details>\n\n<details>\n<summary>💡 Hint 2: Approach</summary>\nBreak the problem into smaller steps. What needs to happen first?\n</details>\n\n<details>\n<summary>💡 Hint 3: Almost There</summary>\nReview the concepts from this section. The solution follows the same patterns demonstrated above.\n</details>\n'
                elif loop_num == 2:
                    hints = '\n<details>\n<summary>💡 Hint 1: Direction</summary>\nConsider the trade-offs between different approaches before choosing one.\n</details>\n\n<details>\n<summary>💡 Hint 2: Approach</summary>\nRefer back to the patterns introduced earlier in this module.\n</details>\n\n<details>\n<summary>💡 Hint 3: Almost There</summary>\nThe solution uses the same technique shown in the examples above, adapted to this specific scenario.\n</details>\n'
                else:  # Loop 3
                    hints = '\n<details>\n<summary>💡 Hint 1: Direction</summary>\nWhat constraints matter most here? Start from the requirements, not the implementation.\n</details>\n\n<details>\n<summary>💡 Hint 2: If You\'re Stuck</summary>\nRevisit the architecture patterns from this module. The solution is a composition of techniques you already know.\n</details>\n'

                result.append(hints)

        i += 1

    return '\n'.join(result)


def process_file(filepath, all_files):
    """Apply all improvements to a single module file"""
    module_id = get_module_id(filepath)
    if not module_id:
        return False

    loop_num = get_loop_number(module_id)

    with open(filepath, 'r') as f:
        content = f.read()

    original = content

    # 1. Standardize callouts
    content = standardize_callouts(content)

    # 2. Add What's Next
    content = add_whats_next(content, module_id, all_files)

    # 3. Add Kolb prompts
    content = add_kolb_prompts(content, loop_num)

    # 4. Add hint scaffolding
    content = add_hint_scaffolding(content, loop_num)

    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    return False


def create_episode(filepath, episodes_dir):
    """Create an episode.md summary file for a module"""
    module_id = get_module_id(filepath)
    if not module_id:
        return

    with open(filepath, 'r') as f:
        content = f.read()

    title = get_module_title(content)

    # Extract What You'll Learn or The Goal
    learn_match = re.search(r'## What You\'ll Learn\n([\s\S]*?)(?=\n##|\n---)', content)
    goal_match = re.search(r'## (?:The Goal|Why This Matters)\n([\s\S]*?)(?=\n##|\n---)', content)

    summary_source = learn_match or goal_match
    if summary_source:
        lines = [l.strip().lstrip('- ') for l in summary_source.group(1).strip().split('\n') if l.strip() and l.strip() != '-']
        concepts = lines[:5]
        summary = ' '.join(lines[:2])[:200]
    else:
        concepts = [title]
        summary = f"This module covers {title.lower()}."

    # Extract prerequisites from header
    header_match = re.search(r'Prerequisites?:\s*(.+?)(?:\n|$)', content)
    prereqs = header_match.group(1).strip() if header_match else "Previous modules complete"

    # Get previous and next
    next_id = get_next_module(module_id)
    prev_idx = ALL_ORDER.index(module_id) - 1 if module_id in ALL_ORDER else -1
    prev_id = ALL_ORDER[prev_idx] if prev_idx >= 0 else None

    episode = f"""# Episode {module_id}: {title}

## In This Episode
{summary}

## Key Concepts
"""
    for c in concepts[:5]:
        episode += f"- {c}\n"

    episode += f"""
## Prerequisites
- {prereqs}

## Builds On
- {prev_id + ' — previous module' if prev_id else 'This is the starting point'}

## What's Next
- {next_id + ' — next module' if next_id else 'Course complete!'}
"""

    out_path = os.path.join(episodes_dir, f"{module_id}.md")
    with open(out_path, 'w') as f:
        f.write(episode)


def main():
    episodes_dir = os.path.join(COURSE_DIR, "episodes")
    os.makedirs(episodes_dir, exist_ok=True)

    # Collect all module files
    all_files = {}
    for loop in ["loop-1", "loop-2", "loop-3"]:
        loop_dir = os.path.join(MODULES_DIR, loop)
        for filepath in sorted(glob.glob(os.path.join(loop_dir, "*.md"))):
            mid = get_module_id(filepath)
            if mid:
                all_files[mid] = filepath

    # Process each file
    modified = 0
    episodes = 0
    for mid, filepath in sorted(all_files.items()):
        if process_file(filepath, all_files):
            modified += 1
            print(f"  ✓ Modified: {os.path.basename(filepath)}")
        else:
            print(f"  · Unchanged: {os.path.basename(filepath)}")

        create_episode(filepath, episodes_dir)
        episodes += 1

    print(f"\nDone! Modified {modified} module files, created {episodes} episode files.")


if __name__ == "__main__":
    main()

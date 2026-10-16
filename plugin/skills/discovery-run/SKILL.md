---
name: discovery-run
description: Run an AI work discovery run on this machine. It reads your own AI sessions, setup and tools, then writes a plain-text results folder to send to your consultant. Start it by typing /ai-work-discovery:discovery-run.
disable-model-invocation: true
---

# Discovery run: orchestrator

You coordinate a **discovery run** for the person in front of you, the **participant**. You are the only one who talks to them. Subagents do the reading; you keep their outputs short in your own context.

Ground rules. Each one is a commitment made to the participant in the briefing:
- **Read-only.** Never change the participant's files, settings or connected apps. Write only inside the run folder.
- **Abstracted output.** Patterns and counts, never anyone's verbatim messages. The participant's own short phrasing may appear as an illustrative excerpt (at most 25 words, at most one per pattern).
- **No scores and no advice.** The results describe what was observed. Interpretation and recommendations come later, from the consultant, together with the participant. Never write "you should", "consider", "next step", "quick win", "opportunity" or a grade.
- **Respect their time.** The participant spends at most about 10 minutes in total: the briefing, one intake reply and the hand-off. Everything else runs without them. Never ask one question at a time.
- **Third parties are protected automatically.** Names of clients, colleagues and other companies are replaced by roles. Secrets are masked.
- **Words to avoid with the participant:** "audit", "score", "rating", "pilot", "user" (say "you").

Reading files: use the Read and Grep tools, never `cat`, `grep`, `awk` or `python -c` in Bash. Bash is only for the plugin's own scripts, written exactly as shown below. Anything else stops the run with a permission prompt for the participant.

Paths: `SKILL` = `${CLAUDE_SKILL_DIR}`. `SCRIPTS` = `${CLAUDE_SKILL_DIR}/../../scripts`. `AGENTS` = the plugin's agents, called by name (`session-mapper`, `analyser`). Check the exact names with the Agent tool's list: they may be prefixed `ai-work-discovery:`.

## 0. Before the briefing (silent)

1. **Model.** If you are not an Opus model, say only: "This works best on Opus. Please type `/model opus` and then run `/ai-work-discovery:discovery-run` again." Then stop.
2. **Python.** Run `python3 --version`. On Windows, if that fails, try `py -3 --version`, then `python --version`. Use whichever works as `PY` from here on. In every command below, write `PY`, `SCRIPTS`, `SKILL` and `RUN` out literally as their actual values, never as shell variables (`$PY`). It must be 3.9 or newer. If none works, go to **Fallback: no Python** at the end.

## 1. Briefing

Show `SKILL/briefing.md` as written (read it and output its text). Fill in the two placeholders: today's date and an estimated run time ("about 20–40 minutes, mostly unattended"). Then wait. Their "yes" (in any wording) is the blanket approval for the whole run. If they decline or ask to stop, stop, and offer to delete anything created.

## 2. Probe and run folder

```bash
PY -I "SCRIPTS/discover.py" init --parent ~ --window 30
```

The output names the run folder. Call it `RUN`. Then:

```bash
PY -I "SCRIPTS/discover.py" probe --run "RUN"
PY -I "SCRIPTS/discover.py" aliases --run "RUN" --show
```

The probe says which surfaces have sessions in the last 30 days. If `suggested_path` is `chat` (fewer than 5 local sessions), tell the participant that most of their AI work doesn't seem to happen here. Ask where it does happen. If that's claude.ai or the desktop chat, point them to the chat version: the same plugin, run as `/ai-work-discovery:discovery-run-chat` in a claude.ai chat. Stop here unless they want the local run anyway.

While the participant reads the intake message below, start the **model self-assessment** in the background (step 5a). It doesn't need their answers.

Permissions: the plugin ships a hook that pre-approves exactly its own scripts (`PY -I "SCRIPTS/<name>.py" …`, with no `;`, `&&`, pipes or redirects), plus reads of the AI configuration and writes inside `RUN`. **Always write script calls in exactly that form**, one per Bash call, with no `cd` before them. Anything else will show the participant a permission prompt.

## 3. Intake: one message, one reply

First draft the **pre-filled self-report**. Read the participant's user-level instructions (`~/.claude/CLAUDE.md`) and the memory indexes (`~/.claude/projects/*/memory/MEMORY.md`, at most 5, picking the largest), plus what you already know about them. Write 4–6 short lines: role, the kinds of work they do, who they work with (as roles, not names), and which AI tools they use. Keep the draft in your context. It goes into `intake.json` as `self_report_drafted`.

Then send **one** message with these parts. Use their language, and keep the whole message to about 20 lines:

1. "Most of your AI work in the last 30 days seems to be in **<surfaces with counts>**. Is that right, or does a lot happen elsewhere (for example in claude.ai chat, ChatGPT or Copilot)?"
2. "Please type `/usage` and tell me roughly how much is left."
3. "Here's how I'd describe your work. Correct anything that's off:" followed by the draft.
4. "To protect other people, I'll hide these folder names in everything I write: <comma-separated list from `hidden_project_folders`>. Are there other names to hide, such as clients, colleagues or companies? And are any of these just ordinary words that are fine to show (like 'bookkeeping')?"
5. Optional: "One question, only if you like: what do you deliberately keep away from AI, and why?"
6. "Answer all of it in one go. Dictating is fine, typos are fine."

From the reply:
- Add every extra name with `PY -I "SCRIPTS/discover.py" aliases --run "RUN" --add "Name=a client"`, using a role that fits: `a client`, `a colleague`, `a company` or `a person`. Add **people and client names they mention anywhere in the reply** as well, not just in point 4.
- Folder names they say are fine to show: `PY -I "SCRIPTS/discover.py" aliases --run "RUN" --keep "bookkeeping"`.
- **Usage under 30% left** → light run (`--light`). Tell them in one line. Otherwise run a full run, and don't mention it.
- If most of their work happens on another surface, note it. Carry on here unless they say otherwise.
- Write `RUN/intake.json`:
  ```json
  {"self_report_drafted": "...", "self_report_corrected": "... their corrected version, or the draft if they changed nothing ...",
   "surfaces_reported": "...", "keeps_away_from_ai": "... their words, or null ...", "usage_left_reported": "..."}
  ```
- Write `RUN/.local/run-notes.json`. Fields: `path` = `local`; `primary_surface`; `other_surfaces_reported`; `coordinator_model` (your model name); `usage_left_at_start`; `run_size` (`full` or `light`); and `started` (the current time).

Then tell them: "Thanks, that's all I need. The rest runs by itself. I'll let you know when the results are ready. You don't need to watch."

## 4. Collect and map (no participant involvement)

```bash
PY -I "SCRIPTS/discover.py" collect --run "RUN"
PY -I "SCRIPTS/map_loop.py" plan --run "RUN" [--light]
```

Then start the subagents **in one message**, so that they run in parallel:

- **Session mappers.** Start ceil(queued / 30) `session-mapper` agents, at least 2 and at most 6, using model `haiku`. Each gets the prompt `RUN=<RUN> SCRIPTS=<SCRIPTS> AGENT=m<N> PY=<PY>`, plus the line "Use PY instead of python3 in commands." if PY is not `python3`.
- **One second coder.** A `session-mapper` with model `sonnet`, prompt `RUN=… SCRIPTS=… AGENT=v1 PASS=verify PY=…`.
- **Three analysers that don't need the map:** `analyser` agents for `environment`, `skills` and `automation`. Each gets the prompt `AREA=<area> RUN=<RUN> SCRIPTS=<SCRIPTS> SKILL=<SKILL> PY=<PY>`.

Never read transcripts or subagent output files yourself; wait for the agents' replies. If a mapper fails, check `map_loop.py status`. If sessions remain, start a mapper **with the same name as the one that failed** (for example `m3`). Its unfinished claim goes back to that name, so a mapper with a new name can't pick it up.

When the mappers and the second coder have finished:

```bash
PY -I "SCRIPTS/map_loop.py" status --run "RUN"
PY -I "SCRIPTS/map_loop.py" aggregate --run "RUN"
```

Then start the `analyser` agents for `session_behaviour`, `connectors` and `context_memory` in one message (same prompt shape). They use the map.

**If the Agent tool isn't available or subagents fail repeatedly**, do the same work yourself, in sequence, following `SKILL/analysers.md`. Use a light run in that case.

## 5. Self-assessment, report and checks

**5a. Model self-assessment.** Start it in the background, during intake, with Bash `run_in_background`:

```bash
PY -I "SCRIPTS/discover.py" self-assess --run "RUN"
```

This runs a separate, fresh session (`claude -p`) from the home folder. That way the AI judges the setup without this run's context. It takes 1–3 minutes.
- If it reports `"ran": true`, note `"self_assessment": "headless"` in `run-notes.json`.
- Otherwise, answer the questions in `SKILL/self-assessment.md` yourself, candidly, and note `"in-session"`.

Then turn the answer into:
- the section `RUN/.local/sections/self_assessment.md`, with the heading `## Model self-assessment`;
- 3–6 elements in `RUN/.local/elements/self_assessment.jsonl`, with `source_kind: "model_self_assessment"`, `analyser: "self_assessment"` and `dimension: "model_view"`.

Leave `self_assessment.raw.md` where it is. It's inside `.local`, so it's never sent, and deleting it would need a permission prompt.

**5b. Validate elements.** Run `PY -I "SCRIPTS/discover.py" elements --run "RUN"`. If any file has errors, fix the lines yourself (the errors say exactly what's wrong) and run the check again until it reports `clean: true`.

**5c. Report.** Read the section files in `RUN/.local/sections/*.md` and the element files. Don't read `collectors/` in full; the analysers have already summarised them. Write `RUN/report.md` following `SKILL/report-template.md`. It contains observations only, and leaves out any element marked `"sensitive": true`.

**5d. Privacy pass.**
1. Run `PY -I "SCRIPTS/discover.py" assemble --run "RUN"`.
2. Run `PY -I "SCRIPTS/sanitize.py" --run "RUN"`. Keep its counts.
3. Read `report.md` and `sections.md`, and skim `elements.jsonl`, looking for **any remaining name of a person, client or company other than the participant**, and for anything that identifies them: email addresses, phone numbers, account IDs. Software products and AI tools are fine. Add each name you find with `aliases --add "Name=<role>"`, then run `sanitize.py` again.
4. Write the counts into `run-notes.json` as `privacy_pass`. Use counts only, never the names: `{"replacements_by_label": {...}, "secrets_masked": N, "model_pass_names_added": N}`. Add `participant_active_minutes` (your estimate, usually 5–10) and `wall_minutes`.
5. Run `assemble` once more, so that the manifest picks up the notes, then `sanitize.py` again.

**5e. The gate.** Run `PY -I "SCRIPTS/check_bundle.py" "RUN"`. Fix every problem it lists, then run it again. Never hand off a bundle that doesn't pass. It enforces plain text only and no hidden names. It also rejects recommendation language, so if it flags any, rewrite those sentences as observations.

## 6. Hand-off

Send one short message:
- "Your results are ready in `RUN`. Everything in the folder is plain text, and nothing in it runs."
- Three to five sentences describing what's in the report, neutrally. No verdict.
- "Would you like to look through it first? You can open `report.md` in any text editor, or I can show it here. If you'd like anything removed, just tell me."
- "When you're happy, attach the six files (`README.txt`, `report.md`, `manifest.json`, `intake.json`, `elements.jsonl`, `sections.md`, `collectors.json`) to an email to hello@matthiasfrank-consulting.com. The hidden `.local` folder stays with you."

If they ask for changes, edit the files, run `sanitize.py` and `check_bundle.py` again, and confirm. If they ask, `open "RUN"` (macOS) or `explorer "RUN"` (Windows) shows the folder.

## Fallback: no Python

Tell the participant, in one line, how to install Python:
- macOS: `xcode-select --install`, or the installer from python.org.
- Windows: `winget install Python.Python.3.12`, or python.org.

Offer two choices: install it and restart the run, or carry on with a reduced run that you do yourself. In the reduced run, follow `SKILL/analysers.md`. Read config and memory files directly, then sample about 20 recent transcripts from `~/.claude/projects/*/*.jsonl`, reading only user and assistant text. Write the same files by hand. Mark it in `run-notes.json` as `"run_size": "reduced-no-python"`. Without the scripts the gate can't run, so before the hand-off check by eye that only `.md`, `.json`, `.jsonl` and `.txt` files are in the folder.

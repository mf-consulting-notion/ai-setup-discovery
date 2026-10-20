# Analyser briefs

Each analyser covers one **area**. It writes two files:
- `RUN/.local/sections/<area>.md`: a narrative of 150–400 words that starts with `## <Area title>`. After it come a line `Unanswered:` and up to 3 questions this area couldn't settle.
- `RUN/.local/elements/<area>.jsonl`: 4–15 evidence elements, one JSON object per line, matching `schemas/evidence-element.json`. The definitions are in `codebook.md`. Give them ids of the form `<area>-<n>`. Use `codebook_version` `"0.4.0"`.

These rules apply to every area:
- **Observations only.** No advice, no "should" or "could", no grades. Say what is there, how much, how often and since when. An absence is an observation too: "no hooks configured", "memory untouched for 60 days".
- **Support on everything.** Give counts with their base, the window and the source kind. Mark single episodes `anecdote: true`.
- **Privacy.** Keep labels like "project B" and "a client" exactly as they are. Never name people or companies other than software vendors. Never quote the participant's messages beyond one excerpt of at most 25 words. Never copy instruction or memory text: describe it ("the user instructions are 46 lines, mostly about how to ask questions and which skills are hidden").
- **Sensitive** (`"sensitive": true`): security tooling, credentials appearing in sessions, incidents involving a client. Record them, but flag them.
- **Read only what your area lists.** All collector files are in `RUN/.local/collectors/`. Read them with `discover.py show` (see your agent instructions), not ad-hoc code. Files outside the run folder may be read only where the brief says so, and must never be modified.
- **Write only about what you read.** Never write that an input is missing because it hasn't appeared yet: the orchestrator starts you once your inputs exist.
- When finished, run `PY -I SCRIPTS/discover.py elements --run RUN`. Fix any errors in your own file. Reply with only: the area, the number of elements, and `clean` or the remaining errors.

## environment
**Read:** `collectors/probe.json`, `environment.json`, `config.json` (`settings.json.cleanup_period_days`), `memory.json` (`history`), and `activity.json` (only `by_surface`, `concurrency`, `hour_of_day`, `weekday`, `sessions_per_week_by_last_activity`, `sessions_started_before_window` and `active_hours_by_project`).

**Cover:**
- **retention first:** Claude Code deletes transcripts after `cleanup_period_days` (default 30) and Codex keeps its own. Compare `memory.json` → `history.prompts_per_week_last12` (prompt history reaches further back) with the transcript weeks before describing trends. Never call use "concentrated" in recent weeks when older transcripts simply no longer exist;
- surfaces and how use splits across them (sessions and active hours);
- models used;
- rhythm: weekday and hour spread, sessions per week;
- concurrency;
- how concentrated work is in projects (the top 3 projects' share of active hours);
- other AI tools and apps present on the machine;
- chat exports in Downloads, and the Codex and Cowork footprint;
- anything that limited this run, such as a missing source or sampling.

**Dimension:** mostly `environment_setup`.

## context_memory
**Read:** `collectors/config.json` (`user_instructions`, `rules`, `projects`), `memory.json`. Also read, without quoting:
- `~/.claude/CLAUDE.md`;
- up to 5 of the largest `~/.claude/projects/*/memory/MEMORY.md` files;
- 10 memory files picked across those folders.

**Cover:**
- instruction layers (user, project), their size and age;
- whether memory is curated (indexed, typed, recently edited) or accumulating;
- staleness (old status-type memories);
- contradictions between layers;
- what the AI is told about the participant;
- projects without instructions.

Cross-check against `map/aggregate.json` if it exists, reading `restatements_by_key_sessions`: preferences typed again and again are candidates for "known but not written down". Record that as an observation.

**Dimension:** `knowledge_capture`.

## skills
**Read:** `collectors/config.json` (`skills`, `plugins`, `account_synced_skills`, `usage_counters`, `commands`, `agents`). Skill descriptions are in `skills.detail[].description`; don't open the skill files themselves.

**Cover:**
- the inventory by source (own, plugin, synced) and user-only vs automatic;
- used in the window vs never or long ago (`usage_counters`);
- the size of the visible description listing;
- skills whose descriptions overlap so much that the AI could confuse them (name the pairs);
- missing or broken skill files.

**Dimension:** `skills`.

## connectors
**Read:** `collectors/tools.json` (`connectors`, `measured_waits_over_60s`) and `config.json` (`mcp_servers_user`, `mcp_servers_project`). If `map/aggregate.json` exists, also read `systems_mentioned` and `inbound_sources` from it.

**Cover:**
- configured vs actually called;
- read vs write;
- error rates and error classes per server, especially for writes;
- how many distinct targets were touched;
- systems that sessions mention but no connector reaches (for example data pasted from a tool with no connector);
- servers with many tools but few calls;
- the slowest calls, using `measured_waits_over_60s`.

**Dimension:** `reach`.

## automation
**Read:** `collectors/config.json` (`settings.json` hooks, permissions, `statusline`, `agents`), `environment.json` (codex), `activity.json` (`concurrency`, plus `per_session` `slash_commands`), and `tools.json` (`builtin_tools`, to see the shares of Agent/Task, background shell and scheduling tools).

**Cover:**
- hooks and what events they're on;
- the permission mode, and allow/deny sizes;
- the share of sessions that use subagents;
- parallel sessions;
- headless or scheduled runs;
- worktrees;
- anything that runs without a prompt.

**Dimension:** `autonomy`.

## session_behaviour
**Read:** `map/aggregate.json` in full, and `map/records.jsonl`. You may read all records; quote nothing from them. Also read `collectors/activity.json` (`per_session` active minutes) and `tools.json` (`per_session` waits), joined on `session`.

This is the richest section, 300–600 words, with 8–15 elements. **Cover:**
- **Workflow inventory:** the recurring workflows with their counts, how they start (`start_trigger`), typical active length, their outcome mix and their friction.
- **Delegation profile:** which `work_kind` and `work_category` combinations are handed over, and with which `supervision_markers`.
- **Interaction modes:** their distribution.
- **Time per workflow and work kind:** `by_workflow_time` and `by_work_kind_time` give active hours, median minutes, outcomes and measured waits per workflow. Use them.
- **Friction:** by type, by cause, by when it was caught, and how much was avoidable. Use measured waits, not guesses. Count sessions with `by_type_sessions`, and instances with `by_type_instances`. Say which you're using. The two biggest type×cause clusters each get their own element.
- **Corrections and restatements:** the top keys, with session counts.
- **Gates** the participant states.
- **Fluency:** the behaviours with the highest and lowest share.
- **Inbound sources and artefact destinations:** how material gets in (paste, screenshot, dictation, connector) and where results end up.
- **Agreement:** the `agreement` figures. Any facet below 0.6 gets `confidence.agreement` set and is described cautiously.

**Dimensions:** `workflow`, `collaboration_pattern`, `autonomy`, `friction`, `fluency`.

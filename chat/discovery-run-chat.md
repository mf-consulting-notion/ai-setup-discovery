# AI Work Discovery: paste-in version

Paste this whole document into a new chat and send it. Everything below is the instruction set; the files it mentions are included as appendices.

---

# Discovery run: chat version

You coordinate a **discovery run** for the participant, inside a chat. The ground rules are the same as in the local version, and each one is a commitment from the briefing:
- **Read-only.** Never change chats, memory, projects or connected apps.
- **Patterns, not quotes.** Never reproduce anyone's messages. The participant's own short phrasing may appear as an illustrative excerpt of at most 25 words.
- **No scores and no advice.** You describe what you observe. Interpretation comes later, from the consultant, together with the participant. Never write "you should", "consider", "next step", "quick win", "opportunity" or a grade.
- **Respect their time.** About 10 minutes of the participant's time in total. Never ask one question at a time.
- **Third parties are protected.** Names of clients, colleagues and companies become roles ("a client", "a colleague"). Never copy secrets, email addresses, phone numbers or IDs.
- **Words to avoid:** "audit", "score", "rating", "pilot", "user" (say "you").

This skill's folder sits inside the plugin. The plugin also holds `codebook.md`, `schemas/` and `scripts/`, and `../discovery-run/` contains `briefing.md`, `analysers.md`, `report-template.md` and `self-assessment.md`. Read them from there.

## 1. Briefing

Show `../discovery-run/briefing.md` with these changes:
- "What gets read" becomes: "Your conversations from the last 30 days in this account (titles and content, read here in this chat), your memory and project instructions, and which apps are connected. Everything is read inside this chat. Nothing is sent anywhere by this run."
- The duration becomes "about 15–30 minutes, mostly without you".
- The closing question becomes: "Shall I start? If yes, reply: **Yes, you may page through my chats from the last 30 days.**"

Wait for a yes. A yes in other words counts too. Either way, treat it as the participant's explicit request to page through all their chats from the window, well beyond the handful of listing calls you'd usually make.

## 2. Capability check (silent; don't narrate it)

Find out what you have here. Check by trying where a harmless check exists:
- **Past chats:** tools that list recent conversations (on claude.ai: `recent_chats`, 20 per call, paged by date), read one in full (`read_conversation`, 50 turns per page) or search them (`conversation_search`, 10 hits per call).
  - Can the listing page back 30 days?
  - Does reading return full text or only excerpts?
  - Chats inside a Project can't be seen from a chat outside it. Note whether this chat is in a Project.
- **Code execution:** a sandbox where you can run Python. If you have one, look for this plugin's scripts with `find / -name discover.py -path '*scripts*' 2>/dev/null` and keep the folder that also holds `map_loop.py` and `check_bundle.py`. If it's there, you can use the same scripts as the local version; write `PLUGIN` below for the folder above `scripts/`. If it isn't, note `scripts: absent` and carry on without them.
- **Files:** can you send files the participant can download (on claude.ai: `SendUserFile`, one download card per file)?
- **Delegation:** a tool for starting subagents. Each subagent costs a lot to start (about 85k tokens on claude.ai), so never start more than 5 in a run.
- **Memory and projects:** whether account memory is on, and whether this chat is inside a project with instructions or knowledge.
- **Connectors:** the connected apps, by name, and whether each can read, write or both.

Keep the answers as notes, keyed by kind (`past_chats`, `code`, `scripts`, `files`, `delegation`, `memory`, `projects`, `connectors`). They go into the manifest under `capabilities`.

## 3. Intake: one message, one reply

Draft a **pre-filled self-report** (4–6 lines) from memory and what you know about the participant. Then send one message:
1. "Where does most of your AI work happen: here in claude.ai chat, the desktop app, Claude Code, ChatGPT, Copilot? Roughly what share?"
2. "How much of your plan's usage is left? (Settings → Usage)"
3. "Here's how I'd describe your work. Correct anything that's off:" followed by the draft.
4. "Are there names I should hide, such as clients, colleagues or companies? I'll replace the ones I come across anyway."
5. "Does a lot of your AI work live inside Projects? Roughly what share, and what kind of work? I can't see chats inside Projects from here."
6. Optional: "What do you deliberately keep away from AI, and why?"
7. **Only if there is no past-chats tool:** "Optional, but it helps a lot: Settings → Privacy → Export data sends you a download link by email. If you upload that file here, I can look at all your chats from the last month, not only this one."
8. "Answer all of it in one go. Dictating is fine."

Record the reply as `intake.json` (the same fields as in the local version, plus `projects_share` and `projects_work` from question 5). If usage is under 30%, run a light version: 15 conversations instead of 40.

If the participant says most of their work happens in Claude Code on their computer, tell them the local version gives a much fuller picture: install the same plugin in Claude Code and run `/ai-work-discovery:discovery-run` there. Carry on here only if they prefer.

## 4. Evidence

Pick the route by what you found:
- **B (the usual route):** a past-chats tool exists.
- **A (deeper):** the participant uploaded a data export and you have code execution with the scripts. Use it instead of B.
- **C:** neither.

Context gets cleared during long work. **Save every record to a file as soon as it exists**, never only in the conversation.

**B. Past-chats tool.**
1. List conversations from the last 30 days, newest first, paging back until you reach the window's start. Skip this conversation. Keep only ids, titles and dates.
2. Take up to 40 of them, or 15 for a light run. If there are more, spread the picks evenly across the window instead of taking the newest.
3. For each one, read it in full and write one session record that follows `codebook.md` and `schemas/session-record.json`, with `surface: "chat"` and `session` set to the first 8 characters of the conversation's id (or `c01`, `c02` and so on). Records hold codes, never content.
4. **With a delegation tool:** split the picks across 3–4 subagents (2 for a light run), about 10 each. Give each one its conversation ids, `codebook.md` and the record schema verbatim, and ask it to return only records. If a subagent can't read past chats, read and code the rest yourself.
5. **With code execution and the scripts:** append each record as one line to `/tmp/run/.local/map/records.jsonl`, after `python3 -I PLUGIN/scripts/discover.py init --out /tmp/run --home /tmp/emptyhome`. Then run `python3 -I PLUGIN/scripts/map_loop.py aggregate --run /tmp/run`. **Without it:** keep a compact tally file as you go: counts per field value, plus friction, corrections and restatements by key.

**A. Code execution with the scripts, plus an uploaded export.** Work as in the local version. Use `--home` pointing at an empty folder, and import the export:

```
python3 -I PLUGIN/scripts/discover.py init --out /tmp/run --home /tmp/emptyhome
python3 -I PLUGIN/scripts/discover.py import-chat --run /tmp/run --export <uploaded file>
python3 -I PLUGIN/scripts/discover.py aliases --run /tmp/run --add "Name=a client" ...
python3 -I PLUGIN/scripts/discover.py collect --run /tmp/run
python3 -I PLUGIN/scripts/map_loop.py plan --run /tmp/run [--cap 40]
```

Then map the sessions. Use `map_loop.py next` and `submit` exactly as described in the plugin's `agents/session-mapper.md`. With a delegation tool, start 3–4 subagents that each loop over `next` and `submit` until the queue is empty, passing them that agent file's instructions verbatim. Otherwise map them yourself, one at a time. Afterwards run `map_loop.py aggregate`.

**C. Neither.** Use only the self-report, memory, project instructions and connectors, plus this conversation. Say plainly in the manifest that past chats couldn't be read.

In every route, list what couldn't be seen as `exclusions`: chats inside Projects (with the share from intake), and conversations outside the window.

## 5. Areas, self-assessment and report

Follow `../discovery-run/analysers.md` for each area that has inputs here:
- **environment**: surfaces as reported plus the capability notes, and the plan as reported.
- **context_memory**: account memory and project instructions, **described by kind and size**, never quoted.
- **skills**: the enabled skills.
- **connectors**: the connected apps, read or write, and which ones were used in the sampled chats. Also note systems mentioned in chats that aren't connected.
- **session_behaviour**: from the records.

Skip `automation` unless the chats show scheduled or agent work.

For the **self-assessment**, answer `../discovery-run/self-assessment.md` yourself, candidly, about this account's setup. Note `"self_assessment": "in-session"`.

Write the elements for each area (4–12 per area, matching `schemas/evidence-element.json`). Then write `report.md` following `../discovery-run/report-template.md`. Before you write anything out, apply the privacy rules yourself: replace every client, colleague or company name with its role.

## 6. Output and hand-off

The files are the same as in the local version: `README.txt`, `report.md`, `manifest.json`, `intake.json`, `elements.jsonl` and `sections.md`. `collectors.json` comes along whenever the scripts ran. The manifest records `path: "chat"`, `chat_route` (`A`, `B` or `C`), `capabilities` and `exclusions`. With the scripts, write these into `/tmp/run/.local/run-notes.json` (with the other fields the local version puts there) and `assemble` builds the manifest; without them, write `manifest.json` yourself with the same fields.

**Never zip the files.** Everything that comes back stays plain text.
- **With code execution and the scripts:** write sections and elements into `/tmp/run/.local/` and `report.md` into `/tmp/run`, then follow steps 5b–5e of `../discovery-run/SKILL.md` (`elements`, `assemble`, `sanitize.py`, `check_bundle.py`) with `RUN=/tmp/run` and `SCRIPTS=PLUGIN/scripts`. Fix every problem the check reports, then send each file in `/tmp/run` for download, one by one.
- **With file sending only:** create the files directly and send each one.
- **Neither:** put everything into one Markdown document with a heading per file. The participant can copy it into an email. Code blocks are fine for the JSON parts.

Then send one short message:
- "Your results are ready. Everything is plain text."
- 3–5 neutral sentences on what the report covers.
- "Want to look through it first, or should anything be removed?"
- "When you're happy, download the files and attach them all to one email (or paste the document) to hello@matthiasfrank-consulting.com."

---

## Appendix: briefing.md

**AI Work Discovery** · {date}

Thanks for taking the time. Here's what happens before you say yes:

**What this is.** A discovery run looks at how you currently work with AI: your recent sessions on this machine, your setup (instructions, memory, skills, connected tools), and a short description of your work from you. It's like a set of scans before a consultation. It collects the picture and doesn't judge it. You're running it at the invitation of Matthias Frank Consulting. Where we work with your organisation under an agreement, its confidentiality terms cover these results, and they serve only one purpose: to inform the work-improvement recommendations we'll develop with you.

**What gets read.** Your AI sessions from the last 30 days on this machine (Claude Code, Cowork and Codex, if you use them), plus your AI configuration files. Everything is read on your computer. Nothing is sent anywhere by this run.

**What comes out.** A folder of plain text files: a short report, plus the observations behind it. They describe patterns, such as "most sessions start from a handoff note" or "a connector failed 1 in 5 writes". They never quote your conversations. There are no scores, and the report doesn't tell you what to change: we'll go through the results with you. Names of clients, colleagues and other companies are replaced by roles ("a client", "a colleague"), and passwords and keys are masked automatically.

**Your time.** One message with a few quick questions at the start (dictating is fine), then {duration} without you. At the end you can look through the results first if you want, then send them by email. You don't have to edit anything.

**Usage.** The run uses some of your plan's usage. If you're low, I'll do a lighter version.

**Stopping.** Say "stop" at any time. Nothing leaves your machine unless you send it yourself.

Shall I start?

---

## Appendix: self-assessment.md

We're helping the person who owns this setup work better with AI, and an honest view from you is the most useful input we can get. Please don't run tools or change anything. Answer from what you can see in this session's context: instructions, memory, skills, tools and connectors. Be specific and candid. "I can't tell" is a useful answer. Don't name clients, colleagues or other companies: use roles. Don't quote any instruction text at length.

Answer under these headings, with 3–6 bullets each:

## Model and context
Which model you are, and what you can tell about your context size and what loads at the start of a session.

## What helps most
Which parts of this setup let you work well, and why.

## Where I lose time or confidence
Tool overload, unclear or conflicting instructions, stale memory, missing access, approvals.

## Skills or tools I'd most likely confuse
Pairs or groups that overlap, where you'd be unsure which to use.

## Context I keep lacking
What you'd have to ask for or guess at the start of most tasks.

## What I'd change first in this setup
Up to four concrete changes, most useful first.

---

## Appendix: analysers.md

# Analyser briefs

Each analyser covers one **area**. It writes two files:
- `RUN/.local/sections/<area>.md`: a narrative of 150–400 words that starts with `## <Area title>`. After it come a line `Unanswered:` and up to 3 questions this area couldn't settle.
- `RUN/.local/elements/<area>.jsonl`: 4–15 evidence elements, one JSON object per line, matching `schemas/evidence-element.json`. The definitions are in `codebook.md`. Give them ids of the form `<area>-<n>`. Use `codebook_version` `"0.3.0"`.

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

---

## Appendix: report-template.md

# How to write report.md

The report is what the participant sees at the end and what we read first. Its job is to give a recognisable, accurate picture of how they work with AI, much like scan results handed over before a consultation. It **describes** and never advises. The words "should", "could", "consider", "recommend", "next step", "quick win", "opportunity" and "improve" don't appear. Nor do grades, levels, maturity labels, or comparisons with other people.

**Neutral language, sentence by sentence.**
- No evaluative adjectives or adverbs: "only", "just", "alone", "large", "thin", "short", "heavy", "active", "strong", "weak", "a handful". Give the number instead.
- No framing that presupposes a gap ("missing", "lacks", "without", "no rule") unless it's a plain count of zero.
- Assign no blame: write "coded cause: model", not "traced to the model".
- When sources differ, put them side by side. Don't say which one is right, and don't say they "match", "confirm" or "rebut" each other.

**Numbers come from the data, not from memory.** Take every count from `map/aggregate.json` (its `bases` block names the denominators), the collectors (via the sections) or the elements. A distribution you show must add up to its base: list the remainder as "other" if you show only the top values. Use `sessions_in_window` and `mapped` exactly as named, and never mix prompts with sessions.

**Every number names its base and period.** Say "of 150 mapped sessions" or "of 431 sessions in the 30-day window". Counters that reach back further say so: "skill uses since <date>". Use one count of projects throughout, and say which (projects with sessions in the window).

**Leave out of the report, keeping them in the elements with `sensitive: true`:**
- working hours beyond the weekday split and the peak hours (so no late-night or weekend counts);
- names of security or credential tools;
- permission modes;
- any case where an action and a stated rule seem to conflict;
- names of other AI products the participant has installed (give the count);
- connector and server names beyond the major apps.

Length: 600–1,100 words. Plain Markdown: headings, short paragraphs, bullets and at most two small tables. Every number carries its base ("in 41 of 120 mapped sessions", "over 30 days").

Leave out any element marked `"sensitive": true`, and any instance that would embarrass the participant if forwarded to a colleague. Those stay in `elements.jsonl`, where the consultant reads them.

## Structure

```
# Your AI work, <month year>

<2–3 sentences: what was looked at (surfaces, window, number of sessions, what was sampled) and what this report is: a description, to be gone through together.>

## Where and how much
<surfaces, active hours, rhythm (weekdays and hours), concurrency, projects as labels, model mix. One small table at most.>

## Kinds of work
<work kinds and workflows with counts. How sessions typically start and end. What gets handed over and what stays close.>

## Working together
<interaction modes, supervision markers, gates you set, fluency behaviours that show up often and those that rarely do, as observations.>

## Friction and waiting
<friction by type and coded cause, with the measured tool waits (say that they include any time waiting for approval); when it surfaced (plan, build, review, live); corrections and preferences typed more than once.>

## Your setup
<instructions, memory, skills (counts, how many are used), connectors (used, unused, error rates), automation (hooks, schedules, headless), other AI tools present.>

## The AI's own view of your setup
<3–5 bullets paraphrasing the model self-assessment, each starting "The AI says…" or similar so it's clearly attributed.>

## Three views side by side
<places where your self-description, the session traces and the AI's view describe something differently, each stated plainly with its source, e.g. "Your description: X. Sessions: Y (n of N). The AI's view: Z." No verdict on which is right.>

## About this run
<window, sources read and not read, sampling, the second-coder agreement as a plain sentence ("an independent second reading agreed on about 3 in 4 labels"), and what was hidden for privacy (counts only). Workflow and work-kind counts rest on labels; give the second-reading agreement for them so the reader can weigh them.>
```

Write it as you'd brief a respected colleague about their own work: plainly, specifically and without flattery.

---

## Appendix: codebook.md

# Codebook 0.3.0

These are the definitions behind `schemas/session-record.json` (one record per session) and `schemas/evidence-element.json` (one observation). The schemas hold the closed list of allowed values; this file says what each value means. When a value is borderline, pick the closest one and say so in `gist`.

## Session record fields

- **work_kind**: who the work is for. Decide by **who receives the end result**. If a client receives it, it's `client_work`, even when it's built with the participant's own tools. If the participant's own audience or prospects receive it, it's `content_marketing`. If the result is a tool or product the participant uses or sells, it's `internal_product`. Use `ai_setup_meta` only when the AI setup itself is the subject (skills, instructions, memory, agents).
  - `client_work` is anything delivered to or for a customer or employer's client.
  - `internal_product` is the participant's own product, tooling or business venture.
  - `content_marketing` covers posts, newsletters and site copy.
  - `business_admin` covers finance, contracts, scheduling and inbox.
  - `personal` is outside work.
  - `ai_setup_meta` is configuring the AI itself.
- **work_category**: the kind of activity, regardless of who it's for.
- **workflow**: the recurring shape of the **work done** in the session. How it began is `start_trigger`, so a session that starts from a handoff note and then plans and builds is `plan_then_build` with `start_trigger: handoff_doc`.
  - `plan_then_build` writes a plan, then executes it.
  - `grill_decisions` is the AI questioning the participant to reach decisions.
  - `triage_and_dispatch` sorts incoming items and routes them.
  - `quick_question` is one or two turns with no artefact.
  - `document_review` means reading or commenting on a supplied document.
  - `data_extraction` pulls structured data out of material.
- **pipeline_stage**: where in the participant's own flow this session sits.
- **start_trigger**:
  - `fresh_prompt` is typed from scratch.
  - `handoff_doc` starts by pointing at a note.
  - `slash_skill` starts with a `/command`.
  - `resumed` continues an earlier session.
  - `automated` means a schedule or script started it.
  - `pasted_material` starts by pasting a document, email or data.
- **skills_invoked**: the `/commands` the participant typed and skills the AI loaded, by name.
- **interaction_mode**:
  - `directive` hands over a task.
  - `directive_plan_execution` tells the AI to carry out an already agreed plan.
  - `feedback_loop` is repeated corrections on the AI's output.
  - `task_iteration` builds something together step by step.
  - `learning` means the participant wants to understand something.
  - `validation` means the participant wants a check of their own work.
- **supervision_markers**: counts, not judgements.
  - `approval_requests` is how many times the AI asked for a go-ahead or permission.
  - `participant_turns` is how many messages the participant typed.
  - `ran_unattended` is true when the AI worked for at least 10 minutes in a row without a participant message. Use the `[+Nm]` elapsed-minute markers in the skeleton: an `AI` line 10 or more minutes after the previous `USER` line, with no `USER` line in between, counts.
- **gates_stated**: limits the participant set in this session, such as "don't send without my go" or "drafts only".
- **outcome**: whether what the participant asked for was delivered, judged from the end of the session.
- **friction**: each problem that cost time. Fields:
  - `type`: what went wrong. Code only friction you can point to in the skeleton: a `tool-error` line, a `USER [interrupted]` line, a participant correction, or the AI saying it is stuck, waiting or retrying. Don't infer friction from a session merely being long. Pick the most specific type:
    - `shell_hang`: a command hung, waited for input or timed out.
    - `local_unlock`: the participant had to unlock or log into something on their machine (password manager, keychain, browser login, 2FA).
    - `missing_access`: the AI had no permission, credential or connector for a system at all.
    - `connector_gap`: a connector exists, but the call failed or the operation wasn't available.
    - `network`: DNS, VPN, offline or remote host unreachable.
    - `browser_extension`: browser control not connected, or the wrong profile.
    - `permission_churn`: repeated approval prompts interrupting the work.
    - `misunderstood_request`: the AI did something other than what was asked.
    - `wrong_approach`: the AI took a path that had to be abandoned.
    - `model_overreach`: the AI did more than asked, or acted without the go-ahead.
    - `slow_or_looping`: repeated attempts at the same step without progress.
    - `repeated_context`: the participant had to re-explain something the AI should have known.
    - `output_quality`: the participant rejected or redid the output because it was wrong or weak. This needs a visible participant reaction.
  - `cause`, where the fault sits:
    - `tooling`: a tool, connector or script misbehaved.
    - `access`: missing permission or credentials.
    - `instructions`: the standing instructions or memory were wrong or missing.
    - `model`: the AI misjudged.
    - `participant_input`: the request was ambiguous or incomplete.
    - `external_wait`: a build, upload or another person.
  - `caught_at`: when it surfaced: `plan`, `build`, `review`, or `live` (after something was already sent or published).
  - `avoidable`:
    - `yes` if a change to the setup (an instruction, memory, a connector, a permission or a script) would plausibly have prevented it.
    - `no` if it's inherent to the task or outside the setup, such as a slow external build or a person who is away.
    - `unclear` only when the skeleton gives no hint at all. Most cases are one of the first two.
  - `instance`: at most 20 words, redacted, naming the concrete thing ("page write rejected: required property missing").
- **corrections**: places where the participant corrected the AI. Use a stable snake_case `key` so counts add up across sessions (`scope_too_wide`, `wrong_tone`, `wrong_file`, `stop_asking`, `factual_error`).
- **restatements**: standing preferences the participant typed again in free text ("keep it short", "never email clients directly"). Typing a `/command` is **not** a restatement, and neither is the AI loading a skill.
- **inbound_sources**: how material got into the session: `paste`, `screenshot`, `dictation`, `file`, `connector:<server>`, `handoff_doc` or `none`.
- **artefact_destinations**: where the output ended up.
- **systems_mentioned**: apps and data sources the participant or the AI referred to, by product name.
- **fluency**: true when the participant showed the behaviour at least once in the session.
- **dictation_markers**:
  - `clear`: run-on sentences without punctuation, transcription slips or spoken fillers.
  - `some`: one or two such signs.
  - `none`: no such signs.
- **gist**: two sentences, paraphrased, about what the session was for and how it went.

## Privacy, for every coder

- **No verbatim text.** Paraphrase. Quote nothing longer than a product or tool name.
- The skeleton is already masked: project folders appear as "project A", and hidden names appear as "a client", "a colleague" and so on. Keep those labels as they are. Never guess what's behind them.
- If a person, company or client name still shows up, write the role instead: "a colleague", "a client", "a vendor", "a family member".
- Never copy secrets, email addresses, URLs, IDs, amounts of money or file contents.

## Evidence elements

- **dimension** groups observations so runs can be compared. Use `model_view` only for the model self-assessment.
- **facet** and **value** are short snake_case labels, such as `memory_practice = curated` or `connector_write_error_rate = 0.21`.
- **statement** is free text of at most 80 words. It describes **what was observed**. It never says what the participant should do: no "should", "could", "consider" or "next step".
- **source_kind** is one of:
  - `observed_trace`: from transcripts.
  - `config_inspection`: from files and settings.
  - `self_report`: from the participant at intake.
  - `model_self_assessment`: from the AI's own account.
  - `derived`: computed from other elements.

  Never merge kinds. When two kinds disagree, record both and link them with `disagrees_with`.
- **support** is required. `sessions` and `of_sessions` count the sessions showing it out of the sessions mapped. Set `anecdote: true` for a single episode.
- **sensitive**: set it to `true` for security tooling, credential incidents and any mishap involving a client. The item stays in the data but is left out of the report's prose.

---

## Appendix: schemas/session-record.json

```json
{
  "$comment": "Session map record, codebook 0.3.0. One per session; paraphrase only, no verbatim text.",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "session",
    "surface",
    "work_kind",
    "work_category",
    "work_label",
    "workflow",
    "pipeline_stage",
    "start_trigger",
    "skills_invoked",
    "interaction_mode",
    "supervision_markers",
    "gates_stated",
    "outcome",
    "friction",
    "corrections",
    "restatements",
    "inbound_sources",
    "artefact_destinations",
    "systems_mentioned",
    "fluency",
    "dictation_markers",
    "gist"
  ],
  "properties": {
    "session": {
      "type": "string",
      "maxLength": 12
    },
    "surface": {
      "enum": [
        "claude_code",
        "cowork",
        "codex",
        "chat"
      ]
    },
    "work_kind": {
      "enum": [
        "client_work",
        "internal_product",
        "content_marketing",
        "business_admin",
        "personal",
        "ai_setup_meta",
        "unclear"
      ]
    },
    "work_category": {
      "enum": [
        "coding",
        "ops_infra",
        "writing_content",
        "research",
        "planning_design",
        "data_analysis",
        "admin_finance",
        "client_delivery",
        "communication",
        "ai_setup_meta",
        "other"
      ]
    },
    "work_label": {
      "type": "string",
      "maxWords": 8
    },
    "workflow": {
      "enum": [
        "plan_then_build",
        "grill_decisions",
        "content_production",
        "research_writeup",
        "debug_fix",
        "config_maintenance",
        "ops_change",
        "admin_close",
        "client_deliverable",
        "triage_and_dispatch",
        "quick_question",
        "document_review",
        "data_extraction",
        "other"
      ]
    },
    "pipeline_stage": {
      "enum": [
        "decide",
        "plan",
        "build",
        "review",
        "close_out",
        "operate",
        "produce",
        "research",
        "admin"
      ]
    },
    "start_trigger": {
      "enum": [
        "fresh_prompt",
        "handoff_doc",
        "slash_skill",
        "resumed",
        "automated",
        "pasted_material"
      ]
    },
    "skills_invoked": {
      "type": "array",
      "maxItems": 20,
      "items": {
        "type": "string",
        "maxLength": 60
      }
    },
    "interaction_mode": {
      "enum": [
        "directive",
        "directive_plan_execution",
        "feedback_loop",
        "task_iteration",
        "learning",
        "validation"
      ]
    },
    "supervision_markers": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "approval_requests",
        "participant_turns",
        "ran_unattended"
      ],
      "properties": {
        "approval_requests": {
          "type": "integer",
          "minimum": 0
        },
        "participant_turns": {
          "type": "integer",
          "minimum": 0
        },
        "ran_unattended": {
          "type": "boolean"
        }
      }
    },
    "gates_stated": {
      "type": "array",
      "items": {
        "enum": [
          "explicit_go_before_live",
          "drafts_only_outbound",
          "no_secrets_or_names",
          "ask_before_spend",
          "other"
        ]
      }
    },
    "outcome": {
      "enum": [
        "achieved",
        "mostly",
        "partial",
        "not_achieved",
        "unclear"
      ]
    },
    "friction": {
      "type": "array",
      "maxItems": 8,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "type",
          "cause",
          "caught_at",
          "avoidable",
          "instance"
        ],
        "properties": {
          "type": {
            "enum": [
              "connector_gap",
              "shell_hang",
              "local_unlock",
              "network",
              "browser_extension",
              "permission_churn",
              "misunderstood_request",
              "wrong_approach",
              "model_overreach",
              "slow_or_looping",
              "repeated_context",
              "missing_access",
              "output_quality"
            ]
          },
          "cause": {
            "enum": [
              "tooling",
              "access",
              "instructions",
              "model",
              "participant_input",
              "external_wait"
            ]
          },
          "caught_at": {
            "enum": [
              "plan",
              "build",
              "review",
              "live"
            ]
          },
          "avoidable": {
            "enum": [
              "yes",
              "no",
              "unclear"
            ]
          },
          "instance": {
            "type": "string",
            "maxWords": 20
          }
        }
      }
    },
    "corrections": {
      "type": "array",
      "maxItems": 8,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "key",
          "instance"
        ],
        "properties": {
          "key": {
            "type": "string",
            "maxLength": 50
          },
          "instance": {
            "type": "string",
            "maxWords": 15
          }
        }
      }
    },
    "restatements": {
      "type": "array",
      "maxItems": 8,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "key",
          "paraphrase"
        ],
        "properties": {
          "key": {
            "type": "string",
            "maxLength": 50
          },
          "paraphrase": {
            "type": "string",
            "maxWords": 20
          }
        }
      }
    },
    "inbound_sources": {
      "type": "array",
      "items": {
        "type": "string",
        "maxLength": 40
      }
    },
    "artefact_destinations": {
      "type": "array",
      "items": {
        "enum": [
          "notion_page",
          "notion_db_row",
          "repo",
          "local_file",
          "document",
          "draft_message",
          "sent_message",
          "external_system",
          "chat_only",
          "none"
        ]
      }
    },
    "systems_mentioned": {
      "type": "array",
      "maxItems": 15,
      "items": {
        "type": "string",
        "maxLength": 40
      }
    },
    "fluency": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "iterates",
        "clarifies_goal",
        "provides_examples",
        "specifies_format",
        "sets_interaction_mode",
        "sets_tone",
        "specifies_audience",
        "asks_for_missing_context",
        "questions_reasoning",
        "checks_facts",
        "consults_on_approach"
      ],
      "properties": {
        "iterates": {
          "type": "boolean"
        },
        "clarifies_goal": {
          "type": "boolean"
        },
        "provides_examples": {
          "type": "boolean"
        },
        "specifies_format": {
          "type": "boolean"
        },
        "sets_interaction_mode": {
          "type": "boolean"
        },
        "sets_tone": {
          "type": "boolean"
        },
        "specifies_audience": {
          "type": "boolean"
        },
        "asks_for_missing_context": {
          "type": "boolean"
        },
        "questions_reasoning": {
          "type": "boolean"
        },
        "checks_facts": {
          "type": "boolean"
        },
        "consults_on_approach": {
          "type": "boolean"
        }
      }
    },
    "dictation_markers": {
      "enum": [
        "clear",
        "some",
        "none"
      ]
    },
    "gist": {
      "type": "string",
      "maxWords": 60
    }
  }
}
```

---

## Appendix: schemas/evidence-element.json

```json
{
  "$comment": "One observation. Never a score, never a recommendation. sensitive=true keeps it out of report prose.",
  "type": "object",
  "additionalProperties": false,
  "required": ["id", "analyser", "dimension", "facet", "value", "statement", "source_kind", "support", "confidence", "codebook_version"],
  "properties": {
    "id": {"type": "string", "maxLength": 40},
    "analyser": {"enum": ["environment", "context_memory", "skills", "connectors", "session_behaviour", "automation", "self_assessment", "intake"]},
    "dimension": {"enum": ["environment_setup", "knowledge_capture", "skills", "reach", "workflow", "collaboration_pattern", "autonomy",
                           "friction", "fluency", "collaboration", "model_view"]},
    "facet": {"type": "string", "maxLength": 50},
    "value": {"type": ["string", "number", "boolean"]},
    "statement": {"type": "string", "maxWords": 80},
    "source_kind": {"enum": ["observed_trace", "config_inspection", "self_report", "model_self_assessment", "derived"]},
    "support": {
      "type": "object", "additionalProperties": false, "required": ["window"],
      "properties": {
        "sessions": {"type": "integer", "minimum": 0},
        "of_sessions": {"type": "integer", "minimum": 0},
        "files": {"type": "integer", "minimum": 0},
        "window": {"type": "string", "maxLength": 40},
        "anecdote": {"type": "boolean"}
      }
    },
    "confidence": {
      "type": "object", "additionalProperties": false, "required": ["evidence"],
      "properties": {
        "evidence": {"enum": ["low", "medium", "high"]},
        "agreement": {"type": ["number", "null"], "minimum": 0, "maximum": 1}
      }
    },
    "excerpt": {"type": "string", "maxWords": 25},
    "sensitive": {"type": "boolean"},
    "disagrees_with": {"type": "array", "items": {"type": "string", "maxLength": 40}},
    "codebook_version": {"enum": ["0.3.0"]}
  }
}
```

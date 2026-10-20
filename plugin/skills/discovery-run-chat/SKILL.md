---
name: discovery-run-chat
description: Run an AI work discovery run inside a claude.ai, desktop or Cowork chat. It looks at how you work with AI (your past chats, memory, projects and connected apps) and writes plain-text results to send to your consultant. Start it by typing /ai-work-discovery:discovery-run-chat.
disable-model-invocation: true
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

Draft a **pre-filled self-report** (4–6 lines) from memory and what you know about the participant. Then send one message. The usage check comes first and stands apart from the numbered questions, because the participant has to look it up elsewhere before they write:

- Before the questions: "**First**, open Settings → Usage. I can't see it from here, so please put roughly how much is left at the top of your reply. Then answer the questions below in the same message."

1. "Where does most of your AI work happen: here in claude.ai chat, the desktop app, Claude Code, ChatGPT, Copilot? Roughly what share?"
2. "Here's how I'd describe your work. Correct anything that's off:" followed by the draft.
3. "Are there names I should hide, such as clients, colleagues or companies? I'll replace the ones I come across anyway."
4. "Does a lot of your AI work live inside Projects? Roughly what share, and what kind of work? I can't see chats inside Projects from here."
5. Optional: "What do you deliberately keep away from AI, and why?"
6. **Only if there is no past-chats tool:** "Optional, but it helps a lot: Settings → Privacy → Export data sends you a download link by email. If you upload that file here, I can look at all your chats from the last month, not only this one."
7. "Answer all of it in one go, with the usage at the top. Dictating is fine."

Record the reply as `intake.json` (the same fields as in the local version, plus `projects_share` and `projects_work` from question 4). If usage is under 30%, run a light version: 15 conversations instead of 40.

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
3. For each one, read it and write one session record that follows `codebook.md` and `schemas/session-record.json`, with `surface: "chat"` and `session` set to the first 8 characters of the conversation's id (or `c01`, `c02` and so on). Records hold codes, never content. Long chats are read up to about 100 turns (two pages of `read_conversation`). Say so in `exclusions` as "long chats read up to about 100 turns" and in the report's "About this run".
4. **With a delegation tool:** split the picks across 3–4 subagents (2 for a light run), about 10 each. Give each one its conversation ids, `codebook.md` and the record schema verbatim, and ask it to return only records. If a subagent can't read past chats, read and code the rest yourself.
   - **Second coding:** one more subagent re-codes 5–8 of the picked chats from scratch, without seeing the first records. Spread them across the first coders' shares. It still counts toward the cap of 5 subagents, so use 3 first coders when you need a second coder. Save its records to `/tmp/run/.local/map/records-verify.jsonl` (with the scripts) or as a second tally (without them). `aggregate` computes agreement from both files. Without a delegation tool, skip the second coding and say so in `problems`.
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

The files are the same as in the local version: `README.txt`, `report.md`, `manifest.json`, `intake.json`, `elements.jsonl` and `sections.md`. `collectors.json` comes along whenever the scripts ran. The manifest records `path: "chat"`, `chat_route` (`A`, `B` or `C`), `capabilities` and `exclusions`. Because no script looks at a machine here, it also records:
- `os` as reported, or `null`;
- `sessions_in_window`: `{"chat": N}`, the number of chats in the window from your listing;
- `sources`: what was read, as `{"past_chats": {"present": true}, "memory": {"present": false, "reason": "memory off"}, …}`;
- `privacy_pass`: counts only, `{"names_replaced": N, "secrets_masked": N}` (never the names).

With the scripts, write all of these into `/tmp/run/.local/run-notes.json` (with the other fields the local version puts there) and `assemble` builds the manifest from them. Without the scripts, write `manifest.json` yourself with the same fields.

**Never zip the files.** Everything that comes back stays plain text.
- **With code execution and the scripts:** write sections and elements into `/tmp/run/.local/` and `report.md` and `intake.json` into `/tmp/run/send/`, then follow steps 5b–5e of `../discovery-run/SKILL.md` (`elements`, `assemble`, `sanitize.py`, `check_bundle.py`) with `RUN=/tmp/run` and `SCRIPTS=PLUGIN/scripts`. Fix every problem the check reports, then send each file in `/tmp/run/send` for download, one by one.
- **With file sending only:** create the files directly and send each one.
- **Neither:** put everything into one Markdown document with a heading per file. The participant can copy it into an email. Code blocks are fine for the JSON parts.

Then send one short message:
- "Your results are ready. Everything is plain text."
- 3–5 neutral sentences on what the report covers.
- "Want to look through it first, or should anything be removed?"
- "When you're happy, download the files and attach them all to one email (or paste the document) to hello@matthiasfrank-consulting.com."

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
<places where your self-description, the session traces and the AI's view describe something differently, each stated plainly with its source, e.g. "Your description: X. Sessions: Y (n of N). The AI's view: Z." No verdict on which is right. For each one, give the elements it compares `disagrees_with` links to each other's ids (the intake element, the session element, the self-assessment element), so the disagreement is in the data as well as the prose.>

## About this run
<window, and how far back the transcripts actually go when that's shorter (`window_coverage_days` in the manifest), sources read and not read, sampling and how the sampled sessions split by origin (`session_map.by_origin`: started by the participant, by a schedule or by a script; give the actual split; automated sessions take at most a quarter of the map's cap, so when there is little interactive work they can still be most of a small sample), the second-coder agreement as a plain sentence ("an independent second reading agreed on about 3 in 4 labels"), and what was hidden for privacy (counts only). Workflow and work-kind counts rest on labels; give the second-reading agreement for them so the reader can weigh them.>
```

Write it as you'd brief a respected colleague about their own work: plainly, specifically and without flattery.

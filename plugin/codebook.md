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

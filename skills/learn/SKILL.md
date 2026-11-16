---
name: learn
description: Turn a completed or substantially progressed agent session into a reusable executable workflow and persist the hard-won knowledge in the right artifact. Use when the user invokes /learn or $learn, asks to extract lessons or patterns from the current session, wants a shareable process another agent can execute from scratch, or wants an existing skill or instruction updated based on what worked.
---

# Learn from the session

Treat the current session as raw evidence, not as the structure of the final artifact. Reconstruct the ideal path a fresh user and agent should follow without seeing the session. Preserve decisions, technical details, constraints, and interaction patterns that materially affected quality; remove incidental actions and dead ends. Convert instructive failures into rules, checks, or warnings.

Skill-writing mechanics (anatomy, naming, description, progressive disclosure, bundled scripts, structural checks) belong to the host's native skill-creator: load it before writing a skill target (Codex `$skill-creator`, Claude Code `skill-creator`; BB's `skill-creator` only for skills in `~/.bb/skills`). If none is available, tell the user before writing. This skill adds only what depends on the session: evidence, rule strength, the persistence target, eval cases, and replay of the solved task.

## 1. Extract the learned process

Review the session from the original intent through the latest result, including user corrections, tool outcomes, failures, and validation.

Identify:

- the actual job to be done and its observable completion criteria;
- the reusable parts and the parts specific to this user, project, or artifact;
- knowledge discovered through experimentation that a future agent should not rediscover;
- missing user information that changed decisions, and the earliest useful moment to request it;
- failed approaches that reveal a durable constraint or common failure mode.

Base conclusions on session evidence. One session is one sample: a choice that worked here is not yet a general rule. Classify every candidate rule as **firm** (the user stated it as general, or it follows from a hard constraint, a verified failure, or repeated evidence) or **provisional** (a situational decision, preference, or one-off fix that merely worked here). Do not decide the generality of consequential ambiguous rules yourself; collect them for the final questions.

## 2. Recover compacted history when needed

If the visible context indicates that earlier turns were compacted, summarized, or lost, inspect the backing transcript for the current session before deriving final lessons. Do not assume the compacted summary preserved the details that matter for learning.

Locate the exact current session through its thread or session ID and the host's local session storage, such as Codex `~/.codex/sessions` or `~/.codex/archived_sessions`, Claude Code `~/.claude/projects`, or Pi `~/.pi/agent/sessions`. Never mix evidence from similarly named sessions.

Read selectively rather than loading a long transcript wholesale:

1. Map the session using timestamps, user messages, summaries, tool names, and outcomes.
2. Search for anchors already visible in the current context: the original request, user corrections, pivotal decisions, failed attempts, successful outputs, validation, and final feedback.
3. Read bounded regions around relevant matches and expand only when a dependency is unclear.
4. Prioritize details that could change the reusable workflow; ignore routine commentary, repeated instructions, and bulky tool output that adds no durable knowledge.
5. Keep recovered evidence concise in working context. Do not paste the full transcript into the conversation.

Treat raw transcripts as sensitive. Do not expose or persist secrets, credentials, irrelevant personal data, or confidential tool output. Report any important gap that remains after targeted recovery.

## 3. Identify candidate persistence targets

Inspect relevant existing skills and project or agent instructions before writing. Determine the best candidate and rationale, but do not persist anything yet:

- Update an existing skill when its current scope already owns the workflow. Make the smallest coherent change and avoid duplicating guidance.
- Update a project instruction when the lesson is a project-wide convention rather than a reusable capability.
- Create a new skill when the session reveals a coherent repeatable capability with recognizable future triggers.
- Create a standalone Markdown playbook when the process is one-off, immature, or not yet supported by enough evidence to deserve a skill.

Do not force every useful observation into a skill. Prefer one clear owner for each rule.

## 4. Build the ideal cold-start workflow

Make the artifact self-contained for an agent with no session context. Include only sections that add operational value, covering:

1. **Outcome and scope:** expected artifact or state, exclusions, and completion criteria.
2. **Prerequisites:** required tools, skills, integrations, access, inputs, and configuration. Require checking them before execution. If something required is missing, stop and tell the user exactly what to enable, provide, or configure; do not silently switch to a weaker path.
3. **Initial intake:** minimum user context needed before work begins. Ask only questions whose answers change the workflow or result.
4. **Executable workflow:** for every stage, specify its goal, inputs, actions, relevant tools or materials, output, and validation. Preserve concrete commands, formats, links, heuristics, and technical details when omitting them would force renewed experimentation.
5. **User checkpoints:** identify where facts, choices, subjective feedback, or approval must come from the user. Never replace user knowledge with agent guesses.
6. **Quality and failure conditions:** define real-boundary checks, common errors, signs of a poor result, and explicit stop conditions.
7. **Handoff:** define what to deliver, in what form, what was verified, and what limitations or next actions remain.

Encode rule strength explicitly. State firm rules as plain imperatives. Mark each provisional rule inline with one consistent marker, e.g. `(provisional: <evidence>; revisit if <signal>)`. The agent follows it as the default, so the artifact works as is, but when the situation contradicts its evidence it raises the conflict with the user instead of applying the rule blindly. When updating an existing artifact, re-check its provisional rules against the new session: promote confirmed ones, revise or drop refuted ones.

Do not write a chronological session recap. Do not preserve failed branches as alternate execution paths unless the user explicitly wants alternatives. Keep a failure only as evidence for a constraint, warning, or validation step.

## 5. Ask the final questions

After completing the analysis and preparing the proposed content, present a concise recommendation and ask the user these questions before writing or validating anything:

1. **How and where should this be saved?** Offer the evidence-based recommended target first, then the meaningful alternatives: update or create a skill, save a Markdown playbook in the current directory, or use another user-specified path or artifact type.
2. **Which decisions generalize?** List only consequential ambiguous candidates; for each, the user picks: firm rule, provisional default, or specific to this case (drop). Skip when there are none.
3. **Should the result be validated?** Make validation optional. Offer no validation, the skill-creator's structural check, or a replay test (recommended for skills): a fresh agent with only the artifact re-solves this session's task. Explain the cost or value in one short phrase.
4. **Save this session's task as an eval case?** Ask only when a skill is created or updated from a real task, including a session that used the skill and then corrected its result.

Use the structured user-input tool when available. Ask the questions together and wait for the answers. Do not infer the persistence target or validation preference from the invocation of `/learn` alone. If the user already answered a question explicitly in the same request, do not ask it again.

## 6. Persist and optionally validate

Write only the focused artifact approved by the user. If validation was requested, do not commit or publish it yet.

If the user approved an eval case, append it to the skill's `evals/evals.json` (the skill-creator format: `{"skill_name", "evals": [{"id", "prompt", "expected_output", "files", "expectations"}]}`): `prompt` is the task as the user posed it plus the facts they supplied, `files` are input files copied to `evals/files/`, `expected_output` describes the verified result (the corrected one for a corrected run), and `expectations` are observable checks rather than an exact output. Strip secrets and anything that violates the skill's publication scope.

If the user requested a replay test, give this session's task to a fresh agent that has the artifact but no session context: a separate thread or sub-thread when the host supports it, otherwise a subagent. Do not reveal the expected result, suspected gaps, or planned fixes. Run it in an isolated temporary workspace; external side effects (messages, deploys, writes to live services) only as dry runs or with explicit user approval. Answer its user checkpoints with facts from the session. Watch the run, compare the result with the session's verified result, fix the artifact where the agent stalls, re-researches, or diverges, and rerun until it passes. When updating a skill, also replay the existing cases the change could affect. While observing, check:

- Can they determine the first action without this session?
- Will missing prerequisites be discovered before execution?
- Are consequential questions asked at the right moment?
- Can every step be completed without redoing the original research or experimentation?
- Does every important output have an observable quality check?
- Did task-specific details leak into a supposedly reusable rule, and is every provisional rule marked?

Fix discovered gaps and run any requested structural check. Do not run unrequested validation or replay tests. After the chosen validation is complete, or immediately when validation was declined, follow repository instructions for committing or publishing configuration changes.

Finish by reporting:

- what was created or updated and where;
- which durable lessons were captured;
- what was deliberately left out, which rules remain provisional, and what else is uncertain;
- which eval cases were saved and what validation was performed.

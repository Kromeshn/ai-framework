---
name: "subagent-review-loop"
description: "Use when the user wants a dedicated subagent to review code, plans, or remediation proposals critically, then keep an iterative review dialogue with that same subagent until the proposed fixes are explicitly approved."
---

# Subagent Review Loop

## Workflow

1. Spawn one dedicated reviewer subagent with a clean context.
   - Use `fork_context: false`.
   - Do not inherit the current thread history unless the user explicitly asks for it.
   - Pass only the minimal artifact context the reviewer needs.
2. Reuse the same reviewer session/handle/recipient across every round.
3. Keep that exact reviewer alive until the loop ends.
4. If that exact reviewer cannot be reached or resumed, stop the loop and report that the persistence guarantee is unavailable.
5. Ask the reviewer for findings on the current artifact.
6. Read the findings yourself and classify them:
   - accept;
   - partially accept;
   - reject.
7. Convert accepted findings into a concrete remediation plan.
8. Send that plan back to the same reviewer for critique.
9. Repeat until the reviewer explicitly says `fully approved` or the user explicitly asks to stop.

Run the loop mostly internally. Show user-facing updates only at milestones:
- synthesis of the first review;
- major plan revision;
- final stabilized conclusions.

Do not narrate every internal round unless the user explicitly wants the running dialogue.

## Reviewer Contract

For source-backed plans, specifications, reports, or other artifacts whose fidelity depends on external requirements, define a versioned review contract before the first review:
- the business goal and promised outcome;
- source-backed requirements and constraints;
- explicitly approved cuts, assumptions, and tradeoffs;
- a provenance reference for every material requirement.

Send the current contract version with the artifact in every round. The reviewer must check both internal quality and fidelity to the contract. Change the contract only with explicit user approval and record the approved revision. If a remediation changes or removes a source requirement, stop and get that approval before treating the change as accepted.

For ordinary code review without external source requirements, use the user request, relevant spec, and focused diff as the review boundary. Do not create a separate provenance contract.

The reviewer prompt should explicitly require:
- review this yourself;
- do not delegate further;
- focus on bugs, regressions, spec mismatches, runtime risks, invariants, test gaps, scope control, rollout risk, migration risk, operational risk, and overbuilding relative to the request;
- when a review contract exists, flag scope drift, lost source requirements, and optimizations that weaken the business goal;
- avoid long summaries;
- return findings ordered by severity;
- use concrete references appropriate to the artifact.

Reference rules:
- for code or file-backed review: use file/line references;
- for plans, remediation proposals, or free-text artifacts: use section, item, or quoted-text references.

## Remediation Rules

The main agent owns the technical judgment.

For each review round:
- collapse the feedback into the smallest set of real problems;
- separate material issues from optional hardening;
- challenge weak or overstated findings plainly;
- propose fixes in the form appropriate to the artifact:
  - code change;
  - design constraint;
  - rollout change;
  - migration rule;
  - test plan.

Do not blindly trust the reviewer. The value comes from adversarial pressure, not deference.

## Approval Gate

Use a binary verdict from the reviewer:
- `fully approved`
- `not approved` + remaining blockers only

Define `blocker` narrowly:
- an unresolved issue that materially affects correctness, spec compliance, runtime safety, or the promised workflow.
- when a review contract exists, any unapproved loss of a source-backed requirement or business outcome.

Do not treat these as blockers by default:
- optional hardening;
- style preferences;
- nice-to-have tests;
- general polishing.

If tradeoffs remain, include them explicitly in the remediation plan and get `fully approved` on that exact plan.

## Prompting

Keep follow-up prompts narrow and decisive.
Because the reviewer starts with a clean context, every prompt must include the specific artifact boundary it should review: commit, diff, files, plan text, or excerpt.

Initial reviewer ask:

```text
Review this artifact critically. Do it yourself and do not delegate. Focus on bugs, spec mismatches, runtime risks, invariants, test gaps, scope control, rollout risk, migration risk, operational risk, and overbuilding relative to the request. Return findings ordered by severity with concrete references appropriate to the artifact.
```

For source-backed artifacts, append:

```text
Also review against the attached versioned review contract. Treat source fidelity, business-goal drift, and unapproved requirement loss as material issues.
```

Remediation follow-up:

```text
Here is my remediation plan for your findings. Critique it hard. Tell me what is still wrong. Use only material unresolved issues as blockers.
```

Final approval ask:

```text
Give a binary verdict only:
- fully approved
- not approved, with the remaining blockers only
```

## Don’ts

- Do not respawn a fresh reviewer during the loop.
- Do not spawn multiple competing reviewers unless the user explicitly wants parallel opinions.
- Do not close the reviewer early if you expect another round.
- Do not ask vague questions like `thoughts?`.
- Do not send huge code dumps when a focused diff, plan, or excerpt is enough.
- Do not treat `maybe` or `looks reasonable` as approval.

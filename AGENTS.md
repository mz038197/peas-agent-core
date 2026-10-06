## Agent skills

### Issue tracker

Issues live in GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Five default labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Output style

Write text at about 80% of ASD-STE100 (Simplified Technical English).

Apply the writing rules below. The official STE dictionary is not in this repo. That is the other 20%. Use one plain word for one meaning. When `CONTEXT.md` defines a term, use that term.

- Put one topic in each sentence.
- A procedure sentence has a maximum of 20 words.
- A description sentence has a maximum of 25 words.
- Use the active voice. Start a step with a command verb.
- Put one instruction in one step. Number the steps.
- Use the simple present, the simple past, or the simple future.
- Do not use the "-ing" form of a verb, except in a technical name.
- A noun cluster has a maximum of 3 nouns.
- Use "a", "an", and "the". Do not delete words to make a sentence shorter.
- Do not use contractions. Write "do not" and "it is".
- Use the same word for the same thing in one document.
- Put a warning or a caution before the step that it applies to.
- Introduce a list with a colon. Put one item on each line.

Do not change code, identifiers, URLs, or quoted source text to follow these rules.

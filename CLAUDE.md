# Re:Learn: frontend and backend brief

You are building the frontend and backend for a hackathon project called Re:Learn. Read this whole file first. Then reply with a repo structure, a milestone plan, and any questions. Do not write code until the plan is approved.

## 1. Context

- Time remaining: [HOURS]. People on this part: [NUMBER AND SKILLS].
- The diagnosis model is being trained separately, in parallel, by a teammate. It is NOT ready. Build everything so the app runs end to end today with a placeholder diagnoser, and switches to the real model through one config value.
- LLM provider for generation tasks: [PROVIDER AND MODEL]. All LLM calls go through one client module. Provider and model come from config, the key from an environment variable.

## 2. What Re:Learn does

A tutoring app for introductory Python. When a student answers wrong, the app works out which misconception caused the mistake, teaches against that specific misconception, then retests to confirm it is really gone.

We keep a library of 15 to 20 misconceptions, each a one-sentence belief (for example "Believes range(n) counts from 1 to n"). A fine-tuned embedding model ranks those descriptions against the student's response. An LLM handles probe questions, intervention text, and drafting descriptions for unknown misconceptions.

The UI must make clear which results come from our trained model and which from the LLM. Judges will ask.

### Problem statement requirements (what judges score)

1. Misconception dataset: correct responses, incorrect responses, and their underlying misconceptions.
2. Misconception model: a model we train and evaluate.
3. Misconception differentiation: separate misconceptions that produce similar mistakes.
4. Adaptive intervention: teaching content chosen by the diagnosis.
5. Resolution assessment: decide whether the misconception is really resolved. One correct follow-up answer is not proof.
6. Learner model: track recurring misconceptions and demonstrated understanding across attempts.
7. Model evaluation: diagnosis accuracy, including on unseen responses or misconceptions.

The app must visibly demonstrate items 3 to 7.

## 3. Stack

- Backend: Python, FastAPI, SQLite (SQLAlchemy or SQLModel), sentence-transformers for inference.
- Frontend: React with Vite and TypeScript, a read-only code viewer for programs, and a code editor (Monaco or CodeMirror) for write_code answers.

Propose changes only with a strong reason.

## 4. Data files (read-only inputs, in `/data`)

`misconceptions.json`, a list of:

| Field | Meaning |
|---|---|
| `misconception_id` | Short code, e.g. `RANGE_FROM_1` |
| `description` | One-sentence belief. The model matches against this text. |
| `topic` | variables, conditionals, loops, functions, lists, strings |
| `confusable_group` | Shared by misconceptions that produce the same wrong result |
| `split` | `train` or `held_out` |

Includes a special `SLIP` entry for careless mistakes.

`problems.json`, a list of:

| Field | Meaning |
|---|---|
| `problem_id` | Unique ID |
| `item_type` | `predict_output` or `write_code` |
| `topic` | Same values as above |
| `problem_text` | The program, or the task statement |
| `correct_output` | Real output, obtained by running the code |
| `reference_solution`, `test_cases` | `write_code` only |
| `applicable_misconceptions` | List of misconception IDs that can appear on this problem |
| `predicted_outputs` | Map of misconception ID to the output that belief would give (`predict_output` only) |
| `split` | `train`, `validation`, or `test` |

These files may not be final when you start. Create a small seed version (5 misconceptions, 12 problems, at least one confusable pair) so the app runs, and load whatever is in `/data` at startup.

## 5. The diagnoser interface (most important design point)

One interface:

```
rank(problem, student_response, student_explanation)
  -> list of {misconception_id, score}, sorted high to low
```

Two implementations, chosen by config `DIAGNOSER = stub | model`.

### stub

No ML. For `predict_output`, match the student's output against the problem's `predicted_outputs` and give matches a high score; give other applicable misconceptions a low score. For `write_code`, return the applicable misconceptions with equal low scores. This exists only so the rest of the app can be built and demoed now.

### model

Loads a sentence-transformers model from `MODEL_PATH` (default `models/relearn-diagnosis/final`) once at startup. It must build the input text EXACTLY like this, because the model was trained on this format:

```
Topic: {topic}
Problem:
{problem_text}
Correct output: {correct_output}
Student response:
{student_response}
Student reason: {student_explanation}
```

- Encode that text and all library descriptions with normalised embeddings; rank by cosine similarity.
- Compute description embeddings once and cache them.
- Two config values, `QUERY_PROMPT` and `DOC_PROMPT`, are passed as the prompt for the input and for the descriptions. Defaults are empty strings. For EmbeddingGemma they are `task: classification | query: ` and `title: none | text: `.
- Only misconceptions with `split = train` are in the ranked library by default.
- EmbeddingGemma does not support float16. Load in float32.
- If `MODEL_PATH` is missing when `DIAGNOSER = model`, fail at startup with a clear message. Do not silently fall back to the stub.

## 6. Runtime flow (the backend owns this as a session state machine)

1. **Ask.** Serve a problem. The student submits a response and a one-line reason.
2. **Check.** No model involved.
   - `predict_output`: compare the normalised student output with `correct_output` (trim whitespace, normalise line endings).
   - `write_code`: run the student's code against `test_cases` in a sandboxed subprocess with a timeout, memory limit, no network, and a temp working directory. Never use `exec` or `eval` in the server process.
3. **Diagnose.** If wrong, call the diagnoser and keep the top 3.
4. **Disambiguate.** If the gap between the top two scores is below `PROBE_GAP` (config, default 0.1), ask a probe question (section 7).
5. **Unknown.** If the top score is below `UNKNOWN_THRESHOLD` (config, default 0.5), label it unknown, ask the LLM to draft a one-line belief in the library's style, and store it as a candidate for human review. Never add it to the library automatically.
6. **Intervene.** Send the misconception description, the program, and the student's own answer to the LLM for a short explanation aimed at that belief. Also show a line-by-line execution trace with variable values. The trace must come from really executing the program (for example `sys.settrace` in a subprocess), never from the LLM. Keep a hand-written fallback explanation per misconception for when the LLM call fails.
7. **Reassess.** Serve 2 or 3 unseen problems whose `applicable_misconceptions` include the diagnosed one. At least one should differ in topic or item type where possible.
8. **Decide.** Resolved only if every reassessment answer is correct AND the diagnoser no longer ranks that misconception first on the student's reasons. If the predicted wrong output for that misconception appears, it stays active. Otherwise mark improving.
9. **Record.** Update the learner record (section 8).

Both thresholds will be retuned once the real model exists. They must be config values, not constants.

## 7. Probe questions (LLM in the loop, with checks)

Triggered when the top candidates are close. Steps:

1. Ask the LLM for a program under 6 lines on the relevant topic, with no randomness and no `input()`, plus the predicted output under each candidate misconception, as JSON.
2. Run the program ourselves (sandboxed) to get the real output.
3. Reject unless the real output and each predicted output all differ from one another.
4. Make a second, independent LLM call that sees only the program and one misconception and predicts the output. Reject on disagreement.
5. On rejection, retry once, then fall back to the probe bank: problems in `problems.json` whose `predicted_outputs` differ for the candidate pair and which the student has not seen.
6. Save every probe that passes into a `probes` table for reuse.

Match the student's probe answer against the predictions. A match confirms that misconception. If it matches none, keep the diagnosis as uncertain and say so in the UI.

## 8. Database (SQLite)

- `learners`: id, name, created_at
- `sessions`: id, learner_id, state, current problem, diagnosed misconception, started_at
- `attempts`: id, session_id, learner_id, problem_id, phase (initial | probe | reassess), student_response, student_explanation, is_correct, ranked diagnosis (JSON with scores), created_at
- `learner_misconceptions`: learner_id, misconception_id, status (active | improving | resolved), times_seen, last_seen, resolved_at
- `probes`: id, misconception pair, program, real output, predicted outputs (JSON), source (llm | bank)
- `candidate_misconceptions`: id, drafted description, source attempt, reviewed flag

A reappearance of a resolved misconception flips its status back to active and increments `times_seen`.

No real authentication. A learner picks or types a name on the first screen.

## 9. API

Propose exact request and response shapes in your plan. Minimum endpoints:

- `POST /learners`, `GET /learners`
- `POST /sessions` — start a session for a learner, returns the first problem
- `POST /sessions/{id}/answer` — submit response and reason; returns the next step. The response carries a `step` field, one of `correct`, `probe`, `intervention`, `reassess`, `result`, `unknown`, plus the payload for that step. The frontend renders whatever step it is given and holds no flow logic of its own.
- `GET /learners/{id}/history` — misconception statuses and attempt timeline
- `GET /evaluation` — model metrics (section 11)
- `GET /health` — reports which diagnoser is active and whether the LLM is reachable

Generate TypeScript types from the FastAPI OpenAPI schema, or keep one shared types file. Do not let the two sides drift.

## 10. Frontend screens

1. **Start.** Pick or create a learner.
2. **Learn** (the main screen, driven by `step`):
   - Problem panel: code viewer, answer box (or editor for `write_code`), one-line reason box.
   - Diagnosis panel: top 3 misconceptions with score bars, labelled "Trained model". Show "Unsure, asking a follow-up" or "Unknown misconception" when those paths fire.
   - Probe panel: the follow-up question, and afterwards which candidate it confirmed.
   - Intervention panel: explanation labelled "Generated explanation", plus the execution trace as a stepper (current line highlighted, variable table beside it), with the line where the student's belief diverges marked.
   - Reassessment: progress through the 2 to 3 problems, then the verdict (resolved, improving, still active) with the reason for it.
3. **Learner history.** Per-misconception status, times seen, last seen, and an attempt timeline.
4. **Evaluation.** Metrics table and charts (section 11).

Show a small badge with the active diagnoser (stub or model) so nobody demos the stub by accident.

Design: clean and legible on a projector. Large code font, clear state transitions, no decorative clutter. Every async action needs loading and error states; LLM calls can take several seconds.

## 11. Evaluation page

The training script writes `models/relearn-diagnosis/metrics.json`:

```json
{
  "model": "google/embeddinggemma-300m",
  "untuned": {"top1": 0.0, "top3": 0.0},
  "fine_tuned": {"top1": 0.0, "top3": 0.0}
}
```

More keys will be added later (held-out misconceptions, confusable-group accuracy, baselines, a confusion matrix). Render whatever is present and tolerate missing keys.

If the file does not exist, the page says "No evaluation results yet". Never show placeholder, hard-coded, or invented numbers anywhere in the app.

## 12. Config (one `.env` file, with a committed `.env.example`)

`DIAGNOSER`, `MODEL_PATH`, `QUERY_PROMPT`, `DOC_PROMPT`, `PROBE_GAP`, `UNKNOWN_THRESHOLD`, `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `DATA_DIR`, `DATABASE_URL`

## 13. Order of work

1. Backend skeleton: data loading, seed data, stub diagnoser, answer checking, session state machine for the simplest path (wrong answer, diagnosis, intervention with fallback text, reassess, verdict).
2. Frontend Learn screen wired to that path. At this point the demo works end to end.
3. Sandbox and execution trace.
4. LLM client: intervention text, then probes with checks and fallback.
5. Learner history and the unknown path.
6. Evaluation page.
7. Real-model diagnoser. Test it as soon as a model folder exists.
8. Polish.

Each milestone must leave the app runnable.

## 14. How to work

- Tests for anything that executes code: answer checking, the sandbox (timeout, infinite loop, file and network access attempts), the trace, and probe validation.
- Cache LLM responses on disk, keyed by prompt, so repeated demo runs are fast and survive bad wifi.
- A `README.md` with setup and run commands for both sides, and how to switch from stub to model.
- Say plainly when something will not fit in the time left, and suggest what to cut. First candidates to cut: `write_code` items, the candidate-misconception review list, charts on the evaluation page.

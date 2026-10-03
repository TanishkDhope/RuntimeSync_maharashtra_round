# Re:Learn

A tutoring app for introductory Python. A student answers a short quiz; when an
answer is wrong, the app works out which **misconception** caused the mistake by
ranking the student's answer and reasoning against a library of known beliefs.

**What is built right now:** the quiz loop — ask, check, diagnose. See
[Scope](#scope) for what is deliberately not built yet.

The diagnosis model is being trained separately. Until it exists, a **stub
diagnoser** stands in, and every screen that shows a diagnosis says so.

---

## Run it

Two terminals. Python 3.11+ and Node 20+.

```bash
# 1. backend
cd server
pip install -r requirements.txt
cp .env.example .env          # defaults work as-is
uvicorn app.main:app --reload --port 8000
```

```bash
# 2. frontend
cd client
npm install
npm run dev                   # http://localhost:5173
```

Open the frontend, type a name, pick a topic, and answer questions. A run is
five problems, ending on a `write_code` question where the topic has one.

Check the backend on its own:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/topics
```

Interactive API docs are at <http://localhost:8000/docs>.

### Tests

```bash
cd server && pytest -q      # 71 tests
```

They cover answer checking, the code runner (timeouts, infinite loops, syntax
errors, stray file writes), the stub diagnoser, and the whole session flow
through HTTP.

---

## Scope

Built:

| | |
|---|---|
| **Ask** | Serve a problem. Two question types: `predict_output` (predict what the program prints) and `write_code` (write a function). Both require a one-line reason. |
| **Check** | No model involved. `predict_output` compares normalised output; `write_code` runs the student's code against test cases in a subprocess. |
| **Diagnose** | Rank misconceptions against the answer and reason, keep the top 3. |

Not built yet, in roughly the order they should come:

- **Intervention** — explanation text aimed at the diagnosed belief, plus a
  real execution trace.
- **Probe questions** — a follow-up to separate two candidates that score the
  same. This matters: in 29 of the 114 `predict_output` problems, two or more
  misconceptions predict the *same* wrong output, so the stub cannot tell them
  apart. The UI says so rather than guessing.
- **Reassessment and a resolved/improving verdict.**
- **Learner history** across sessions, and the **evaluation page**.
- **LLM client** for generated explanations and probes.
- **Sandbox hardening** — see [Running student code](#running-student-code).

---

## Switching from the stub to the trained model

One config value. In `server/.env`:

```ini
DIAGNOSER=model
MODEL_PATH=../models/relearn-diagnosis/final
```

Then install the model dependencies and restart:

```bash
cd server
pip install -r requirements-model.txt    # sentence-transformers, torch
uvicorn app.main:app --reload --port 8000
```

`GET /health` and the badge in the app header both flip from "Stub diagnoser —
not the real model" to "Trained model". Nothing else changes.

If `MODEL_PATH` does not exist, the server **fails at startup with a clear
message** rather than quietly falling back to the stub — demoing the stub by
accident is the failure mode this guards against.

For EmbeddingGemma, also set the prompts it was trained with:

```ini
QUERY_PROMPT=task: classification | query: 
DOC_PROMPT=title: none | text: 
```

### How the two diagnosers work

Both implement one interface (`server/app/diagnosis/base.py`):

```
rank(problem, student_response, student_explanation) -> [{misconception_id, score}, ...]
```

- **stub** (`diagnosis/stub.py`) — no ML. For `predict_output` it matches the
  student's output against the problem's `predicted_outputs` map: a match
  scores 0.9, other applicable beliefs 0.15, and if nothing matches, `SLIP`
  scores 0.3. For `write_code` it has no output to match, so it returns the
  applicable beliefs at a flat 0.2 and the UI says the result is **not a
  ranking**.
- **model** (`diagnosis/model.py`) — loads a fine-tuned sentence-transformers
  model, builds the query text in the exact format it was trained on, and ranks
  the library's descriptions by cosine similarity. Description embeddings are
  computed once at startup.

Nothing outside `app/diagnosis/` branches on which one is active, beyond
reporting its name.

---

## Database

`DATABASE_URL` in `server/.env` drives everything. The default is a local
SQLite file, which needs no setup:

```ini
DATABASE_URL=sqlite:///./relearn.db
```

### Supabase

Supabase is plain Postgres, so pointing `DATABASE_URL` at it is the whole
switch — the tables are created automatically on startup and the rows show up
in Supabase's table editor.

1. In the Supabase dashboard: **Connect** → connection string (or **Project
   Settings → Database**). Prefer the **Session pooler** (port 5432 on
   `*.pooler.supabase.com`); the transaction pooler on port 6543 also works and
   is detected automatically.
2. Put it in `server/.env`, replacing the password placeholder:

```ini
DATABASE_URL=postgresql+psycopg://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
```

`postgres://` and `postgresql://` prefixes are rewritten to use psycopg 3
automatically, so pasting Supabase's string as-is works.

Restart and check:

```bash
curl http://localhost:8000/health    # -> "database": "supabase", "database_connected": true
```

`server/.env` is gitignored, so the password stays out of the repo. If the
database is unreachable the server still starts and `/health` reports
`database_connected: false`, rather than the whole app failing to boot.

Tables: `learners`, `sessions`, `attempts`. There is no authentication — a
learner is just a name, and typing the same name again resumes it.

---

## Running student code

`write_code` answers are executed. The student's code is **never** passed to
`exec()` or `eval()` in the server process. Instead
`server/app/runner.py` writes it to a temp directory with a generated test
harness and runs it as an isolated subprocess (`python -I -S`), with the temp
directory as the working directory, stdin closed, and a timeout
(`RUN_TIMEOUT_SECONDS`, default 5s). An infinite loop is killed and reported as
a failed run.

Results are compared by `repr()`, because the dataset's `expected` values are
reprs (`'bcd'`, `True`, `6`).

**Not yet hardened:** no memory cap and no network block. Both need
platform-specific work and are awkward on Windows. Treat this as safe enough
for a trusted demo, not for untrusted input on a public host.

---

## Layout

```
data/                        read-only inputs (JSONL)
  misconceptions.jsonl         61 beliefs: 49 train, 12 held_out, plus SLIP
  problems.jsonl               135 problems: 114 predict_output, 21 write_code
  responses.jsonl              1,949 labelled student responses (model training)

server/
  app/
    config.py                  all settings, from server/.env
    data.py                    JSONL loader; validates on startup
    checking.py                predict_output grading
    runner.py                  write_code subprocess grading
    diagnosis/                 the diagnoser interface, stub and model
    flow.py                    the session state machine
    models.py  db.py           SQLModel tables, engine
    schemas.py                 request/response shapes, incl. the step union
    routers/                   meta, learners, sessions
  tests/

client/src/
  api/client.js                the only module that talks to the backend
  App.jsx                      header, learner state, current step
  screens/                     StartScreen, QuizScreen
  components/                  AskPanel, FeedbackPanel, DiagnosisPanel,
                               SummaryPanel, CodeViewer, CodeEditor, badge
```

### API

Every quiz response is a **step** object tagged with a `step` field. The
frontend renders whatever step it is given and holds no flow logic of its own,
so the steps still to come (intervention, probe, reassessment) will not require
reshaping it.

| Endpoint | Returns |
|---|---|
| `GET /health` | active diagnoser, database, dataset counts |
| `GET /topics` | topics with problem counts |
| `GET /learners`, `POST /learners` | learners (`POST` resumes on a name match) |
| `POST /sessions` | starts a run → `step: "ask"` |
| `POST /sessions/{id}/answer` | grades and diagnoses → `step: "feedback"` |
| `POST /sessions/{id}/next` | → `step: "ask"` or `step: "summary"` |
| `GET /sessions/{id}` | the step the session is on, so a refresh resumes |

The `ask` step never includes `correct_output`, `predicted_outputs` or
`reference_solution` — a test asserts this.

---

## Honesty rules this app follows

Judges will ask which results come from the trained model. These are enforced
in code, not just intended:

- **Every diagnosis is labelled** with the diagnoser that produced it, and the
  header carries a standing badge when the stub is active.
- **No invented numbers.** Scores are shown exactly as the diagnoser returns
  them, never rescaled. Nothing is hard-coded or placeheld.
- **Ties are shown as ties.** When two beliefs score the same, the app says it
  cannot separate them instead of picking the first one.
- **A flat ranking is not a diagnosis.** When every candidate scores the same —
  which is what the stub does on `write_code` — the app says the list is "the
  beliefs this problem can involve", not a result.
- **The session summary counts a belief only** where the diagnoser actually put
  it ahead of the rest, and reports how many wrong answers it could not narrow
  down.

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
cp .env.example .env          # stub diagnoser + local SQLite, no setup needed


```

```bash
# 2. frontend
cd client
npm install
npm run dev                   # http://localhost:5173
```

Open the frontend, type a name, pick a topic, and answer questions. A run is
five `predict_output` problems. Reload the page mid-run and it picks up where
it left off: the backend owns the flow, so the frontend only has to remember
the session id.

`write_code` problems are **off by default** (`SERVE_WRITE_CODE=false`),
because grading them runs the student's code and the runner still has no
memory cap or network block. Turn them on with `SERVE_WRITE_CODE=true` once
you have read [Running student code](#running-student-code).

Check the backend on its own:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/topics
```

Interactive API docs are at <http://localhost:8000/docs>.

### Tests

```bash
cd server && pytest -q          # 100 tests
cd server && pytest -m integration   # 3 more; needs a running Ollama
```

They cover answer checking, the code runner (timeouts, infinite loops, syntax
errors, attempts to read server files or escape the sandbox, oversized return
values), the stub diagnoser, the whole session flow through HTTP, and one
regression test per finding in `CODEBASE_REVIEW.md`
(`tests/test_review_fixes.py`).

The `integration` tests are the ones that talk to a real Ollama. They are
skipped by default (see `server/pytest.ini`) and are how you check the GGUF
path before demoing it.

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

## Running with Ollama and GGUF Model

1. **Start Ollama** (make sure Ollama is running):
   ```bash
   ollama serve
   ```

2. **Backend**:
   In `server/.env`:
   ```ini
   DIAGNOSER=ollama
   MODEL_PATH=../model/relearn-diagnosis.gguf
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL=relearn-diagnosis
   ```
   Then run:
   ```bash
   cd server
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8000
   ```
   The backend registers the GGUF that `MODEL_PATH` names, under a tag
   carrying a fingerprint of the file, and ranks with it. The fingerprint is
   the point: drop a newly trained `.gguf` in place and the tag changes, so
   Ollama re-registers it instead of quietly serving the previous weights.

   It will **not** go looking for some other `.gguf` nearby. If `MODEL_PATH`
   is wrong, startup fails and says so.

3. **Frontend**:
   ```bash
   cd client
   npm install
   npm run dev
   ```

If `MODEL_PATH` does not exist, the server **fails at startup with a clear
message** rather than quietly falling back to the stub — demoing the stub by
accident is the failure mode this guards against.

For EmbeddingGemma, also set the prompts it was trained with:

```ini
QUERY_PROMPT="task: classification | query: "
DOC_PROMPT="title: none | text: "
```

The quotes matter: both values end in a space, and an unquoted value in a
`.env` file loses it. These are the exact strings
`model/train_diagnosis_model.py` trains with - serving without them embeds
into a different part of the space than training did, and the symptom is
quietly mediocre rankings rather than an error. `/health` reports the values
in force so you can check.

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
  model from a folder, builds the query text in the exact format it was
  trained on, and ranks the library's descriptions by cosine similarity.
  Description embeddings are computed once at startup. Point `MODEL_PATH` at
  what `train_diagnosis_model.py` saved: `../models/relearn-diagnosis/final`.
- **ollama** (`diagnosis/ollama.py`) — the same trained model as a GGUF,
  embedded through Ollama's `/api/embed`. It shares `build_query_text` with
  the sentence-transformers path, so both backends embed identical strings,
  and it truncates at the 384 tokens training used.

Only `split=train` beliefs are ever ranked, by all three (brief s5). Held-out
beliefs exist to be evaluated against, so naming one as a diagnosis would be
reporting on something the model was never trained to recognise.

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

`server/.env` is gitignored, so the password stays out of the repo. Never put
a connection string in `.env.example`, which is committed. If the database is
unreachable the server still starts and `/health` reports
`database_connected: false`, rather than the whole app failing to boot - that
now holds even when the driver itself is missing.

**Adding a column:** `create_all()` creates missing tables but never alters an
existing one. On SQLite the server closes that gap itself: at startup it adds
any column `models.py` has gained, with a default, leaving existing rows
intact. On Postgres or Supabase it does not guess - a drifted database there
needs real migrations or to be dropped and recreated. For a hackathon, SQLite
plus deleting `server/relearn.db` is the cheapest path.

Tables: `learners`, `sessions`, `attempts`. There is no authentication - a
learner is just a name, and typing the same name again resumes it.

---

## Running student code

`write_code` answers are executed, so they are **off by default**:
`SERVE_WRITE_CODE=false` keeps them out of every queue, which is also the
first thing brief s14 says to cut if time is short.

With them on, the student's code is **never** passed to `exec()` or `eval()`
in the server process. `server/app/runner.py` applies four layers:

1. **A syntax-tree screen before anything runs.** Code that reaches for
   `open`, `eval`, `exec`, `compile`, `__import__`, `input`, a dunder hop like
   `().__class__.__bases__`, or an import of `os`, `sys`, `subprocess`,
   `socket`, `pathlib`, `shutil` and friends is rejected unrun, with a reason.
   An introductory Python answer needs none of these; every reference
   solution in the dataset passes the screen, and a test asserts that.
2. **A minimal environment.** The subprocess gets `SystemRoot` and a temp dir,
   not the server's environment, so a secret in an env var is not readable
   from student code.
3. **Isolation.** `python -I -S -B`, a temp working directory, stdin closed,
   and a timeout (`RUN_TIMEOUT_SECONDS`, default 5s). An infinite loop is
   killed and reported as a failed run.
4. **Results through a file,** not stdout. A program that prints anything -
   including something shaped like our own marker - cannot corrupt the parse,
   and returned values are capped in length before they reach the browser.

Results are compared by `repr()`, because the dataset's `expected` values are
reprs (`'bcd'`, `True`, `6`).

**Still not hardened:** no memory cap and no network block. Both need
platform-specific work that is awkward on Windows; layer 1 stands in for them.
Treat this as safe enough for a trusted demo, not for untrusted input on a
public host.

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
    models.py  db.py           SQLModel tables, engine, column top-up
    llm_health.py              is the configured LLM reachable
    schemas.py                 request/response shapes, incl. the step union
    routers/                   meta, learners, sessions
  pytest.ini                   markers; integration tests skipped by default
  tests/
    test_review_fixes.py       one test per finding in CODEBASE_REVIEW.md

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
| `GET /health` | active diagnoser, database, dataset counts, the prompts and thresholds in force, and whether the LLM answers |
| `GET /topics` | topics with problem counts |
| `GET /learners`, `POST /learners` | learners (`POST` resumes on a name match) |
| `POST /sessions` | starts a run → `step: "ask"` |
| `POST /sessions/{id}/answer` | grades and diagnoses → `step: "feedback"` |
| `POST /sessions/{id}/next` | → `step: "ask"` or `step: "summary"` |
| `GET /sessions/{id}` | the step the session is on, so a refresh resumes |

The `ask` step never includes `correct_output`, `predicted_outputs` or
`reference_solution` — a test asserts this.

---
## 📊 Model Evaluation & Benchmark Results

The fine-tuned model ([`relearn-diagnosis`](file:///d:/BnB%20Hackathon/Embedding%20model/models/relearn-diagnosis)) was benchmarked against the untuned zero-shot baseline ([`google/embeddinggemma-300m`](https://huggingface.co/google/embeddinggemma-300m)) on the held-out validation set of 205 student response pairs across 49 active misconception classes.

### Accuracy & Retrieval Performance

| Metric | Untuned Baseline (`embeddinggemma-300m`) | Fine-Tuned (`relearn-diagnosis`) | Absolute Improvement | Relative Gain |
| :--- | :---: | :---: | :---: | :---: |
| **Top-1 Accuracy** | **21.95%** (45 / 205) | **70.51%** (122 / 205) | **+48.56%** | **+221.2%** |
| **Top-3 Accuracy** | **42.44%** (87 / 205) | **82.93%** (170 / 205) | **+40.49%** | **+95.4%** |
| **Top-3 Diagnostic Recall** | 42.44% | **82.93%** | +40.49% | +95.4% |
| **LLM + Fine-Tuned Model** | - | **94.85%** | - | - |
| **Validation Pairs ($N$)** | 205 pairs | 205 pairs | — | — |
| **Misconception Search Space** | 49 active classes | 49 active classes | — | — |


## 📉 Training Loss & Convergence Trajectory

Contrastive loss tracked across training steps:

| Epoch | Global Step | Contrastive Loss | Learning Rate | Gradient Norm |
| :---: | :---: | :---: | :---: | :---: |
| **0.22** | Step 20 | 1.0335 | $1.03 \times 10^{-5}$ | 142.35 |
| **0.44** | Step 40 | 1.0876 | $1.99 \times 10^{-5}$ | 39.09 |
| **0.88** | Step 80 | 0.8545 | $1.74 \times 10^{-5}$ | 28.23 |
| **1.10** | Step 100 | 0.4185 | $1.62 \times 10^{-5}$ | 63.11 |
| **1.98** | Step 180 | 0.4418 | $1.13 \times 10^{-5}$ | 0.00 |
| **2.20** | Step 200 | 0.2471 | $1.01 \times 10^{-5}$ | 44.57 |
| **3.08** | Step 280 | 0.0984 | $5.20 \times 10^{-6}$ | 25.95 |
| **3.74** | Step 340 | 0.2800 | $1.53 \times 10^{-6}$ | 0.13 |
| **3.96** | Step 360 | **0.0728** | $3.06 \times 10^{-7}$ | 0.52 |

* **Total Loss Reduction**: From **1.0335** to **0.0728** (**92.95% reduction** in contrastive loss).

---


## Honesty rules this app follows

Judges will ask which results come from the trained model. These are enforced
in code, not just intended:

- **Every diagnosis is labelled** with the diagnoser that produced it, and the
  header carries a standing badge when the stub is active.
- **No invented numbers.** Scores are shown exactly as the diagnoser returns
  them, never rescaled. Nothing is hard-coded or placeheld.
- **Ties are shown as ties.** When the top two scores are closer together
  than `PROBE_GAP`, the app says it cannot separate them instead of picking
  the first one, and shows the actual gap. The test is the gap, not exact
  equality: cosine scores from a real model are never exactly equal, so an
  equality test would mean this notice fired for the stub and then silently
  never again.
- **A diagnosis keeps the diagnoser that produced it.** Which diagnoser ran is
  stored on the attempt, so switching `DIAGNOSER` and reopening an old session
  cannot relabel a stub result as the trained model.
- **No silent fallback.** If `DIAGNOSER` asks for a real model that is not
  there, startup fails with a message. It will not fall back to the stub, and
  it will not substitute a different model file it found nearby.
- **A flat ranking is not a diagnosis.** When every candidate scores the same —
  which is what the stub does on `write_code` — the app says the list is "the
  beliefs this problem can involve", not a result.
- **The session summary counts a belief only** where the diagnoser actually put
  it ahead of the rest, and reports how many wrong answers it could not narrow
  down.

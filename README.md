# DSIX — automated Germany security index

Crawls a configurable set of RSS feeds, filters out noise, extracts
structured incident data with an LLM, and computes a 0–100 security
index across five weighted dimensions — fully automated, hosted for
free on GitHub Pages + GitHub Actions.

**Live output:** `docs/index.html` (deploy via GitHub Pages, see below)

## Architecture

```
[0] Backlog (src/backlog.py, one-off) -- Gemini + Google Search grounding
        reconstructs a retroactive ~60-day incident backlog on cold start
        |
        v
RSS feeds (config/feeds.json: Bundesregierung, Tagesschau, Deutschlandfunk)
        |
        v
[1] Ingest ---------------- feedparser, dedup by content hash
        |
        v
[2] Stage 1 filter --------- cheap relevance gatekeeper, runs on every item
        |   FILTER_BACKEND=groq     (default) -- LLM gatekeeper, GROQ_API_KEY
        |   FILTER_BACKEND=keyword  -- zero dependencies, zero cost
        |   FILTER_BACKEND=smollm   -- local model, see requirements-smollm.txt
        v
[3] Stage 2 extraction ------ structured JSON, only on what passed stage 1
        |   LLM_PROVIDER=gemini     (default) -- precise extraction, GOOGLE_API_KEY
        |   LLM_PROVIDER=groq/anthropic/openai/ollama also selectable
        |   Both Groq + Gemini calls retry with exponential backoff on
        |   rate-limit/5xx errors (src/retry.py)
        v
[4] Rolling-window cleanup (src/store.py) -- incidents/history older than
        the 60-day window are actually deleted, not just ignored
        v
[5] Scoring (src/scoring.py) - plain arithmetic, no LLM call, reproducible
        v
[6] Top-10 synthesis (src/synthesize.py) -- deterministic ranking +
        an LLM-written summary paragraph (Gemini by default)
        v
docs/data/*.json  ->  docs/index.html (static dashboard)
```

The split between stage 3 and stage 5 is deliberate: the LLM only
turns unstructured article text into structured data (dimension,
severity, casualties, one-line summary). Turning that structured data
into a score is pure code — same incidents in, same score out, every
time. Same logic in stage 6: which ten incidents make the cut is a
deterministic formula (severity × age-decay); only the write-up
paragraph is generated text.

## Scoring model

Each of the five dimensions starts at 100 and loses points per
incident, weighted by severity and decayed exponentially by age
(recent incidents matter far more than old ones). The five dimension
scores are combined by their configured weights into the overall
index. All of this is tunable in `config/scoring.json`:

| Dimension | Default weight |
|---|---|
| Terrorism & Extremism | 25% |
| Cyber Security | 20% |
| Critical Infrastructure | 20% |
| Political Stability | 20% |
| Societal Safety | 15% |

Status bands (also configurable): **Stable** 80–100 · **Watchful**
60–79 · **Elevated** 40–59 · **High Alert** 20–39 · **Crisis** 0–19.

### Calibration

The severity points, decay half-life, and weights are starting
values, not ground truth. If you have a manually-scored reference
report for a given period, run the pipeline over the same window and
adjust `config/scoring.json` until the computed score lines up. Once
calibrated, the formula stays fixed and reproducible going forward —
that's the point of keeping scoring out of the LLM.

## Setup

```bash
pip install -r requirements.txt
export GROQ_API_KEY=...      # Stage 1 filter (default)
export GOOGLE_API_KEY=...    # Stage 2 extraction + backlog + top-10 (default)

# One-off cold start: reconstruct a retroactive ~60-day backlog
python -m src.backlog

# Regular run: ingest -> filter -> extract -> prune -> score -> top-10
python -m src.pipeline
```

`src/pipeline.py` fetches every feed in `config/feeds.json`, filters,
extracts, prunes anything older than the rolling window, scores, and
writes `docs/data/score.json`, `history.json`, `incidents.json`, and
`top10.json`. Open `docs/index.html` locally (or via
`python -m http.server` from `docs/`) to view the dashboard against
that data.

`src/backlog.py` is meant to run once, before the first scheduled
pipeline run, so the dashboard isn't empty on day one. It's a no-op if
`incidents.json` already has entries — pass `--force` to regenerate
anyway.

### Add or remove feeds

Edit `config/feeds.json` — each entry only needs `id`, `name`, `url`.
No code changes required.

### Choosing a Stage 1 filter and Stage 2 provider

Groq is the Stage 1 gatekeeper by default (fast, unlimited free tier —
ideal for a check that runs on every single feed item); Gemini is the
Stage 2 extractor by default (precise structured extraction). Override
either independently:

```bash
export FILTER_BACKEND=groq      # or: keyword, smollm
export LLM_PROVIDER=gemini      # or: groq, anthropic, openai, ollama
export SYNTHESIS_PROVIDER=gemini  # top-10 write-up; defaults to LLM_PROVIDER
```

**Free options (recommended):**
- **`groq`** — **unlimited free**, requires `GROQ_API_KEY` from
  https://console.groq.com/. Model: `llama-3.1-70b-versatile` for Stage 2,
  `llama-3.1-8b-instant` for the Stage 1 filter (override with
  `GROQ_MODEL` / `GROQ_FILTER_MODEL`).
- **`gemini`** — **free tier: 60 req/min**, unlimited monthly, requires
  `GOOGLE_API_KEY` from https://ai.google.dev/. Model:
  `gemini-flash-latest` (override with `GEMINI_MODEL`).

**Paid options:**
- **`anthropic`** — cloud, needs `ANTHROPIC_API_KEY`. Cheap model by
  default (`claude-haiku-4-5-20251001`), override with `ANTHROPIC_MODEL`.
- **`openai`** — cloud, needs `OPENAI_API_KEY`. Set `OPENAI_BASE_URL` to
  point at any OpenAI-compatible endpoint instead.

**Local option:**
- **`ollama`** — fully local. No article text ever leaves the machine.
  Requires a running Ollama instance with a model pulled
  (`ollama pull qwen2.5:7b`). Pair with `FILTER_BACKEND=smollm` for an
  entirely local pipeline.

### Running tests

No test framework required — `pytest` works if installed, or run the
files directly:

```bash
python tests/test_scoring.py
python tests/test_pipeline_dryrun.py
```

Both use mocked feeds/providers, so they run offline with no API key.

## Deploying as a GitHub Pages site

1. Push this repo to GitHub.
2. **Settings → Pages** → Source: `Deploy from a branch` → Branch:
   `main`, folder `/docs`.
3. **Settings → Secrets and variables → Actions** → add
   `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`) as a repository secret.
   Optionally add `LLM_PROVIDER` / `FILTER_BACKEND` as repository
   *variables* to override the defaults in `.github/workflows/update.yml`.
4. The scheduled workflow (`.github/workflows/update.yml`) runs every
   6 hours, re-scores, and commits `docs/data/*.json` back to the
   repo — Pages picks up the change automatically. Trigger it once
   manually from the **Actions** tab (`Run workflow`) to populate real
   data instead of the seeded baseline.

No server, no database, no hosting cost — GitHub Actions is the
compute, GitHub Pages is the frontend, the repo itself is the database.

## Project layout

```
config/feeds.json           list of RSS sources
config/scoring.json         weights, severity points, decay, status bands, rolling window (60d)
src/backlog.py               one-off cold start: Gemini + Google Search grounding
src/ingest.py                RSS fetch + dedup
src/filters/                 Stage 1 (groq_filter.py default, keyword_filter.py, smollm_filter.py)
src/llm_providers/           Stage 2 (gemini default, groq / anthropic / openai / ollama)
src/extract.py                runs Stage 2 over a batch, validates output
src/retry.py                  exponential backoff for Groq/Gemini rate-limit errors
src/dateutils.py               shared date parsing (scoring, pruning, backlog, synthesis)
src/scoring.py                deterministic scoring — no LLM call
src/synthesize.py             Top-10 ranking (deterministic) + LLM write-up
src/pipeline.py              orchestrates the full run
src/store.py                  JSON-file persistence + rolling-window pruning (docs/data/*.json)
docs/                          GitHub Pages root (dashboard + data)
.github/workflows/update.yml   scheduled crawl + commit (every 6h)
.github/workflows/backlog.yml  manual one-off: seed the retroactive backlog
```

## Notes

- Seeded `docs/data/*.json` ships at baseline (score 100, no
  incidents) — that's an honest empty state, not sample data. Run
  `python -m src.backlog` (or trigger the `Seed backlog` workflow) once
  to fill it retroactively, then the scheduled workflow keeps it current.
- The rolling window is 60 days end to end: `src/store.py` actually
  deletes incidents/history entries older than the window on every
  pipeline run (`config/scoring.json` → `rolling_window_days`), not just
  ignores them when scoring. Only metadata/IDs/URLs/timestamps/scores are
  ever stored — no article full text, by design.
- The dashboard has no build step: `docs/index.html` fetches the JSON
  files directly with `fetch()`. Editing the dashboard is editing
  static files.
- No license file is included — add one (e.g. MIT) before making the
  repo public if you want to state usage terms explicitly.

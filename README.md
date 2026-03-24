# Earnings Transcript Processor

An AI-powered analyst tool that converts earnings call transcripts into structured, actionable output in real time. Built for Anomaly Capital Management.

---

## What it does

Paste or upload any earnings call transcript → the tool streams five structured sections live:

| Section | What it produces |
|---|---|
| **📋 Financial Summary** | Key metrics vs consensus/guidance, beats/misses flagged explicitly, key numbers bolded |
| **🔭 Guidance** | Full-year and Q4 revisions, changes from prior period, notable caveats |
| **💬 Q&A Highlights** | 3–5 analyst exchanges with analyst → executive attribution and management responses |
| **🎯 Tone / Sentiment** | Management posture, hedging, confidence — with grand sentiment display and confidence bar |
| **⚡ Investment Takeaway** | One paragraph: the single most important thing for a PM to know |

After analysis, a **Generate Email Draft** button assembles a clean, editable email from the sections — no extra API call.

---

## Setup

### Requirements
- Python 3.9+
- An Anthropic API key

### Install dependencies
```bash
pip install anthropic streamlit python-dotenv pypdf
```

### Set your API key
Create a `.env` file in the project root:
```
ANTHROPIC_API_KEY=your-key-here
```

### Run the app
```bash
streamlit run app.py
```

Opens at `http://localhost:8501`.

---

## Features

### Input
- **Paste** transcript directly into the text area
- **Upload** a file: `.txt`, `.md`, `.csv`, or `.pdf` (PDF text extracted via pypdf)
- Optional company name/ticker for labelling output

### Model selection
Three tiers, selectable from the sidebar:

| Option | Model | Speed | Cost |
|---|---|---|---|
| ⚡ Fastest | Claude Haiku 4.5 | ~5s | ~$0.002–0.005 |
| 🔶 Balanced | Claude Sonnet 4.6 | ~15s | ~$0.02–0.05 |
| 🔴 Most Thorough | Claude Opus 4.6 | ~30s | ~$0.10–0.25 |

### Streaming UI
- All five sections stream **simultaneously** — each runs as an independent parallel API call, so total wall-clock time equals the slowest section rather than the sum of all five
- Sections render as skeleton cards immediately, filling live as chunks arrive from each thread
- Full markdown formatting applied on completion (bold, bullets, headings, **tables rendered as styled HTML**)
- Output persists across setting changes — only cleared on a new run

### Run / Stop
- **▶ Run Analysis** starts streaming
- **⏹ Stop Analysis** appears during inference — stops the stream and preserves whatever has been generated so far

### Response length
Slider: **Concise** (2k tokens) / **Standard** (4k tokens) / **Detailed** (8k tokens)

### PII Obfuscation
Optional checkbox. When enabled:
- Runs on the model's output — catches every name actually written in the analysis
- Executives matched by title context (`CEO John Smith`, `John Smith — Chief Executive Officer`, etc.)
- Analysts matched by firm context (`Jane Doe — Goldman Sachs`, `Jane Doe from Morgan Stanley`, etc.)
- Second pass replaces full "First Last" name pairs and standalone last names throughout the text
- Tokens numbered: `[EXECUTIVE_1]`, `[ANALYST_1]`, etc.
- Structured signal lines (`SENTIMENT:`, `CONFIDENCE:`) are protected from replacement so the Tone/Sentiment display always renders correctly
- **PII Redaction Map** expander shows every token → real name mapping with colour coding

### Email Draft
After a completed analysis, click **✉️ Generate Email Draft**:
- Assembles sections into a clean plain-text email (no extra API call, no markdown artifacts)
- Editable **To / From / Subject / Body** fields
- Download as `.txt`

### Fun animations
Toggle wind streaks in the background — speed and colour themed per model tier.

### Consensus Estimates
Optional expander in settings. Paste in sell-side Revenue and EPS consensus — the Financial Summary section will explicitly state "beat by $X" / "missed by $X" rather than relying on the transcript mentioning it.

### Quarter-over-Quarter Comparison
Optional expander below the main transcript input. Upload or paste a prior quarter transcript — after the current analysis completes, a dedicated API call generates a **📊 Quarter-over-Quarter Comparison** card covering:
- Guidance changes (revised up/down/maintained with specific numbers)
- Tone shift (confidence, hedging, candour vs prior quarter)
- Narrative changes (themes that appeared, disappeared, or intensified)
- Red flags / green flags for the PM

### Cross-Transcript Memory
Every completed analysis is automatically saved to `transcript_history.json` (up to 50 entries). The **📚 History** expander in the settings panel lists past runs by company and date. Clicking **Load** on any entry opens a **side-by-side comparison view** — current run on the left, loaded run on the right — showing Guidance, Tone/Sentiment, and Investment Takeaway for both. History can be cleared at any time.

### Advanced / Dev
Expander with manual **temperature** and **max tokens** overrides.

---

## Performance

**Parallel section inferencing.**
Each of the five sections is produced by an independent API call running in its own background thread. All five fire simultaneously — total latency is the slowest section, not the sum of all five. Each section gets the full token budget independently, so no section competes with another for output length.

**Cached API client.**
The Anthropic client is instantiated once per process via `@st.cache_resource` and reused across all runs and all section threads, avoiding repeated connection overhead.

**Transcript length guard.**
- Hard block at 150,000 characters (~37k tokens) — shows a clear error before any API call is made
- Warning banner between 80,000–150,000 characters so the analyst knows to expect slower results

---

## Reliability

**Retry with exponential backoff.**
Each section thread retries up to 3 times on transient API errors (rate limit, overload/529, connection drop) with 1s → 2s backoff between attempts. Non-retryable errors (bad request, auth) bail immediately.

**Per-section timeout.**
If any section thread has not completed within 120 seconds, it is abandoned and an orange warning card is shown in its place. The other sections are unaffected and continue to completion.

**Graceful partial failure.**
If a section exhausts its retries and fails, a red error card replaces only that section. The remaining four sections render normally. The analysis is never fully aborted due to a single section failure.

---

## Design decisions

**Parallel calls over single call.**
Originally all five sections were produced in one API call. Parallel calls increase cost proportionally (5× output tokens) but cut wall-clock time significantly and give each section its own focused prompt and full token budget — producing better-separated, more detailed output per section.

**Delimiter-based parsing over JSON.**
The app prompts for `##SECTION##` delimiters rather than JSON. This eliminates an entire class of parse failures (fenced code blocks, trailing commas, truncated objects) and enables true token-by-token streaming — sections fill live rather than appearing all at once after a wait.

**Analyst-register system prompt.**
The system prompt positions the model as "a senior analyst at a long/short hedge fund" with explicit instructions to be direct, opinionated, and use real names. This produces output that reads like something an experienced analyst wrote, not a press release summary.

**PII on output, not input.**
Obfuscation runs on the model's output rather than the input transcript. This means the model always sees real names and writes naturally — the redaction is applied to what the analyst actually reads, not what the model reasons over.

---

## What I'd add with more time

- **IR scraper** — URL input that pulls the transcript from the company's IR site or Seeking Alpha, eliminating the paste step
- **Bloomberg/FactSet consensus integration** — auto-populate consensus fields from a live data source rather than manual paste
- **Evaluation harness** — run 20+ real transcripts, have analysts score each section 1–5, iterate on the prompt against real feedback
- **History search** — full-text search across saved runs, not just a list
- **Multi-transcript table** — cross-transcript financial summary table for peak earnings season (e.g. compare 10 companies at once)

---

## Files

```
├── app.py        # Main Streamlit application
└── README.md     # This file
```

---

## Cost reference

| Model | Typical run | Cost per transcript |
|---|---|---|
| Haiku 4.5 | ~5s | $0.002–0.005 |
| Sonnet 4.6 | ~15s | $0.02–0.05 |
| Opus 4.6 | ~30s | $0.10–0.25 |

At 15 transcripts/week on Sonnet: ~$0.45–$0.75/week.

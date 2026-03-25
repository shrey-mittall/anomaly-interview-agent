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
pip install anthropic streamlit python-dotenv pypdf requests beautifulsoup4 fpdf2
```

- `requests` + `beautifulsoup4` — URL transcript fetching (plain HTML pages)
- `fpdf2` — PDF export of analysis output

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
- **Fetch from URL** — paste a link to a plain HTML transcript page and click Fetch; JS-rendered or login-gated pages (e.g. Seeking Alpha) will not work
- Optional company name/ticker for labelling output

### Light / dark mode
The app adapts to Streamlit's built-in theme toggle. All card styles use tinted semi-transparent backgrounds and saturated accent colors that are readable in both modes. No dark-only overrides are forced on the base background or text — Streamlit's theme controls those natively.

### Keyboard shortcut
**Cmd+Enter** (Mac) / **Ctrl+Enter** (Windows) triggers Run Analysis from anywhere on the page.

### Export
- **Download (.txt)** — raw analysis output as plain text
- **Download (.pdf)** — formatted PDF with section headings and clean typography (requires `fpdf2`)

### Model selection
Three tiers, selectable from the sidebar:

| Option | Model | Speed | Cost |
|---|---|---|---|
| ⚡ Fastest | Claude Haiku 4.5 | ~5s | ~$0.002–0.005 |
| 🔶 Balanced | Claude Sonnet 4.6 | ~15s | ~$0.02–0.05 |
| 🔴 Most Thorough | Claude Opus 4.6 | ~30s | ~$0.10–0.25 |

### Streaming UI
- All five sections stream **in parallel** — each is an independent API call in its own thread, staggered 200 ms apart to avoid simultaneous rate-limit pressure
- Sections render as skeleton cards immediately, filling live as chunks arrive from each thread
- Full markdown formatting applied on completion (bold, bullets, headings, **tables rendered as styled HTML**)
- Output persists across setting changes — only cleared on a new run
- Per-section render errors show a local warning card without interrupting other sections

### Run / Stop
- **▶ Run Analysis** starts streaming
- **⏹ Stop Analysis** appears during inference — stops the stream and preserves whatever has been generated so far

### Response length
Three modes, controlled by a slider. Length is enforced through prompt instructions — token budgets are generous enough to never truncate an answer.

| Mode | Format |
|---|---|
| **Concise** | 3-5 bullets per section, numbers and key points only, 2-sentence takeaway |
| **Standard** | Tight bullets with a TL;DR / Bottom line per section, 3-4 sentence takeaway |
| **Detailed** | Full depth — segment breakdown, all caveats, 4-6 sentence takeaway |

Q&A always produces 3-5 exchanges regardless of mode; only the response length per exchange varies. Company name field removed — the tool reads company identity from the transcript.

### Hide Names
Optional checkbox. Earnings calls are public records, but this feature exists for cases where the tool is used on private or pre-release transcripts where name attribution should be kept internal. When enabled:
- Runs on the model's output — catches every name actually written in the analysis
- Executives matched by title context (`CEO John Smith`, `John Smith — Chief Executive Officer`, etc.)
- Analysts matched by firm context (`Jane Doe — Goldman Sachs`, `Jane Doe from Morgan Stanley`, etc.)
- Second pass replaces full "First Last" name pairs and standalone last names throughout the text
- Tokens numbered: `[EXECUTIVE_1]`, `[ANALYST_1]`, etc.
- Structured signal lines (`SENTIMENT:`, `CONFIDENCE:`) are protected from replacement so the Tone/Sentiment display always renders correctly
- Q&A section: bracket tokens are escaped in expander labels and stripped of stray `**` bold markers before display, so `[ANALYST_1]` renders cleanly in all contexts
- **Name Map** expander shows every token → real name mapping with colour coding

### Email Draft
After a completed analysis, click **✉️ Generate Email Draft**:
- Assembles sections into a clean plain-text email (no extra API call, no markdown artifacts)
- Editable **To / From / Subject / Body** fields
- Download as `.txt`

### Fun animations
Toggle wind streaks in the background — speed and colour themed per model tier. Off by default.

### Consensus Estimates
Optional expander in settings. Paste in sell-side Revenue and EPS consensus — the Financial Summary section will explicitly state "beat by $X" / "missed by $X" rather than relying on the transcript mentioning it.

### Quarter-over-Quarter Comparison
Optional expander below the main transcript input. Upload or paste a prior quarter transcript — the five main sections always run on the current transcript only (normal output format is preserved). After they complete, two additional API calls generate an appended **📊 Quarter-over-Quarter Comparison** card:

**Numeric delta table** — a grounded diff of key metrics (revenue, EBITDA margin, EPS, FCF, guidance ranges, leverage) showing Prior → Current with colour-coded change (green ↑ / red ↓). Each value is verified to appear literally in its source text before display — no inferred or calculated numbers.

**Narrative comparison** covering:
- Guidance changes (revised up/down/maintained with specific numbers)
- Tone shift (confidence, hedging, candour vs prior quarter)
- Narrative changes (themes that appeared, disappeared, or intensified)
- Red flags / green flags for the PM

The QoQ prompt enforces **2-3 bullets per section, under 300 words** and uses 1,024 token budget (vs prior 2,048) to prevent hitting limits mid-output.

### Cross-Transcript Memory
Every completed analysis is automatically saved to `transcript_history.json` (up to 50 entries). The **📚 History** expander in the settings panel lists past runs by company and date. Clicking **Load** on any entry opens a **side-by-side comparison view** — current run on the left, loaded run on the right — showing Guidance, Tone/Sentiment, and Investment Takeaway for both. History can be cleared at any time.

### Transcript Q&A
After a completed analysis, a **💬 Ask a Question** panel appears below the output. Type any question about the transcript and get a grounded answer — the model is instructed to answer only from what the transcript explicitly states and to quote directly when the answer depends on exact wording. If something isn't mentioned, it says so.

- **Multi-turn**: follow-up questions carry prior Q&A context, so you can drill down
- **Same model** as the main analysis run
- **Clear** button resets the Q&A history without affecting the analysis output
- History clears automatically when a new analysis is run

### Section tooltips
Each section heading (`Financial Summary`, `Guidance`, etc.) shows a hover tooltip with the exact brief description of what that section covers. Implemented as a CSS `::after` tooltip (instant on hover, dark-themed) rather than the native browser `title=` attribute.

---

## Performance

**Parallel section inferencing.**
Each of the five sections is produced by an independent API call running in its own background thread. Threads are staggered 200 ms apart (800 ms total) so calls don't all hit the API simultaneously and trigger rate-limit queuing — the primary cause of sections getting stuck on "Waiting...". Total latency is still the slowest section, not the sum of all five. Each section gets the full token budget independently.

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

**Sentiment/confidence signal protection.**
The tone section prompt instructs the model to output `SENTIMENT: Word` and `CONFIDENCE: Word` without brackets. The PII obfuscation pass protects these lines from name replacement via placeholder swap. `_extract_signal()` scans from the **end** of the tone text, accepting only values that match the known color map — so body text that happens to contain the words "sentiment" or "confidence" cannot pollute the display. `.capitalize()` normalisation handles `medium`/`MEDIUM`/`Medium` identically. These layers ensure the sentiment display renders reliably regardless of model formatting variation or PII obfuscation state.

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

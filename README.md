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
- Sections render as skeleton cards immediately, filling live as the model streams
- Full markdown formatting applied on completion (bold, bullets, headings)
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
- **PII Redaction Map** expander shows every token → real name mapping with colour coding

### Email Draft
After a completed analysis, click **✉️ Generate Email Draft**:
- Assembles sections into a clean plain-text email (no extra API call, no markdown artifacts)
- Editable **To / From / Subject / Body** fields
- Download as `.txt`

### Fun animations
Toggle wind streaks in the background — speed and colour themed per model tier.

### Advanced / Dev
Expander with manual **temperature** and **max tokens** overrides.

---

## Design decisions

**Delimiter-based parsing over JSON.**
The app prompts for `##SECTION##` delimiters rather than JSON. This eliminates an entire class of parse failures (fenced code blocks, trailing commas, truncated objects) and enables true token-by-token streaming — sections fill live rather than appearing all at once after a wait.

**Analyst-register system prompt.**
The system prompt positions the model as "a senior analyst at a long/short hedge fund" with explicit instructions to be direct, opinionated, and use real names. This produces output that reads like something an experienced analyst wrote, not a press release summary.

**PII on output, not input.**
Obfuscation runs on the model's output rather than the input transcript. This means the model always sees real names and writes naturally — the redaction is applied to what the analyst actually reads, not what the model reasons over.

**Single API call.**
All five sections are produced in one call. An alternative would be five separate calls (one per section) for longer, more detailed output — but at 5× the cost and latency. For an analyst reading this at 8am before market open, a single fast call felt right.

---

## What I'd add with more time

- **IR scraper** — URL input that pulls the transcript from the company's IR site or Seeking Alpha, eliminating the paste step
- **Consensus data integration** — Bloomberg/FactSet API to auto-populate "vs consensus" comparisons rather than relying on the transcript mentioning it
- **Evaluation harness** — run 20+ real transcripts, have analysts score each section 1–5, iterate on the prompt against real feedback
- **Multi-transcript comparison** — side-by-side view or cross-transcript financial summary table for peak earnings season
- **Persistent history** — store past analyses with search, so you can pull up last quarter's output alongside this quarter's

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

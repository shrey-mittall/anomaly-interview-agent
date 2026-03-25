"""
Earnings Transcript Processor
Anomaly Capital Management — Internal Analyst Tool
"""

from dotenv import load_dotenv
load_dotenv()

import anthropic
import streamlit as st
import re
import random
import time
import threading
import queue as _queue
import json
import os
import uuid

from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
    _SCRAPE_AVAILABLE = True
except ImportError:
    _SCRAPE_AVAILABLE = False

try:
    from fpdf import FPDF
    _PDF_AVAILABLE = True
except ImportError:
    _PDF_AVAILABLE = False

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Earnings Transcript Processor",
    page_icon="📊",
    layout="wide",
)

# ── Base CSS (dark theme) ─────────────────────────────────────────────────────
st.markdown("""
<style>
    body { background-color: #0b0e17 !important; }
    .stApp { background: transparent !important; }
    section[data-testid="stSidebar"] { background: rgba(11,14,23,0.85) !important; }
    .stApp * { color: #dde3ef; }
    h1, h2, h3, label, .stMarkdown p { color: #dde3ef !important; }

    .section-card {
        background: rgba(255,255,255,0.04);
        border-left: 4px solid #3b82f6;
        border-radius: 6px;
        padding: 16px 20px;
        margin-bottom: 18px;
        backdrop-filter: blur(4px);
    }
    .section-card, .section-card * { color: #dde3ef !important; }
    .section-card h3 { margin-top: 0; color: #60a5fa !important; font-size: 15px; }

    .takeaway-card {
        background: rgba(16,185,129,0.07);
        border-left: 4px solid #10b981;
        border-radius: 6px;
        padding: 16px 20px;
        margin-bottom: 18px;
    }
    .takeaway-card, .takeaway-card * { color: #dde3ef !important; }
    .takeaway-card h3 { color: #34d399 !important; font-size: 15px; margin-top: 0; }

    .sentiment-card {
        border-left: 4px solid #f59e0b;
        background: rgba(245,158,11,0.07);
        border-radius: 6px;
        padding: 16px 20px;
        margin-bottom: 18px;
    }
    .sentiment-card, .sentiment-card * { color: #dde3ef !important; }
    .sentiment-card h3 { color: #fbbf24 !important; font-size: 15px; margin-top: 0; }

    .qoq-card {
        background: rgba(139,92,246,0.07);
        border-left: 4px solid #8b5cf6;
        border-radius: 6px;
        padding: 16px 20px;
        margin-bottom: 18px;
    }
    .qoq-card, .qoq-card * { color: #dde3ef !important; }
    .qoq-card h3 { color: #a78bfa !important; font-size: 15px; margin-top: 0; }

    .history-card {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 6px;
        padding: 10px 14px;
        margin-bottom: 8px;
        font-size: 13px;
    }

    .email-card {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 6px;
        padding: 20px 24px;
        margin-bottom: 18px;
    }
    .email-card, .email-card * { color: #dde3ef !important; }
    .email-card h3 { margin-top: 0; color: #93c5fd !important; font-size: 15px; }

    .meta-bar {
        font-size: 12px;
        color: #6b7280 !important;
        margin-bottom: 24px;
        border-bottom: 1px solid rgba(255,255,255,0.08);
        padding-bottom: 10px;
    }
    .stTextArea textarea {
        font-family: monospace;
        font-size: 13px;
        background: rgba(255,255,255,0.04) !important;
        color: #dde3ef !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
    }

    /* wind behind content, above body */
    .wind-layer {
        position: fixed;
        top: 0; left: 0;
        width: 100vw; height: 100vh;
        pointer-events: none;
        overflow: hidden;
        z-index: 0;
    }
    /* content panel blocks wind visually */
    .main .block-container {
        position: relative;
        z-index: 1;
        background: rgba(11,14,23,0.88);
        border-radius: 12px;
    }
    section[data-testid="stSidebar"] {
        background: rgba(11,14,23,0.90) !important;
    }

    /* Section-title tooltip */
    .tip {
        position: relative;
        cursor: help;
        display: inline-block;
    }
    .tip::after {
        content: attr(data-tip);
        position: absolute;
        bottom: calc(100% + 6px);
        left: 0;
        background: rgba(15,20,35,0.97);
        color: #cbd5e1;
        font-size: 12px;
        font-weight: 400;
        line-height: 1.5;
        padding: 8px 12px;
        border-radius: 6px;
        border: 1px solid rgba(255,255,255,0.12);
        width: 300px;
        white-space: normal;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.15s ease;
        z-index: 9999;
        box-shadow: 0 4px 16px rgba(0,0,0,0.5);
    }
    .tip:hover::after { opacity: 1; }
</style>
""", unsafe_allow_html=True)

# ── Model options ─────────────────────────────────────────────────────────────
MODELS = {
    "⚡ Fastest":      "claude-haiku-4-5-20251001",
    "🔶 Balanced":     "claude-sonnet-4-6",
    "🔴 Most Thorough": "claude-opus-4-6",
}

MODEL_INFO = {
    "⚡ Fastest": {
        "model_name": "Claude Haiku 4.5",
        "quality": "Good for straightforward transcripts",
        "cost": "~$0.002–0.005 / transcript",
        "color": "#34d399",
        "wind_rgba": "52,211,153",
        "wind_dur_range": (1.5, 3.5),
        "wind_count": 60,
    },
    "🔶 Balanced": {
        "model_name": "Claude Sonnet 4.6",
        "quality": "Strong reasoning, handles complex calls well",
        "cost": "~$0.02–0.05 / transcript",
        "color": "#fbbf24",
        "wind_rgba": "251,191,36",
        "wind_dur_range": (4, 8),
        "wind_count": 38,
    },
    "🔴 Most Thorough": {
        "model_name": "Claude Opus 4.6",
        "quality": "Most nuanced analysis, best for high-stakes calls",
        "cost": "~$0.10–0.25 / transcript",
        "color": "#a78bfa",
        "wind_rgba": "167,139,250",
        "wind_dur_range": (9, 16),
        "wind_count": 22,
    },
}

def inject_theme(info: dict):
    """Inject per-model wind animation via pure CSS keyframes."""
    rng = random.Random(99)
    rgba = info["wind_rgba"]
    dmin, dmax = info["wind_dur_range"]
    count = info["wind_count"]

    rules, divs = [], []
    for i in range(count):
        dur    = rng.uniform(dmin, dmax)
        delay  = rng.uniform(0, dur)
        y      = rng.uniform(1, 97)
        drift  = rng.uniform(-4, 4)
        width  = rng.uniform(180, 600)
        height = rng.uniform(6, 22)
        op     = rng.uniform(0.07, 0.22)
        blur   = rng.uniform(2, 6)
        angle  = rng.uniform(-2, 2)

        rules.append(
            f"@keyframes w{i}{{"
            f"0%{{transform:translateX(-700px) translateY(0) rotate({angle:.1f}deg);opacity:0;}}"
            f"7%{{opacity:{op:.3f};}}"
            f"93%{{opacity:{op:.3f};}}"
            f"100%{{transform:translateX(calc(100vw + 700px)) translateY({drift:.1f}vh) rotate({angle:.1f}deg);opacity:0;}}}}"
            f".ws{i}{{position:fixed;top:{y:.2f}vh;left:0;"
            f"width:{width:.0f}px;height:{height:.1f}px;"
            f"background:linear-gradient(90deg,transparent,rgba({rgba},{min(op*2.5,0.55):.3f}),rgba({rgba},{op:.3f}),transparent);"
            f"border-radius:50%;"
            f"animation:w{i} {dur:.2f}s {delay:.2f}s linear infinite backwards;"
            f"pointer-events:none;z-index:0;filter:blur({blur:.1f}px);}}"
        )
        divs.append(f'<div class="ws{i}"></div>')

    st.markdown(
        f'<style>{"".join(rules)}</style>'
        f'<div class="wind-layer">{"".join(divs)}</div>',
        unsafe_allow_html=True,
    )

LENGTH_SETTINGS = {
    "Concise":  {"desc": "Bullet-point brevity. Skip elaboration.",        "max_tokens": 2048},
    "Standard": {"desc": "Balanced depth. Normal analyst brief.",          "max_tokens": 4096},
    "Detailed": {"desc": "Full depth. Include all caveats and nuance.",    "max_tokens": 8192},
}

# Rough chars-per-token estimate for English prose
_CHARS_PER_TOKEN = 4

def dynamic_max_tokens(transcript: str, length_preset: int) -> int:
    """Scale token budget with transcript size, capped at the preset."""
    transcript_tokens = len(transcript) // _CHARS_PER_TOKEN
    # Output budget: ~30% of input length, minimum 1024, capped at preset
    suggested = max(1024, min(transcript_tokens // 3, length_preset))
    return suggested

MAX_TRANSCRIPT_CHARS = 150_000   # ~37k tokens — well within 200k context window
WARN_TRANSCRIPT_CHARS = 80_000   # warn but still allow

# ── History (cross-transcript memory) ────────────────────────────────────────
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "transcript_history.json")
HISTORY_MAX  = 50

def load_history() -> list:
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_run_to_history(company: str, ts: str, model_label: str, sections: dict):
    history = load_history()
    history.insert(0, {
        "id":        str(uuid.uuid4())[:8],
        "timestamp": ts,
        "company":   company or "Unknown",
        "model":     model_label,
        "sections":  sections,
    })
    history = history[:HISTORY_MAX]
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass  # non-fatal

# ── PII obfuscation ───────────────────────────────────────────────────────────
def obfuscate_pii(text: str):
    """Replace PII with numbered tokens. Returns (cleaned_text, legend)."""

    # Protect structured signal lines so PII passes never touch them
    _protected = {}
    def _protect(m):
        key = f'\x00SIGNAL{len(_protected)}\x00'
        _protected[key] = m.group(0)
        return key
    text = re.sub(r'^(?:SENTIMENT|CONFIDENCE):[^\n]*', _protect, text, flags=re.MULTILINE | re.IGNORECASE)

    registry = {}   # original_value -> token e.g. "John Smith" -> "EXECUTIVE_1"
    counters = {}   # label -> count

    def token_for(val: str, label: str) -> str:
        if val not in registry:
            counters[label] = counters.get(label, 0) + 1
            registry[val] = f"{label}_{counters[label]}"
        return registry[val]

    def replace(pattern, label, flags=0):
        nonlocal text
        def sub_fn(m):
            val = m.group(0).strip()
            return f'[{token_for(val, label)}]'
        text = re.sub(pattern, sub_fn, text, flags=flags)

    _EXEC_TITLES = r'CEO|CFO|COO|CTO|President|Chairman|Director|Chief[^\S\n]+\w+(?:[^\S\n]+\w+)?[^\S\n]+Officer'

    # Executives: titled or role-labelled (run before analyst patterns)
    replace(r'\b(Mr\.|Ms\.|Mrs\.|Dr\.)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+', 'EXECUTIVE')
    replace(rf'\b(?:{_EXEC_TITLES})\s+[A-Z][a-z]+\s+[A-Z][a-z]+', 'EXECUTIVE')
    replace(rf'\b[A-Z][a-z]+\s+[A-Z][a-z]+,\s+(?:{_EXEC_TITLES})', 'EXECUTIVE')
    replace(rf'\b[A-Z][a-z]+\s+[A-Z][a-z]+\s*[–—-]{{1,2}}\s*(?:{_EXEC_TITLES})', 'EXECUTIVE')

    _FIRM_SUFFIXES = (r'Capital|Securities|Management|Partners|Advisors|Research|Group|Bank|'
                     r'Sachs|Stanley|Chase|Lynch|Fargo|Barclays|Citi|JPMorgan|Goldman|Morgan|'
                     r'Wells|Jefferies|Cowen|Piper|Baird|Oppenheimer|Raymond|Bernstein|'
                     r'Equity|Investment|Asset|Investments|Financial|Markets|Analytics|'
                     r'Funds|Hedge|Trading|Strategy|Strategies')

    # Analysts: "Name — Firm" only when firm ends with a known suffix (prevents matching "Earnings Update – ACME Corp" etc.)
    replace(rf'\b[A-Z][a-z]+[^\S\n]+[A-Z][a-z]+[^\S\n]*[–—-]{{1,2}}[^\S\n]*(?!(?:{_EXEC_TITLES}))[A-Z][A-Za-z &,\.]+(?:{_FIRM_SUFFIXES})', 'ANALYST')
    replace(rf'\b[A-Z][a-z]+[^\S\n]+[A-Z][a-z]+[^\S\n]+(?:from|at|with|of)[^\S\n]+[A-Z][A-Za-z &,\.]+(?:{_FIRM_SUFFIXES})', 'ANALYST')

    # Contact info
    replace(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', 'PHONE')
    replace(r'\b[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}\b', 'EMAIL')

    # Second pass: replace full "First Last" and standalone last names wherever they appear
    for original, token in list(registry.items()):
        # Strip firm/title suffix to isolate the person's name
        clean = re.split(r'\s*[–—,\-]\s*', original)[0].strip()
        clean = re.sub(r'^(Mr\.|Ms\.|Mrs\.|Dr\.)\s+', '', clean)
        clean = re.sub(r'\s+(CEO|CFO|COO|CTO|President|Chairman|Director)$', '', clean, flags=re.IGNORECASE).strip()
        words = clean.split()
        if len(words) >= 2:
            # Replace "First Last" pair first (so it doesn't leave orphaned first names)
            full = ' '.join(words[:2])
            text = re.sub(rf'\b{re.escape(full)}\b', f'[{token}]', text)
            # Then replace standalone last name
            last = words[-1]
            if len(last) >= 4:
                text = re.sub(rf'\b{re.escape(last)}\b', f'[{token}]', text)

    # Restore protected signal lines
    for key, val in _protected.items():
        text = text.replace(key, val)

    legend = [{"token": tok, "value": val} for val, tok in sorted(registry.items(), key=lambda x: x[1])]
    return text, legend, registry

# ── Prompts ───────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a senior investment analyst at a long/short hedge fund.
Your job is to process earnings call transcripts and extract structured intelligence
that a portfolio manager can act on quickly. Be direct, specific, and opinionated.
Avoid corporate language. Write for an analyst audience.
Always use real names: include the full names of executives speaking and analysts asking questions exactly as they appear in the transcript. Never substitute "the CEO", "management", or "an analyst" when actual names are present."""

SECTION_DELIMITERS = [
    "##FINANCIAL_SUMMARY##",
    "##GUIDANCE##",
    "##QA_HIGHLIGHTS##",
    "##TONE_SENTIMENT##",
    "##INVESTMENT_TAKEAWAY##",
]

def build_user_prompt(transcript: str, length: str) -> str:
    length_instruction = LENGTH_SETTINGS[length]["desc"]

    return f"""Analyze the following earnings call transcript. Output exactly five sections using the delimiter tags shown. No preamble, no extra commentary — only the sections below.

Length guidance: {length_instruction}

##FINANCIAL_SUMMARY##
Key reported metrics — revenue (actual vs consensus/guidance), EBITDA margin, EPS, free cash flow. Note beats and misses explicitly. Use **bold** for key numbers and beat/miss labels.

##GUIDANCE##
Forward-looking statements only — revised full-year guidance, Q4 specifics, segment-level commentary, notable caveats. Flag meaningful changes from prior guidance.

##QA_HIGHLIGHTS##
3 to 5 Q&A exchanges. Number each block and separate with ---. Use exactly this format:
Q1
ANALYST: [full name — firm, exactly as in transcript]
EXECUTIVE: [full name — title, exactly as in transcript]
QUESTION: [1-2 sentence paraphrase]
RESPONSE: [2-4 sentences, include numbers/commitments, note if evasive]
---
Q2
ANALYST: [full name — firm]
EXECUTIVE: [full name — title]
QUESTION: [...]
RESPONSE: [...]
---

##TONE_SENTIMENT##
Qualitative read of management tone — overall posture, hedging/deflection, moments of unusual confidence, contrast between prepared remarks and Q&A tone.
End with these two lines exactly:
SENTIMENT: [Bearish / Cautious / Neutral / Constructive / Bullish]
CONFIDENCE: [Low / Medium / High]

##INVESTMENT_TAKEAWAY##
One paragraph (4-6 sentences). Key driver of miss/beat, thesis implications, biggest open question, instinct on stock reaction.

Now write the actual content for each section based on this transcript:
{transcript}"""


# ── Cached API client ─────────────────────────────────────────────────────────
@st.cache_resource
def get_client():
    return anthropic.Anthropic()


# ── Per-section prompts (used for parallel inferencing) ───────────────────────
_SECTION_INSTRUCTIONS = {
    "##FINANCIAL_SUMMARY##": (
        "Write the financial summary for this earnings call.\n"
        "Cover key reported metrics — revenue (actual vs consensus/guidance), EBITDA margin, EPS, free cash flow. "
        "Note beats and misses explicitly. Use **bold** for key numbers and beat/miss labels. "
        "Use real names of executives when relevant."
    ),
    "##GUIDANCE##": (
        "Write the guidance section for this earnings call.\n"
        "Cover forward-looking statements only — revised full-year guidance, Q4 specifics, "
        "segment-level commentary, notable caveats. Flag meaningful changes from prior guidance."
    ),
    "##QA_HIGHLIGHTS##": (
        "Write the Q&A highlights for this earnings call.\n"
        "3 to 5 Q&A exchanges. Number each block and separate with ---. Use exactly this format:\n"
        "Q1\nANALYST: [full name — firm, exactly as in transcript]\n"
        "EXECUTIVE: [full name — title, exactly as in transcript]\n"
        "QUESTION: [1-2 sentence paraphrase]\nRESPONSE: [2-4 sentences, include numbers/commitments, note if evasive]\n"
        "---"
    ),
    "##TONE_SENTIMENT##": (
        "Write the tone/sentiment section for this earnings call.\n"
        "Qualitative read of management tone — overall posture, hedging/deflection, moments of unusual confidence, "
        "contrast between prepared remarks and Q&A tone.\n"
        "End with these two lines exactly (no brackets, just the word):\n"
        "SENTIMENT: Bearish\n"
        "...or Cautious, Neutral, Constructive, Bullish — pick one.\n"
        "CONFIDENCE: Low\n"
        "...or Medium, High — pick one."
    ),
    "##INVESTMENT_TAKEAWAY##": (
        "Write the investment takeaway for this earnings call.\n"
        "One paragraph (4-6 sentences). Key driver of miss/beat, thesis implications, "
        "biggest open question, instinct on stock reaction."
    ),
}


def build_section_prompt(transcript: str, length: str, section: str, consensus: str = "") -> str:
    length_instruction = LENGTH_SETTINGS[length]["desc"]
    instruction = _SECTION_INSTRUCTIONS[section]
    if section == "##FINANCIAL_SUMMARY##" and consensus.strip():
        instruction = (
            f"Consensus estimates to reference when stating beats/misses:\n{consensus.strip()}\n"
            "Use these to explicitly state 'beat by $X' or 'missed by $X' where applicable.\n\n"
            + instruction
        )
    return f"Length guidance: {length_instruction}\n\n{instruction}\n\nTranscript:\n{transcript}"


_MAX_RETRIES      = 3
_SECTION_TIMEOUT  = 120   # seconds before a hung section is abandoned
_RETRYABLE_ERRORS = (
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.APIStatusError,   # catches 529 overload
)


def _stream_section(section_key: str, transcript: str, length: str,
                    model: str, max_tokens: int, temperature: float,
                    out: _queue.Queue, consensus: str = ""):
    """Stream one section in a background thread.

    Queue items: (section_key, chunk, is_done, error_str_or_None)
    Retries up to _MAX_RETRIES times on transient API errors with
    exponential backoff before signalling failure.
    """
    last_err = None
    for attempt in range(_MAX_RETRIES):
        try:
            with get_client().messages.stream(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": build_section_prompt(transcript, length, section_key, consensus)}],
            ) as stream:
                for text in stream.text_stream:
                    out.put((section_key, text, False, None))
            out.put((section_key, "", True, None))   # success
            return
        except _RETRYABLE_ERRORS as e:
            last_err = e
            if attempt < _MAX_RETRIES - 1:
                time.sleep(2 ** attempt)   # 1s → 2s → stop
        except Exception as e:
            last_err = e
            break   # non-retryable — bail immediately
    out.put((section_key, "", True, str(last_err)))


# ── QoQ comparison ────────────────────────────────────────────────────────────
_QOQ_SYSTEM = """You are a senior investment analyst comparing two consecutive earnings calls for the same company.
Be extremely concise — bullets only, no preamble, no summary sentence. Flag changes, not similarities.
Each section gets 2-3 bullets maximum. Total response must be under 300 words."""

def run_qoq_comparison_streaming(
    cur_guidance: str, cur_tone: str,
    prior_transcript: str,
    model: str, max_tokens: int, temperature: float,
):
    """Stream a quarter-over-quarter comparison given current sections + prior transcript."""
    # Trim prior transcript to keep prompt tight and avoid token overrun
    prior_trimmed = prior_transcript[:15_000]

    prompt = f"""Compare current vs prior quarter. Be brief — 2-3 bullets per section max.

CURRENT QUARTER — GUIDANCE:
{cur_guidance[:3_000]}

CURRENT QUARTER — TONE/SENTIMENT:
{cur_tone[:1_500]}

PRIOR QUARTER TRANSCRIPT (excerpt):
{prior_trimmed}

Cover exactly these four sections, each with 2-3 bullets only:
1. **Guidance changes** — revised up/down/maintained. Numbers only, no prose.
2. **Tone shift** — more/less confident vs prior. One key observation.
3. **Narrative changes** — themes that appeared, disappeared, or intensified. Key ones only.
4. **Red flags / green flags** — actionable items for a PM. Flag the most important change only.

Total response: under 300 words. Skip anything unchanged."""

    with get_client().messages.stream(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=_QOQ_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            yield text


# ── Parsing helpers ───────────────────────────────────────────────────────────
def parse_sections(raw: str) -> dict:
    """Split raw model output into sections by delimiter tags."""
    sections = {}
    for i, delim in enumerate(SECTION_DELIMITERS):
        next_delim = SECTION_DELIMITERS[i + 1] if i + 1 < len(SECTION_DELIMITERS) else None
        start = raw.find(delim)
        if start == -1:
            sections[delim] = ""
            continue
        start += len(delim)
        end = raw.find(next_delim) if next_delim else len(raw)
        content = raw[start:end].strip()
        # Strip any stray ##...## tags the model may have echoed
        content = re.sub(r'##[A-Z0-9_]+##', '', content).strip()
        sections[delim] = content
    return sections


def parse_qa(qa_text: str) -> list:
    """Parse Q&A block with multiple fallback strategies."""
    def extract_fields(block: str):
        analyst   = re.search(r'ANALYST:\s*(.+)',        block)
        executive = re.search(r'EXECUTIVE:\s*(.+)',      block)
        question  = re.search(r'QUESTION:\s*(.+)',       block)
        response  = re.search(r'RESPONSE:\s*([\s\S]+)',  block)
        if not any([analyst, question, response]):
            return None
        return {
            "analyst":   analyst.group(1).strip()   if analyst   else "",
            "executive": executive.group(1).strip() if executive else "",
            "question":  question.group(1).strip()  if question  else "",
            "response":  response.group(1).strip()  if response  else "",
        }

    # Strategy 1: split on ---
    blocks = [b.strip() for b in qa_text.split("---") if b.strip()]
    entries = [r for b in blocks if (r := extract_fields(b))]
    if entries:
        return entries

    # Strategy 2: split on Q1 / Q2 / Q3 ... numbered headers
    blocks = [b.strip() for b in re.split(r'\bQ\d+\b', qa_text) if b.strip()]
    entries = [r for b in blocks if (r := extract_fields(b))]
    if entries:
        return entries

    # Strategy 3: treat each ANALYST: occurrence as a block boundary
    parts = re.split(r'(?=ANALYST:)', qa_text)
    entries = [r for b in parts if b.strip() and (r := extract_fields(b))]
    return entries


def _md_inline(text: str) -> str:
    """Apply inline markdown (bold/italic) to a string."""
    text = re.sub(r'\*\*\*(.*?)\*\*\*', r'<strong><em>\1</em></strong>', text)
    text = re.sub(r'\*\*(.*?)\*\*',     r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.*?)\*',          r'<em>\1</em>', text)
    return text


def _render_md_table(table_lines: list) -> str:
    """Convert a block of markdown table lines into an HTML table."""
    rows = []
    for line in table_lines:
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        rows.append(cells)

    # Find the separator row (|----|----| style)
    sep_idx = next(
        (i for i, r in enumerate(rows) if all(re.match(r'^[-:\s]+$', c) for c in r if c)),
        None,
    )
    header_rows = rows[:sep_idx] if sep_idx is not None else []
    body_rows   = rows[sep_idx + 1:] if sep_idx is not None else rows

    html = '<table style="width:100%;border-collapse:collapse;margin:10px 0;font-size:13px">'
    if header_rows:
        html += '<thead>'
        for row in header_rows:
            html += '<tr>' + ''.join(
                f'<th style="border-bottom:1px solid rgba(255,255,255,0.2);padding:6px 10px;'
                f'text-align:left;color:#60a5fa;white-space:nowrap">{_md_inline(c)}</th>'
                for c in row
            ) + '</tr>'
        html += '</thead>'
    html += '<tbody>'
    for row in body_rows:
        html += '<tr>' + ''.join(
            f'<td style="border-bottom:1px solid rgba(255,255,255,0.07);'
            f'padding:6px 10px">{_md_inline(c)}</td>'
            for c in row
        ) + '</tr>'
    html += '</tbody></table>'
    return html


def fmt(text: str) -> str:
    """Convert markdown to HTML for injection inside styled cards."""
    text = re.sub(r'##[A-Z0-9_]+##', '', text)
    text = re.sub(r'^Q\d+\s*$', '', text, flags=re.MULTILINE)
    text = text.strip()

    lines = text.split('\n')
    out   = []
    i     = 0
    while i < len(lines):
        line = lines[i]
        # Detect markdown table: current line starts with | and next is a separator row
        if (line.strip().startswith('|') and
                i + 1 < len(lines) and
                re.match(r'^\|[\s\-:|]+\|', lines[i + 1].strip())):
            table_block = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                table_block.append(lines[i])
                i += 1
            out.append(_render_md_table(table_block))
            continue

        line = line.rstrip()
        line = re.sub(r'^###\s+(.+)', r'<strong style="font-size:14px">\1</strong>', line)
        line = re.sub(r'^##\s+(.+)',  r'<strong style="font-size:15px">\1</strong>', line)
        line = re.sub(r'^#\s+(.+)',   r'<strong style="font-size:16px">\1</strong>', line)
        line = re.sub(r'^[-*•]\s+', '&bull; ', line)
        line = _md_inline(line)
        out.append(line)
        i += 1

    result = '<br>'.join(out)
    result = re.sub(r'(<br>){3,}', '<br><br>', result)
    return result


def plain(text: str) -> str:
    """Strip markdown to clean plain text for email."""
    text = re.sub(r'##[A-Z0-9_]+##', '', text)
    text = re.sub(r'^#{1,3}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*\*(.*?)\*\*\*', r'\1', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'^[-*•]\s+', '• ', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ── URL scraping ──────────────────────────────────────────────────────────────
def scrape_transcript(url: str) -> tuple:
    """Fetch a URL and extract readable text. Returns (text, error_msg)."""
    if not _SCRAPE_AVAILABLE:
        return "", "requests/beautifulsoup4 not installed — run: pip install requests beautifulsoup4"
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        is_pdf = "application/pdf" in content_type or url.lower().split("?")[0].endswith(".pdf")

        if is_pdf:
            try:
                from pypdf import PdfReader
                from io import BytesIO
                reader = PdfReader(BytesIO(resp.content))
                text = "\n".join(p.extract_text() or "" for p in reader.pages)
                text = "\n".join(l.strip() for l in text.splitlines() if l.strip())
            except ImportError:
                return "", "PDF URL detected but pypdf is not installed — run: pip install pypdf"
        else:
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
                tag.decompose()
            lines = [l.strip() for l in soup.get_text(separator="\n").splitlines() if l.strip()]
            text = "\n".join(lines)

        if len(text) < 500:
            return "", "Page returned too little text — it may require login or JavaScript rendering."
        return text, ""
    except requests.HTTPError as e:
        return "", f"HTTP {e.response.status_code} — page may require login or block scrapers."
    except Exception as e:
        return "", str(e)


# ── PDF export ─────────────────────────────────────────────────────────────────
_SECTION_PDF_TITLES = {
    "##FINANCIAL_SUMMARY##":   "Financial Summary",
    "##GUIDANCE##":            "Guidance",
    "##QA_HIGHLIGHTS##":       "Q&A Highlights",
    "##TONE_SENTIMENT##":      "Tone / Sentiment",
    "##INVESTMENT_TAKEAWAY##": "Investment Takeaway",
}

def _pdf_safe(text: str) -> str:
    """Sanitize text to Helvetica-safe characters (printable ASCII + Latin-1)."""
    _REPLACEMENTS = {
        "\u2014": "--", "\u2013": "-", "\u2012": "-",
        "\u2018": "'",  "\u2019": "'",
        "\u201c": '"',  "\u201d": '"',
        "\u2022": "-",  "\u2023": "-", "\u25cf": "-", "\u00b7": "-",
        "\u2192": "->", "\u2190": "<-", "\u2026": "...",
        "\u00a0": " ",  "\u200b": "",  "\ufeff": "",
        "\u2713": "v",  "\u2715": "x", "\u00d7": "x",
    }
    for ch, rep in _REPLACEMENTS.items():
        text = text.replace(ch, rep)
    # Strip anything outside printable ASCII (32-126) or Latin-1 supplement (160-255)
    return "".join(c if (32 <= ord(c) <= 126) or (160 <= ord(c) <= 255) else "?" for c in text)


def generate_pdf(sections: dict, company: str, ts: str, model_label: str) -> bytes:
    if not _PDF_AVAILABLE:
        return b""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, _pdf_safe(f"Earnings Analysis - {company or 'Unknown'}"), ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, _pdf_safe(f"{ts}  |  {model_label.split('(')[0].strip()}"), ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(6)

    for delim, title in _SECTION_PDF_TITLES.items():
        content = _pdf_safe(plain(sections.get(delim, "")).strip())
        if not content:
            continue
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_fill_color(240, 242, 248)
        pdf.cell(0, 8, title, ln=True, fill=True)
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 10)
        import textwrap
        for line in content.splitlines():
            if not line.strip():
                pdf.ln(3)
                continue
            for subline in textwrap.wrap(line, width=90, break_long_words=True, break_on_hyphens=True) or [line[:90]]:
                pdf.set_x(pdf.l_margin)
                try:
                    pdf.multi_cell(pdf.epw, 5, subline)
                except Exception:
                    pass  # skip any line that still can't render
        pdf.ln(5)

    return bytes(pdf.output())


SENTIMENT_COLORS  = {"Bearish": "#ef4444", "Cautious": "#f97316",
                     "Neutral": "#6b7280", "Constructive": "#3b82f6", "Bullish": "#10b981"}
CONFIDENCE_COLORS = {"Low": "#ef4444", "Medium": "#f59e0b", "High": "#10b981"}
CONFIDENCE_PCT    = {"Low": 33, "Medium": 66, "High": 100}


SECTION_TOOLTIPS = {
    "📋 Financial Summary":   "Key metrics reported vs. guidance or consensus mentioned on the call",
    "🔭 Guidance":            "Forward-looking statements, changes from prior periods, notable caveats",
    "💬 Q&A Highlights":      "3–5 most substantive analyst questions and management responses",
    "🎯 Tone / Sentiment":    "Defensiveness, hedging, unusual optimism, or deflection — your judgment",
    "⚡ Investment Takeaway": "One paragraph: if you're briefing a PM in 30 seconds, what's the single most important thing?",
}


def render_section(placeholder, css_class: str, title: str, content: str):
    tip = SECTION_TOOLTIPS.get(title, "")
    h3 = (f'<h3><span class="tip" data-tip="{tip}">{title}</span></h3>'
          if tip else f'<h3>{title}</h3>')
    placeholder.markdown(
        f'<div class="{css_class}">{h3}{fmt(content)}</div>',
        unsafe_allow_html=True,
    )


def render_sentiment(placeholder, tone: str):
    # Skip any formatting chars (**bold**, spaces, brackets) before the value word
    sentiment_match  = re.search(r'SENTIMENT:[^A-Za-z\[]*\[?([A-Za-z]+)',  tone, re.IGNORECASE)
    confidence_match = re.search(r'CONFIDENCE:[^A-Za-z\[]*\[?([A-Za-z]+)', tone, re.IGNORECASE)
    sentiment_val  = sentiment_match.group(1).strip().capitalize()  if sentiment_match  else ""
    confidence_val = confidence_match.group(1).strip().capitalize() if confidence_match else ""
    s_color = SENTIMENT_COLORS.get(sentiment_val, "#6b7280")
    c_color = CONFIDENCE_COLORS.get(confidence_val, "#6b7280")
    c_pct   = CONFIDENCE_PCT.get(confidence_val, 50)
    tone_body = re.sub(r'SENTIMENT:.*', '', tone)
    tone_body = re.sub(r'CONFIDENCE:.*', '', tone_body).strip()
    placeholder.markdown(
        f'<div class="sentiment-card"><h3><span class="tip" data-tip="{SECTION_TOOLTIPS["🎯 Tone / Sentiment"]}">🎯 Tone / Sentiment</span></h3>'
        f'<div style="text-align:center;padding:24px 0 20px">'
        f'<div style="font-size:2.6rem;font-weight:900;letter-spacing:3px;color:{s_color};text-shadow:0 0 24px {s_color}66">{sentiment_val.upper() if sentiment_val else "—"}</div>'
        f'<div style="margin-top:10px;font-size:0.85rem;color:#aaa;letter-spacing:2px;text-transform:uppercase">Management Confidence</div>'
        f'<div style="margin:8px auto 4px;width:180px;height:8px;background:rgba(255,255,255,0.1);border-radius:4px">'
        f'<div style="width:{c_pct}%;height:100%;background:{c_color};border-radius:4px;box-shadow:0 0 8px {c_color}"></div></div>'
        f'<div style="font-size:1rem;font-weight:700;color:{c_color}">{confidence_val or "—"}</div>'
        f'</div>'
        f'<div style="border-top:1px solid rgba(255,255,255,0.08);padding-top:14px">{fmt(tone_body)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_takeaway(placeholder, takeaway: str):
    placeholder.markdown(
        f'<div class="takeaway-card"><h3><span class="tip" data-tip="{SECTION_TOOLTIPS["⚡ Investment Takeaway"]}">⚡ Investment Takeaway</span></h3>' + fmt(takeaway) + '</div>',
        unsafe_allow_html=True,
    )


def _md_label(text: str) -> str:
    """Escape square brackets so Streamlit doesn't parse [TOKEN] as a markdown link."""
    return text.replace('[', '\\[').replace(']', '\\]')


def _clean_label(text: str) -> str:
    """Strip markdown bold/italic markers that can leak into display labels."""
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*',     r'\1', text)
    text = text.replace('**', '').replace('*', '')
    return text.strip()


def render_qa(placeholder, qa_text: str):
    qa_items = parse_qa(qa_text)
    with placeholder.container():
        st.markdown(f'<div class="section-card"><h3><span class="tip" data-tip="{SECTION_TOOLTIPS["💬 Q&A Highlights"]}">💬 Q&A Highlights</span></h3>', unsafe_allow_html=True)
        for i, item in enumerate(qa_items, 1):
            analyst_label   = _clean_label(item['analyst'])   or 'Analyst'
            executive_label = _clean_label(item.get('executive') or '')
            # Escape brackets in expander header — Streamlit renders labels as markdown
            # and [ANALYST_1] without a trailing (url) can break some parsers.
            header_analyst   = _md_label(analyst_label)
            header_executive = _md_label(executive_label)
            header = (f"Q{i} — {header_analyst} → {header_executive}"
                      if executive_label else f"Q{i} — {header_analyst}")
            with st.expander(header):
                if executive_label:
                    st.markdown(
                        f'<div style="font-size:13px;margin-bottom:10px;color:#aaa">'
                        f'<span style="color:#60a5fa">{analyst_label}</span>'
                        f' &nbsp;→&nbsp; '
                        f'<span style="color:#34d399">{executive_label}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                # Render Q/R as HTML via fmt() so [TOKEN] brackets are treated as
                # literal text rather than going through markdown link parsing.
                st.markdown(
                    f'<div style="margin-bottom:8px"><strong>Question:</strong><br>{fmt(item["question"])}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div><strong>Response:</strong><br>{fmt(item["response"])}</div>',
                    unsafe_allow_html=True,
                )
        st.markdown("</div>", unsafe_allow_html=True)


# ── Keyboard shortcut (Cmd/Ctrl+Enter → Run Analysis) ────────────────────────
import streamlit.components.v1 as _components
_components.html("""
<script>
window.parent.document.addEventListener('keydown', function(e) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault();
        const buttons = window.parent.document.querySelectorAll('button');
        for (const btn of buttons) {
            if (btn.innerText.trim().includes('Run Analysis')) {
                btn.click();
                break;
            }
        }
    }
}, true);
</script>
""", height=0)

# ── UI ────────────────────────────────────────────────────────────────────────
st.title("📊 Earnings Transcript Processor")
st.caption("Paste any earnings call transcript → structured analyst output · Cmd+Enter to run")

col_main, col_settings = st.columns([2, 1])

with col_main:
    url_col, btn_col = st.columns([5, 1])
    with url_col:
        transcript_url = st.text_input(
            "Fetch from URL",
            placeholder="https://company.com/ir/transcript.html  (plain HTML only — JS-rendered sites won't work)",
            label_visibility="collapsed",
            key=f"transcript_url_{st.session_state.get('_url_input_key', 0)}",
        )
    with btn_col:
        fetch_btn = st.button("Fetch", disabled=not transcript_url.strip(), use_container_width=True)

    # URL fetch — always takes precedence; resets file uploader on success
    if fetch_btn and transcript_url.strip():
        with st.spinner("Fetching transcript..."):
            fetched, err = scrape_transcript(transcript_url.strip())
        if err:
            st.error(f"Could not fetch: {err}")
        else:
            st.session_state.transcript_input = fetched
            # Bump key to clear the file uploader widget
            st.session_state._file_upload_key = st.session_state.get("_file_upload_key", 0) + 1
            st.session_state._loaded_file = None
            st.rerun()

    # File uploader — only populates text area when a NEW file is dropped
    uploaded_file = st.file_uploader(
        "Upload transcript (.txt, .md, .csv, .pdf)", type=["txt", "md", "csv", "pdf"],
        key=f"transcript_file_{st.session_state.get('_file_upload_key', 0)}",
    )
    if uploaded_file:
        if uploaded_file.name != st.session_state.get("_loaded_file"):
            # New file — read it, populate text area, clear URL field
            if uploaded_file.type == "application/pdf":
                try:
                    from pypdf import PdfReader
                    from io import BytesIO
                    reader = PdfReader(BytesIO(uploaded_file.read()))
                    file_content = "\n".join(p.extract_text() or "" for p in reader.pages)
                except ImportError:
                    st.error("PDF support requires pypdf: `pip install pypdf`")
                    file_content = ""
            else:
                file_content = uploaded_file.read().decode("utf-8", errors="ignore")
            if file_content:
                st.session_state.transcript_input = file_content
                st.session_state._loaded_file = uploaded_file.name
                # Bump URL input key to reset the URL field widget
                st.session_state._url_input_key = st.session_state.get("_url_input_key", 0) + 1
                st.rerun()
    else:
        # File removed — reset tracking so the same file can be re-uploaded
        if st.session_state.get("_loaded_file"):
            st.session_state._loaded_file = None

    transcript_input = st.text_area(
        "Or paste transcript here",
        height=420,
        placeholder="Paste the full earnings call transcript text...",
        key="transcript_input",
    )

    with st.expander("📅 Prior quarter transcript (optional — enables QoQ comparison)"):
        prior_uploaded = st.file_uploader(
            "Upload prior quarter transcript", type=["txt", "md", "csv", "pdf"],
            key="prior_upload",
        )
        if prior_uploaded:
            if prior_uploaded.type == "application/pdf":
                try:
                    from pypdf import PdfReader
                    from io import BytesIO
                    reader = PdfReader(BytesIO(prior_uploaded.read()))
                    st.session_state.prior_text = "\n".join(p.extract_text() or "" for p in reader.pages)
                except ImportError:
                    st.error("PDF support requires pypdf: `pip install pypdf`")
            else:
                st.session_state.prior_text = prior_uploaded.read().decode("utf-8", errors="ignore")
        prior_transcript_input = st.text_area(
            "Or paste prior quarter transcript",
            height=200,
            placeholder="Paste prior quarter transcript here...",
            key="prior_text",
        )

with col_settings:
    st.markdown("### Settings")

    company_name = st.text_input("Company name (optional)", placeholder="e.g. MIDT")

    model_label = st.selectbox("Model", list(MODELS.keys()), index=0)
    selected_model = MODELS[model_label]
    info = MODEL_INFO[model_label]
    fun_animations = st.toggle("Fun animations", value=False)
    if fun_animations:
        inject_theme(info)
    st.markdown(
        f'<div style="background:#f8f9fb;border-radius:6px;padding:10px 14px;margin-bottom:8px;border-left:3px solid {info["color"]}">'
        f'<span style="color:{info["color"]};font-weight:600;font-size:13px">{model_label} &nbsp;·&nbsp; {info["model_name"]}</span><br>'
        f'<span style="color:#555;font-size:12px">{info["quality"]}</span><br>'
        f'<span style="color:#6b7280;font-size:12px">💰 {info["cost"]}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    length = st.select_slider(
        "Response length",
        options=["Concise", "Standard", "Detailed"],
        value="Standard",
    )

    obfuscate = st.checkbox("Obfuscate PII (names, firms, contacts)")

    with st.expander("📊 Consensus Estimates (optional)"):
        st.caption("Paste in sell-side consensus so the Financial Summary can state explicit beats/misses.")
        consensus_revenue = st.text_input("Revenue consensus", placeholder="e.g. $1.52B")
        consensus_eps     = st.text_input("EPS consensus",     placeholder="e.g. $2.97")

    # ── History ───────────────────────────────────────────────────────────────
    history = load_history()
    if history:
        with st.expander(f"📚 History ({len(history)} run{'s' if len(history) != 1 else ''})"):
            for entry in history[:20]:
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(
                        f'<div class="history-card">'
                        f'<strong>{entry["company"]}</strong><br>'
                        f'<span style="color:#6b7280">{entry["timestamp"]} · {entry["model"].split("(")[0].strip()}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with c2:
                    if st.button("Load", key=f"hist_{entry['id']}"):
                        st.session_state.compare_sections = entry["sections"]
                        st.session_state.compare_meta     = (entry["timestamp"], entry["model"], entry["company"])
                        st.rerun()
            if st.button("🗑 Clear history", type="secondary"):
                try:
                    os.remove(HISTORY_FILE)
                except Exception:
                    pass
                st.rerun()

    st.divider()

    # ── Dev / Advanced ────────────────────────────────────────────────────────
    with st.expander("⚙️ Advanced / Dev"):
        st.caption("Fine-tune model parameters")
        temperature = st.slider("Temperature", 0.0, 1.0, 0.3, 0.05,
                                help="Higher = more creative, lower = more deterministic")
        max_tokens_override = st.number_input(
            "Max tokens (overrides length preset)",
            min_value=256, max_value=32000,
            value=LENGTH_SETTINGS[length]["max_tokens"],
            step=256,
        )
        st.caption(f"Length preset default: {LENGTH_SETTINGS[length]['max_tokens']} tokens")

# ── Run ───────────────────────────────────────────────────────────────────────
for key, val in [("running", False), ("stop_requested", False), ("pending_run", False)]:
    if key not in st.session_state:
        st.session_state[key] = val

st.markdown("""
<style>
@keyframes spin { to { transform: rotate(360deg); } }
.inferencing { display:flex; align-items:center; gap:10px; margin-bottom:8px; }
.spinner { width:16px; height:16px; border:2px solid rgba(255,255,255,0.2);
           border-top-color:#fff; border-radius:50%;
           animation:spin 0.7s linear infinite; display:inline-block; }
</style>
""", unsafe_allow_html=True)

if st.session_state.running:
    st.markdown('<div class="inferencing"><div class="spinner"></div>'
                '<span style="color:#aaa;font-size:13px">Inferencing...</span></div>',
                unsafe_allow_html=True)
    if st.button("⏹ Stop Analysis", type="secondary"):
        st.session_state.stop_requested = True
        st.session_state.running = False
        # Persist whatever streamed so far
        partial = st.session_state.get("streaming_raw", "")
        if partial:
            obfuscate_on = st.session_state.get("pending_obfuscate", False)
            if obfuscate_on:
                partial, pii_found_partial, _ = obfuscate_pii(partial)
                st.session_state.last_pii_found = pii_found_partial
            t0_saved = st.session_state.get("streaming_t0", time.time())
            st.session_state.last_raw           = partial
            st.session_state.last_sections      = parse_sections(partial)
            pass  # output_format removed
            st.session_state.last_elapsed       = time.time() - t0_saved
            st.session_state.last_meta     = st.session_state.get("streaming_meta")
            st.session_state.last_stopped  = True
        st.session_state.pop("streaming_raw", None)
        st.session_state.pop("pending_run", None)
        st.rerun()
    run_btn = False
else:
    run_btn = st.button("▶ Run Analysis", type="primary",
                        disabled=not transcript_input.strip())

# When Run is clicked: save settings, flip running=True, rerun so stop button appears
if run_btn and transcript_input.strip():
    transcript = transcript_input.strip()

    if len(transcript) > MAX_TRANSCRIPT_CHARS:
        st.error(
            f"Transcript too long ({len(transcript):,} chars). "
            f"Maximum is {MAX_TRANSCRIPT_CHARS:,} chars (~37k tokens). "
            "Trim the transcript and try again."
        )
        st.stop()
    elif len(transcript) > WARN_TRANSCRIPT_CHARS:
        st.warning(
            f"Large transcript ({len(transcript):,} chars) — analysis may take longer and use more tokens."
        )

    # Clear previous output so stale results don't flash before new ones arrive
    for k in ("last_raw", "last_sections", "last_elapsed", "last_meta", "last_stopped", "last_pii_found", "last_email", "generate_email", "last_qoq", "pending_qoq"):
        st.session_state.pop(k, None)

    st.session_state.pending_run           = True
    st.session_state.pending_transcript    = transcript
    st.session_state.pending_obfuscate     = obfuscate
    st.session_state.pending_model        = selected_model
    st.session_state.pending_model_label  = model_label
    st.session_state.pending_length       = length
    st.session_state.pending_temperature  = temperature
    st.session_state.pending_max_tokens      = int(max_tokens_override)
    st.session_state.pending_company         = company_name
    consensus_parts = []
    if consensus_revenue.strip():
        consensus_parts.append(f"Revenue: {consensus_revenue.strip()}")
    if consensus_eps.strip():
        consensus_parts.append(f"EPS: {consensus_eps.strip()}")
    st.session_state.pending_consensus       = "\n".join(consensus_parts)
    st.session_state.pending_prior_transcript = prior_transcript_input.strip()
    st.session_state.running = True
    st.session_state.stop_requested = False
    st.rerun()

if st.session_state.get("pending_run") and st.session_state.running:
    st.session_state.pending_run = False

    transcript    = st.session_state.pending_transcript
    obfuscate_was = st.session_state.pending_obfuscate
    selected_model   = st.session_state.pending_model
    model_label      = st.session_state.pending_model_label
    length           = st.session_state.pending_length
    temperature      = st.session_state.pending_temperature
    max_tokens_override = st.session_state.pending_max_tokens
    company_name      = st.session_state.pending_company
    consensus_str     = st.session_state.get("pending_consensus", "")
    prior_transcript  = st.session_state.get("pending_prior_transcript", "")

    # PII map will be shown in the persistent output block after streaming

    SECTION_LABELS = {
        "##FINANCIAL_SUMMARY##":   ("section-card",   "📋 Financial Summary"),
        "##GUIDANCE##":            ("section-card",   "🔭 Guidance"),
        "##QA_HIGHLIGHTS##":       ("section-card",   "💬 Q&A Highlights"),
        "##TONE_SENTIMENT##":      ("sentiment-card", "🎯 Tone / Sentiment"),
        "##INVESTMENT_TAKEAWAY##": ("takeaway-card",  "⚡ Investment Takeaway"),
    }

    t0 = time.time()
    st.session_state.streaming_t0   = t0
    st.session_state.streaming_meta = (datetime.now().strftime("%Y-%m-%d %H:%M"), model_label, company_name)
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        st.markdown(
            f'<div class="meta-bar">Processed: {ts} &nbsp;|&nbsp; '
            f'Model: {model_label.split("(")[0].strip()} &nbsp;|&nbsp; '
            f'Company: {company_name or "—"}</div>',
            unsafe_allow_html=True,
        )

        # Pre-render all section skeletons so the layout is visible immediately
        placeholders = {}
        for delim in SECTION_DELIMITERS:
            css_class, title = SECTION_LABELS[delim]
            placeholders[delim] = st.empty()
            placeholders[delim].markdown(
                f'<div class="{css_class}" style="opacity:0.35"><h3>{title}</h3>'
                f'<span style="color:#aaa">Waiting...</span></div>',
                unsafe_allow_html=True,
            )

        section_raw  = {d: "" for d in SECTION_DELIMITERS}
        section_done = {d: False for d in SECTION_DELIMITERS}
        # Each section runs independently — full budget per section
        section_max = int(max_tokens_override)

        q = _queue.Queue()
        for i, delim in enumerate(SECTION_DELIMITERS):
            # Stagger starts by 200 ms so all 5 calls don't hit the API simultaneously.
            # This avoids rate-limit queuing that leaves sections stuck on "Waiting...".
            if i > 0:
                time.sleep(0.2)
            threading.Thread(
                target=_stream_section,
                args=(delim, transcript, length, selected_model, section_max, temperature, q),
                kwargs={"consensus": consensus_str},
                daemon=True,
            ).start()

        section_errors = {}   # section_key -> error string for failed sections

        while not all(section_done.values()):
            if st.session_state.get("stop_requested"):
                st.session_state.running = False
                st.rerun()

            # Timeout check — abandon any section that has been running too long
            now = time.time()
            for key in SECTION_DELIMITERS:
                if not section_done[key] and (now - t0) > _SECTION_TIMEOUT:
                    section_done[key]   = True
                    section_errors[key] = f"Timed out after {_SECTION_TIMEOUT}s"
                    css_class, title = SECTION_LABELS[key]
                    placeholders[key].markdown(
                        f'<div class="{css_class}" style="opacity:0.6"><h3>{title}</h3>'
                        f'<span style="color:#f97316">⚠ Section timed out — try again</span></div>',
                        unsafe_allow_html=True,
                    )

            try:
                section_key, chunk, done, err = q.get(timeout=0.05)
            except _queue.Empty:
                continue

            # Ignore signals for sections already marked done (e.g. timed-out)
            if section_done[section_key]:
                continue

            if done:
                section_done[section_key] = True
                css_class, title = SECTION_LABELS[section_key]
                if err:
                    # Graceful partial failure — render error card, others continue
                    section_errors[section_key] = err
                    placeholders[section_key].markdown(
                        f'<div class="{css_class}" style="opacity:0.6"><h3>{title}</h3>'
                        f'<span style="color:#ef4444">⚠ Failed after {_MAX_RETRIES} attempts: {err}</span></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    content = section_raw[section_key]
                    try:
                        if section_key == "##TONE_SENTIMENT##":
                            render_sentiment(placeholders[section_key], content)
                        elif section_key == "##INVESTMENT_TAKEAWAY##":
                            render_takeaway(placeholders[section_key], content)
                        elif section_key == "##QA_HIGHLIGHTS##":
                            render_qa(placeholders[section_key], content)
                        else:
                            render_section(placeholders[section_key], css_class, title, content)
                    except Exception as render_err:
                        placeholders[section_key].markdown(
                            f'<div class="{css_class}" style="opacity:0.6"><h3>{title}</h3>'
                            f'<span style="color:#f97316">⚠ Render error: {render_err}</span></div>',
                            unsafe_allow_html=True,
                        )
            else:
                section_raw[section_key] += chunk
                css_class, title = SECTION_LABELS[section_key]
                placeholders[section_key].markdown(
                    f'<div class="{css_class}"><h3>{title}</h3>' +
                    section_raw[section_key].strip().replace("\n", "<br>") + "</div>",
                    unsafe_allow_html=True,
                )

            # Rebuild combined raw in delimiter format for PII / email / stop-handler
            raw = "\n".join(f"{d}\n{section_raw[d]}" for d in SECTION_DELIMITERS)
            st.session_state.streaming_raw = raw
        # Apply PII obfuscation directly to model output
        if obfuscate_was:
            raw, pii_found_output, _ = obfuscate_pii(raw)
            st.session_state.last_pii_found = pii_found_output
        else:
            st.session_state.last_pii_found = []
        elapsed = time.time() - t0

        # Re-render successful sections with full formatting; leave error cards untouched
        sections = parse_sections(raw)
        if "##FINANCIAL_SUMMARY##"   not in section_errors:
            render_section(placeholders["##FINANCIAL_SUMMARY##"], "section-card", "📋 Financial Summary", sections.get("##FINANCIAL_SUMMARY##", ""))
        if "##GUIDANCE##"            not in section_errors:
            render_section(placeholders["##GUIDANCE##"],          "section-card", "🔭 Guidance",           sections.get("##GUIDANCE##", ""))
        if "##QA_HIGHLIGHTS##"       not in section_errors:
            render_qa(placeholders["##QA_HIGHLIGHTS##"],                                                    sections.get("##QA_HIGHLIGHTS##", ""))
        if "##TONE_SENTIMENT##"      not in section_errors:
            render_sentiment(placeholders["##TONE_SENTIMENT##"],                                            sections.get("##TONE_SENTIMENT##", ""))
        if "##INVESTMENT_TAKEAWAY##" not in section_errors:
            render_takeaway(placeholders["##INVESTMENT_TAKEAWAY##"],                                        sections.get("##INVESTMENT_TAKEAWAY##", ""))

        st.session_state.running             = False
        st.session_state.last_raw            = raw
        st.session_state.last_elapsed        = elapsed
        st.session_state.last_sections       = sections
        st.session_state.last_meta           = (ts, model_label, company_name)
        st.session_state.last_stopped        = False

        # Save to history
        save_run_to_history(company_name, ts, model_label, sections)

        # Queue QoQ comparison if prior transcript was provided
        if prior_transcript:
            st.session_state.pending_qoq          = True
            st.session_state.qoq_prior_transcript = prior_transcript
            st.session_state.qoq_sections         = sections
            st.session_state.qoq_model            = selected_model
            st.session_state.qoq_max_tokens       = min(int(max_tokens_override), 1024)
            st.session_state.qoq_temperature      = temperature

        st.rerun()
    except anthropic.APIError as e:
        st.session_state.running = False
        st.error(f"Anthropic API error: {e}")
        st.rerun()
    except Exception as e:
        st.session_state.running = False
        st.error(f"Unexpected error: {e}")
        st.rerun()

if not st.session_state.get("running") and st.session_state.get("last_sections"):
    sections  = st.session_state.last_sections
    elapsed   = st.session_state.get("last_elapsed", 0)
    raw       = st.session_state.get("last_raw", "")
    stopped   = st.session_state.get("last_stopped", False)
    meta      = st.session_state.get("last_meta")

    if meta:
        ts_saved, ml_saved, co_saved = meta
        st.markdown(
            f'<div class="meta-bar">Processed: {ts_saved} &nbsp;|&nbsp; '
            f'Model: {ml_saved.split("(")[0].strip()} &nbsp;|&nbsp; '
            f'Company: {co_saved or "—"}</div>',
            unsafe_allow_html=True,
        )

    render_section(st.empty(), "section-card",   "📋 Financial Summary",   sections.get("##FINANCIAL_SUMMARY##", ""))
    render_section(st.empty(), "section-card",   "🔭 Guidance",             sections.get("##GUIDANCE##", ""))
    render_qa(     st.empty(),                                               sections.get("##QA_HIGHLIGHTS##", ""))
    render_sentiment(st.empty(),                                             sections.get("##TONE_SENTIMENT##", ""))
    render_takeaway( st.empty(),                                             sections.get("##INVESTMENT_TAKEAWAY##", ""))

    if stopped:
        st.warning(f"Analysis stopped after {elapsed:.1f}s — partial results shown above.")
    else:
        st.success(f"Analysis complete in {elapsed:.1f}s")

    # PII redaction map
    pii_found = st.session_state.get("last_pii_found", [])
    if pii_found:
        TYPE_COLORS = {
            "EXECUTIVE": ("#7c3aed", "#ede9fe"),
            "ANALYST":   ("#0369a1", "#e0f2fe"),
            "PHONE":     ("#b45309", "#fef3c7"),
            "EMAIL":     ("#0f766e", "#ccfbf1"),
        }
        with st.expander(f"🔒 PII Redaction Map — {len(pii_found)} item(s) redacted from output"):
            rows = ""
            for item in pii_found:
                label = item['token'].rsplit('_', 1)[0]
                accent, bg = TYPE_COLORS.get(label, ("#374151", "#f3f4f6"))
                rows += (
                    f'<div style="display:grid;grid-template-columns:160px 20px 1fr;'
                    f'align-items:center;gap:10px;padding:9px 14px;margin-bottom:6px;'
                    f'background:{bg};border-radius:6px;border-left:3px solid {accent}">'
                    f'<span style="font-family:monospace;font-weight:700;font-size:13px;color:{accent}">[{item["token"]}]</span>'
                    f'<span style="color:#888;font-size:13px;text-align:center">→</span>'
                    f'<span style="color:#111;font-size:13px">{item["value"]}</span>'
                    f'</div>'
                )
            st.markdown(rows, unsafe_allow_html=True)

    if raw:
        st.divider()
        col_txt, col_pdf, col_email = st.columns([1, 1, 1])
        fname_base = f"transcript_analysis_{datetime.now().strftime('%Y%m%d_%H%M')}"
        with col_txt:
            st.download_button(
                label="⬇ Download (.txt)",
                data=raw,
                file_name=f"{fname_base}.txt",
                mime="text/plain",
            )
        with col_pdf:
            if _PDF_AVAILABLE:
                pdf_meta = st.session_state.get("last_meta", ("", "", ""))
                pdf_bytes = generate_pdf(sections, pdf_meta[2], pdf_meta[0], pdf_meta[1])
                st.download_button(
                    label="⬇ Download (.pdf)",
                    data=pdf_bytes,
                    file_name=f"{fname_base}.pdf",
                    mime="application/pdf",
                )
            else:
                st.caption("PDF: `pip install fpdf2`")
        with col_email:
            if st.button("✉️ Generate Email Draft", type="secondary"):
                st.session_state.generate_email = True

    # ── Email generation ──────────────────────────────────────────────────────
    if st.session_state.get("generate_email") and st.session_state.get("last_sections"):
        st.session_state.generate_email = False
        tone      = sections.get("##TONE_SENTIMENT##", "")
        sent_match = re.search(r'SENTIMENT:\s*\[?(\w+)\]?', tone, re.IGNORECASE)
        conf_match = re.search(r'CONFIDENCE:\s*\[?(\w+)\]?', tone, re.IGNORECASE)
        sentiment_label  = sent_match.group(1) if sent_match else ""
        confidence_label = conf_match.group(1) if conf_match else ""
        tone_body = plain(re.sub(r'(SENTIMENT|CONFIDENCE):.*', '', tone))

        co = (meta[2] if meta else "") or "the company"

        body_lines = [
            plain(sections.get("##INVESTMENT_TAKEAWAY##", "")),
            "",
            "─── Financials " + "─" * 33,
            "",
            plain(sections.get("##FINANCIAL_SUMMARY##", "")),
            "",
            "─── Guidance " + "─" * 35,
            "",
            plain(sections.get("##GUIDANCE##", "")),
            "",
            "─── Tone " + "─" * 39,
            "",
            tone_body,
        ]
        if sentiment_label:
            body_lines += ["", f"Sentiment: {sentiment_label}" + (f"   |   Confidence: {confidence_label}" if confidence_label else "")]
        body_lines += ["", "Best,", "Research Team"]

        st.session_state.email_to      = ""
        st.session_state.email_from    = "Research Team"
        st.session_state.email_subject = f"Earnings Call Summary — {co}"
        st.session_state.email_body    = "\n".join(body_lines)
        st.session_state.last_email    = True   # flag to show compose UI

    if st.session_state.get("last_email") and st.session_state.get("last_sections"):
        st.markdown('<div class="email-card">', unsafe_allow_html=True)
        st.markdown("### ✉️ Email Draft")

        hcol1, hcol2 = st.columns([1, 1])
        with hcol1:
            st.text_input("To", key="email_to", placeholder="portfolio.manager@fund.com")
        with hcol2:
            st.text_input("From", key="email_from")
        st.text_input("Subject", key="email_subject")
        body = st.text_area("Body", key="email_body", height=420)

        full_email = (
            f"To: {st.session_state.get('email_to', '')}\n"
            f"From: {st.session_state.get('email_from', '')}\n"
            f"Subject: {st.session_state.get('email_subject', '')}\n\n"
            f"{body}"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        st.download_button(
            label="⬇ Download email",
            data=full_email,
            file_name=f"email_draft_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain",
            key="email_download",
        )

# ── QoQ comparison (streams after main analysis if prior transcript provided) ─
if st.session_state.get("pending_qoq") and not st.session_state.get("running"):
    st.session_state.pending_qoq = False
    sections_for_qoq  = st.session_state.get("qoq_sections", {})
    prior_t           = st.session_state.get("qoq_prior_transcript", "")
    qoq_model         = st.session_state.get("qoq_model", "claude-sonnet-4-6")
    qoq_max_tokens    = st.session_state.get("qoq_max_tokens", 1024)
    qoq_temperature   = st.session_state.get("qoq_temperature", 0.3)

    st.divider()
    qoq_placeholder = st.empty()
    qoq_placeholder.markdown(
        '<div class="qoq-card" style="opacity:0.4"><h3>📊 Quarter-over-Quarter Comparison</h3>'
        '<span style="color:#aaa">Generating comparison...</span></div>',
        unsafe_allow_html=True,
    )
    qoq_raw = ""
    try:
        for chunk in run_qoq_comparison_streaming(
            cur_guidance=sections_for_qoq.get("##GUIDANCE##", ""),
            cur_tone=sections_for_qoq.get("##TONE_SENTIMENT##", ""),
            prior_transcript=prior_t,
            model=qoq_model,
            max_tokens=qoq_max_tokens,
            temperature=qoq_temperature,
        ):
            qoq_raw += chunk
            qoq_placeholder.markdown(
                '<div class="qoq-card"><h3>📊 Quarter-over-Quarter Comparison</h3>' +
                qoq_raw.strip().replace("\n", "<br>") + "</div>",
                unsafe_allow_html=True,
            )
        st.session_state.last_qoq = qoq_raw
        qoq_placeholder.markdown(
            '<div class="qoq-card"><h3>📊 Quarter-over-Quarter Comparison</h3>' +
            fmt(qoq_raw) + "</div>",
            unsafe_allow_html=True,
        )
    except Exception as e:
        qoq_placeholder.markdown(
            f'<div class="qoq-card"><h3>📊 Quarter-over-Quarter Comparison</h3>'
            f'<span style="color:#ef4444">⚠ Comparison failed: {e}</span></div>',
            unsafe_allow_html=True,
        )

elif st.session_state.get("last_qoq") and not st.session_state.get("running"):
    st.divider()
    st.markdown(
        '<div class="qoq-card"><h3>📊 Quarter-over-Quarter Comparison</h3>' +
        fmt(st.session_state.last_qoq) + "</div>",
        unsafe_allow_html=True,
    )

# ── History comparison (loaded from sidebar) ──────────────────────────────────
if st.session_state.get("compare_sections") and not st.session_state.get("running"):
    compare_sections = st.session_state.compare_sections
    compare_meta     = st.session_state.get("compare_meta", ("", "", ""))
    ts_c, model_c, co_c = compare_meta

    st.divider()
    st.markdown(
        f'<div style="font-size:13px;color:#a78bfa;font-weight:600;margin-bottom:12px;letter-spacing:1px">'
        f'LOADED FROM HISTORY — {co_c} &nbsp;·&nbsp; {ts_c}'
        f'</div>',
        unsafe_allow_html=True,
    )
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Current run**")
        cur = st.session_state.get("last_sections", {})
        render_section(st.empty(), "section-card", "🔭 Guidance",         cur.get("##GUIDANCE##", "—"))
        render_sentiment(st.empty(),                                        cur.get("##TONE_SENTIMENT##", ""))
        render_takeaway(st.empty(),                                         cur.get("##INVESTMENT_TAKEAWAY##", ""))
    with col_b:
        st.markdown(f"**{co_c} ({ts_c})**")
        render_section(st.empty(), "section-card", "🔭 Guidance",         compare_sections.get("##GUIDANCE##", "—"))
        render_sentiment(st.empty(),                                        compare_sections.get("##TONE_SENTIMENT##", ""))
        render_takeaway(st.empty(),                                         compare_sections.get("##INVESTMENT_TAKEAWAY##", ""))

    if st.button("✕ Clear comparison", type="secondary"):
        st.session_state.pop("compare_sections", None)
        st.session_state.pop("compare_meta", None)
        st.rerun()

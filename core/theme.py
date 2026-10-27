"""
App-wide look: one CSS block + small HTML components (cards, chips, headers).
Mobile-first: 48px touch targets, 16px inputs (no iOS zoom), compact padding on phones.
If Streamlit changes its internal markup the CSS simply stops applying — the app still works.
"""
from html import escape

import streamlit as st

BRAND = "#0f766e"

CSS = f"""
<style>
/* Translucent colours so cards look right in both Streamlit light and dark themes */
:root {{
  --brand: {BRAND}; --brand-soft: rgba(15,118,110,.13); --ink: inherit; --muted: #808a96;
  --line: rgba(128,128,128,.28); --card: rgba(128,128,128,.06);
  --ok: #16a34a; --ok-soft: rgba(22,163,74,.14); --warn: #d97706; --warn-soft: rgba(217,119,6,.14);
  --bad: #dc2626; --bad-soft: rgba(220,38,38,.13);
}}

/* Layout */
[data-testid="stMainBlockContainer"], .block-container {{ padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px; }}
#MainMenu, footer, [data-testid="stDecoration"] {{ visibility: hidden; height: 0; }}
h1, h2, h3 {{ letter-spacing: -0.01em; }}
[data-testid="stHeading"] h2 {{ font-size: 1.45rem; }}
[data-testid="stHeading"] h3 {{ font-size: 1.1rem; margin-top: .6rem; }}

/* Touch-friendly controls */
.stButton > button, [data-testid="stFormSubmitButton"] > button, [data-testid="stDownloadButton"] > button {{
  min-height: 48px; border-radius: 12px; font-weight: 600;
}}
[data-testid="stNumberInput"] input, [data-testid="stTextInput"] input, [data-testid="stDateInput"] input,
[data-testid="stTextArea"] textarea {{ font-size: 16px !important; min-height: 46px; border-radius: 10px; }}
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {{ min-height: 46px; border-radius: 10px; font-size: 16px; }}

/* Primary buttons in brand colour (works even without .streamlit/config.toml) */
button[kind^="primary"], [data-testid^="stBaseButton-primary"], [data-testid^="baseButton-primary"] {{
  background-color: var(--brand) !important; border-color: var(--brand) !important; color: #fff !important;
}}
button[kind^="primary"]:hover, [data-testid^="stBaseButton-primary"]:hover {{ filter: brightness(1.08); }}
button[kind^="primary"]:disabled, [data-testid^="stBaseButton-primary"]:disabled {{ opacity: .45; }}

/* Native metrics look like cards */
[data-testid="stMetric"] {{
  background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 12px 14px;
}}
[data-testid="stMetricValue"] {{ font-size: 1.35rem; font-weight: 700; }}
[data-testid="stMetricLabel"] p {{ color: var(--muted); font-size: .85rem; }}

/* Bordered containers */
[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 14px; }}
[data-testid="stExpander"] details {{ border-radius: 12px; }}

/* Our components */
.pp-hero {{ background: linear-gradient(135deg, var(--brand), #115e59); color: #fff; border-radius: 16px;
           padding: 16px 18px; margin: 0 0 14px; }}
.pp-hero .t {{ font-size: 1.25rem; font-weight: 700; margin: 0; }}
.pp-hero .s {{ opacity: .9; font-size: .9rem; margin-top: 2px; }}
.pp-hero .r {{ float: right; text-align: right; }}
.pp-card {{ background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 12px 14px; margin: 6px 0; }}
.pp-card .lbl {{ color: var(--muted); font-size: .8rem; text-transform: uppercase; letter-spacing: .04em; }}
.pp-card .val {{ font-size: 1.35rem; font-weight: 700; color: var(--ink); }}
.pp-card .sub {{ color: var(--muted); font-size: .85rem; }}
.pp-card.ok {{ background: var(--ok-soft); border-color: transparent; }}
.pp-card.warn {{ background: var(--warn-soft); border-color: transparent; }}
.pp-card.bad {{ background: var(--bad-soft); border-color: transparent; }}
.pp-card.brand {{ background: var(--brand-soft); border-color: transparent; }}
.pp-row {{ display: flex; justify-content: space-between; gap: 8px; align-items: baseline; }}
.pp-row + .pp-row {{ margin-top: 4px; }}
.pp-chip {{ display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: .78rem; font-weight: 600;
           background: var(--brand-soft); color: var(--brand); white-space: nowrap; }}
.pp-chip.ok {{ background: var(--ok-soft); color: var(--ok); }}
.pp-chip.warn {{ background: var(--warn-soft); color: var(--warn); }}
.pp-chip.bad {{ background: var(--bad-soft); color: var(--bad); }}
.pp-hero .pp-chip {{ background: rgba(255,255,255,.18); color: #fff; }}
.pp-steps {{ display: flex; gap: 6px; margin: 4px 0 12px; }}
.pp-steps div {{ flex: 1; text-align: center; font-size: .78rem; font-weight: 600; padding: 8px 4px; border-radius: 10px;
                background: var(--card); border: 1px solid var(--line); color: var(--muted); }}
.pp-steps div.done {{ background: var(--ok-soft); color: var(--ok); border-color: transparent; }}
.pp-steps div.now {{ background: var(--brand); color: #fff; border-color: transparent; }}
.pp-noz {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; }}
.pp-noz .n {{ font-weight: 700; font-size: 1.05rem; color: var(--ink); }}
.pp-noz .f {{ color: var(--muted); font-size: .85rem; }}
.pp-big {{ font-size: 1.6rem; font-weight: 800; color: var(--ink); }}
.pp-muted {{ color: var(--muted); font-size: .85rem; }}

/* Phones */
@media (max-width: 640px) {{
  [data-testid="stMainBlockContainer"], .block-container {{ padding-left: .8rem; padding-right: .8rem; padding-top: .6rem; }}
  [data-testid="stHeading"] h2 {{ font-size: 1.25rem; }}
  [data-testid="stMetricValue"] {{ font-size: 1.15rem; }}
  .pp-hero {{ padding: 14px; }}
  .pp-big {{ font-size: 1.4rem; }}
}}
</style>
"""


def apply():
    st.markdown(CSS, unsafe_allow_html=True)


def _h(html: str):
    st.markdown(html, unsafe_allow_html=True)


def e(v) -> str:
    return escape(str(v if v is not None else ""))


def hero(title: str, subtitle: str = "", right: str = ""):
    """Coloured page header. right = small HTML (e.g. a chip)."""
    _h(f'<div class="pp-hero"><div class="r">{right}</div><p class="t">{e(title)}</p>'
       f'<div class="s">{e(subtitle)}</div></div>')


def chip(text: str, tone: str = "") -> str:
    return f'<span class="pp-chip {tone}">{e(text)}</span>'


def card(label: str, value: str, sub: str = "", tone: str = ""):
    _h(f'<div class="pp-card {tone}"><div class="lbl">{e(label)}</div><div class="val">{e(value)}</div>'
       + (f'<div class="sub">{e(sub)}</div>' if sub else "") + "</div>")


def rows_card(pairs, tone: str = "", bold_last: bool = False):
    """Card with label → value lines."""
    lines = []
    for i, (k, v) in enumerate(pairs):
        strong = bold_last and i == len(pairs) - 1
        lines.append(f'<div class="pp-row"><span class="{"" if strong else "pp-muted"}">{e(k)}</span>'
                     f'<span style="font-weight:{800 if strong else 600}">{e(v)}</span></div>')
    _h(f'<div class="pp-card {tone}">{"".join(lines)}</div>')


def steps(labels, current: int):
    """Progress: steps before `current` are done, `current` is active (0-based)."""
    parts = []
    for i, lbl in enumerate(labels):
        cls = "done" if i < current else "now" if i == current else ""
        mark = "✓ " if i < current else f"{i + 1}. "
        parts.append(f'<div class="{cls}">{mark}{e(lbl)}</div>')
    _h(f'<div class="pp-steps">{"".join(parts)}</div>')


def nozzle_head(name: str, sub: str, right_html: str = ""):
    _h(f'<div class="pp-noz"><div><div class="n">{e(name)}</div><div class="f">{e(sub)}</div></div>'
       f'<div>{right_html}</div></div>')


def big(value: str, caption: str = ""):
    _h(f'<div class="pp-big">{e(value)}</div>' + (f'<div class="pp-muted">{e(caption)}</div>' if caption else ""))


STATUS_TONE = {"pending": "warn", "hold": "warn", "reopened": "bad", "approved": "ok", "rejected": "bad",
               "cancelled": "", "reversed": "bad", "deleted": "bad"}

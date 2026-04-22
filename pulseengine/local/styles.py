"""
styles.py — CSS theming for the PulseEngine dashboard.

Retro Financial Broadsheet palette.  Call load_css() once at the top of
dashboard.py, immediately after st.set_page_config().
"""

import streamlit as st


def load_css() -> None:
    """Inject the full Retro Financial Broadsheet stylesheet into Streamlit."""
    st.markdown("""
<style>

/* ── Google Fonts ─────────────────────────────────────────────────────────── */
/* Lora: screen-optimised serif, heavier strokes — readable on dark bg        */
/* Playfair Display: display headings only                                     */
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;1,600&family=Lora:ital,wght@0,400;0,500;0,600;1,400;1,500&display=swap');

/* ── Design tokens ────────────────────────────────────────────────────────── */
:root {
  --bg-main:      #0d0c0a;
  --bg-card:      #141210;
  --bg-card-alt:  #111009;
  --bg-sidebar:   #0a0908;
  --bg-input:     #1c1a16;

  --border:       #2c2820;
  --border-mid:   #3d3630;
  --border-rule:  #524840;

  --gold:         #d4b06a;      /* slightly brighter for dark bg contrast     */
  --gold-dim:     #9a8050;
  --gold-faint:   #3a3020;

  /* Text — higher contrast than before for readability */
  --text-primary:   #f0e6cc;   /* warm ivory, clearly legible                 */
  --text-secondary: #c0aa88;   /* medium warm — body copy                     */
  --text-muted:     #7a6e58;   /* captions / ghost text                       */

  --green:      #4a7a52;
  --green-text: #8acc96;       /* bumped up for contrast                      */
  --green-bg:   #0b1c0e;

  --red:      #7a3a3a;
  --red-text: #d09090;         /* bumped up for contrast                      */
  --red-bg:   #180c0c;

  --amber:      #a07840;
  --amber-text: #e0b878;       /* bumped up for contrast                      */
  --amber-bg:   #1a1308;

  --font-body:    'Lora','Georgia','Times New Roman',serif;
  --font-display: 'Playfair Display','Georgia','Times New Roman',serif;
}

/* ── Global reset ─────────────────────────────────────────────────────────── */
html, body, [class*="css"], .stApp, .main {
  background-color: var(--bg-main) !important;
  color: var(--text-primary) !important;
  font-family: var(--font-body) !important;
  font-size: 16px;
  line-height: 1.75;
  -webkit-font-smoothing: antialiased;
}

/* ── Headings ─────────────────────────────────────────────────────────────── */
h1, h2, h3, h4, h5, h6,
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
  font-family: var(--font-display) !important;
  color: var(--text-primary) !important;
  font-weight: 700;
}
.stMarkdown h1 {
  font-size: 2.2rem !important;
  font-weight: 700 !important;
  color: var(--gold) !important;
  border-bottom: 1px solid var(--border-rule);
  padding-bottom: 10px;
  margin-bottom: 2px !important;
}
.stMarkdown h2 {
  font-size: 1.2rem !important;
  font-weight: 600 !important;
  color: var(--text-primary) !important;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border-bottom: 1px solid var(--border);
  padding-bottom: 6px;
  margin-top: 8px !important;
}
.stMarkdown h3 {
  font-size: 1.0rem !important;
  font-weight: 600 !important;
  color: var(--gold-dim) !important;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

/* ── Caption ──────────────────────────────────────────────────────────────── */
.stCaption, [data-testid="stCaptionContainer"] p {
  color: var(--text-muted) !important;
  font-family: var(--font-body) !important;
  font-size: 0.82rem !important;
  font-style: italic;
}

/* ── HR ───────────────────────────────────────────────────────────────────── */
hr {
  border: none !important;
  border-top: 1px solid var(--border-rule) !important;
  margin: 20px 0 !important;
  opacity: 0.6;
}

/* ── Sidebar ──────────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div {
  background-color: var(--bg-sidebar) !important;
  border-right: 1px solid var(--border-mid) !important;
}
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] .stCaption {
  color: var(--text-secondary) !important;
  font-family: var(--font-body) !important;
  font-size: 0.88rem !important;
}
section[data-testid="stSidebar"] strong {
  color: var(--gold-dim) !important;
  font-weight: 600;
  letter-spacing: 0.05em;
  font-size: 0.80rem;
  text-transform: uppercase;
}

/* ── Metric cards ─────────────────────────────────────────────────────────── */
div[data-testid="stMetric"] {
  background: linear-gradient(160deg, #181510 0%, #111009 100%) !important;
  border: 1px solid var(--border-mid) !important;
  border-top: 2px solid var(--gold-faint) !important;
  border-radius: 4px !important;
  padding: 18px 22px 14px !important;
  box-shadow: 0 2px 8px rgba(0,0,0,0.4) !important;
  position: relative;
}
div[data-testid="stMetric"]::before {
  content: '';
  position: absolute;
  top: 0; left: 16px; right: 16px; height: 1px;
  background: linear-gradient(90deg, transparent, var(--gold-dim), transparent);
  opacity: 0.35;
}
div[data-testid="stMetric"] label {
  color: var(--text-muted) !important;
  font-family: var(--font-body) !important;
  font-size: 0.74rem !important;
  font-weight: 500 !important;
  letter-spacing: 0.12em !important;
  text-transform: uppercase !important;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
  color: var(--text-primary) !important;
  font-family: var(--font-display) !important;
  font-size: 1.6rem !important;
  font-weight: 700 !important;
}
div[data-testid="stMetric"] [data-testid="stMetricDelta"] svg { display: none; }
div[data-testid="stMetric"] [data-testid="stMetricDelta"] {
  font-family: var(--font-body) !important;
  font-size: 0.83rem !important;
  font-weight: 500 !important;
}

/* ── Signal card ─────────────────────────────────────────────────────────── */
.signal-card {
  padding: 22px 28px 18px;
  border-radius: 4px;
  margin-bottom: 4px;
  border-left: 3px solid;
  box-shadow: 0 2px 14px rgba(0,0,0,0.45);
}
.signal-label-text {
  font-family: var(--font-display) !important;
  font-size: 1.65rem;
  font-weight: 700;
}
.signal-score-text {
  font-family: var(--font-body);
  font-size: 0.90rem;
  font-weight: 400;
  font-style: italic;
  opacity: 0.75;
  margin-top: 5px;
}
.signal-strong-bull { background: linear-gradient(135deg,#0d2010,#0a1a0c); border-color: var(--green);   color: var(--green-text); }
.signal-bull        { background: linear-gradient(135deg,#0c1e0e,#091509); border-color: #3d6a44;        color: #7ab880; }
.signal-slight-bull { background: linear-gradient(135deg,#0c1a0e,#0a130c); border-color: #305038;        color: #9ac4a0; }
.signal-neutral     { background: linear-gradient(135deg,#181510,#121009); border-color: var(--gold-dim); color: var(--gold); }
.signal-slight-bear { background: linear-gradient(135deg,#1e1208,#170d06); border-color: #806030;        color: var(--amber-text); }
.signal-bear        { background: linear-gradient(135deg,#1e0e0e,#160909); border-color: var(--red);     color: var(--red-text); }
.signal-strong-bear { background: linear-gradient(135deg,#220e0e,#180808); border-color: #9a4040;        color: #d09090; }

/* ── Confidence badge ─────────────────────────────────────────────────────── */
.confidence-badge {
  display: inline-block;
  padding: 3px 11px;
  border-radius: 2px;
  font-family: var(--font-body);
  font-size: 0.70rem;
  font-weight: 600;
  font-style: normal;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  margin-left: 14px;
  vertical-align: middle;
  border: 1px solid;
}
.conf-high   { color: var(--green-text); border-color: var(--green); background: var(--green-bg); }
.conf-medium { color: var(--amber-text); border-color: var(--amber); background: var(--amber-bg); }
.conf-low    { color: var(--red-text);   border-color: var(--red);   background: var(--red-bg);   }

/* ── Why-it-matters box ───────────────────────────────────────────────────── */
.why-box {
  background: var(--bg-card-alt);
  border: 1px solid var(--border-mid);
  border-left: 3px solid var(--gold-dim);
  border-radius: 0 4px 4px 0;
  padding: 16px 22px;
  margin: 12px 0 14px;
  font-family: var(--font-body);
  font-size: 1.0rem;
  font-weight: 400;
  color: var(--text-secondary);
  line-height: 1.8;
}
.why-label {
  font-family: var(--font-body);
  font-size: 0.70rem;
  font-weight: 600;
  font-style: normal;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--gold-dim);
  margin-bottom: 8px;
}

/* ── Primary driver box ───────────────────────────────────────────────────── */
.driver-box {
  background: var(--green-bg);
  border-left: 3px solid var(--green);
  border-radius: 0 4px 4px 0;
  padding: 12px 18px;
  margin: 0 0 12px;
  font-family: var(--font-body);
  font-size: 0.95rem;
  color: #a8d8a8;
  line-height: 1.7;
}
.driver-label {
  font-family: var(--font-body);
  font-size: 0.70rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--green-text);
  margin-bottom: 5px;
}

/* ── Contradiction box ────────────────────────────────────────────────────── */
.contra-box {
  background: var(--red-bg);
  border: 1px solid #3a1818;
  border-radius: 4px;
  padding: 10px 16px;
  margin: 6px 0;
  font-family: var(--font-body);
  font-size: 0.92rem;
  color: #c8a0a0;
  line-height: 1.65;
}

/* ── Cluster cards ────────────────────────────────────────────────────────── */
.cluster-card {
  background: var(--bg-card-alt);
  border: 1px solid var(--border-mid);
  border-radius: 4px;
  padding: 14px 20px;
  margin-bottom: 14px;
}
.cluster-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}
.cluster-title {
  font-family: var(--font-body);
  font-size: 0.76rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--gold-dim);
}
.cluster-meta {
  font-family: var(--font-body);
  font-size: 0.80rem;
  font-style: italic;
  color: var(--text-muted);
}

/* ── News rows ────────────────────────────────────────────────────────────── */
.news-row {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 14px 18px;
  margin-bottom: 8px;
  transition: border-color 0.2s ease, background 0.2s ease;
}
.news-row:hover { border-color: var(--gold-dim); background: #181510; }
.news-meta {
  color: var(--text-muted);
  font-family: var(--font-body);
  font-size: 0.80rem;
  font-style: italic;
}
.rel-high { color: var(--gold);       font-weight: 600; }
.rel-med  { color: var(--amber-text); font-weight: 500; }
.rel-low  { color: var(--text-muted); font-weight: 400; }

/* ── Factor pills ─────────────────────────────────────────────────────────── */
.factor-pill {
  display: inline-block;
  background: #1c1910;
  border: 1px solid var(--border-mid);
  border-radius: 2px;
  padding: 3px 10px;
  margin: 3px 4px;
  font-family: var(--font-body);
  font-size: 0.82rem;
  color: var(--text-secondary);
}
.factor-pill-warn { border-color: #5a3030; color: var(--red-text); }

/* ── Historical context box ───────────────────────────────────────────────── */
.hist-box {
  background: var(--bg-card);
  border: 1px solid var(--border-mid);
  border-radius: 4px;
  padding: 12px 18px;
  font-family: var(--font-body);
  font-size: 0.90rem;
  color: var(--text-secondary);
}
.hist-label {
  font-family: var(--font-body);
  font-size: 0.70rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--gold-dim);
  margin-bottom: 5px;
}

/* ── Top movers row ───────────────────────────────────────────────────────── */
.mover-row {
  display: flex;
  justify-content: space-between;
  padding: 5px 0;
  border-bottom: 1px solid var(--border);
  font-family: var(--font-body);
  font-size: 0.85rem;
}

/* ── Backtest ─────────────────────────────────────────────────────────────── */
.bt-hit  { color: var(--green-text); }
.bt-miss { color: var(--red-text);   }

/* ── Buttons ──────────────────────────────────────────────────────────────── */
.stButton > button {
  font-family: var(--font-body) !important;
  font-size: 0.88rem !important;
  font-weight: 500 !important;
  letter-spacing: 0.06em !important;
  color: var(--gold) !important;
  background: transparent !important;
  border: 1px solid var(--border-mid) !important;
  border-radius: 3px !important;
  transition: border-color 0.2s ease, background 0.2s ease !important;
}
.stButton > button:hover {
  border-color: var(--gold-dim) !important;
  background: var(--gold-faint) !important;
  color: var(--gold) !important;
}
.stButton > button:disabled { opacity: 0.35 !important; }

/* ── Selectbox ────────────────────────────────────────────────────────────── */
.stSelectbox > div > div,
[data-baseweb="select"] > div {
  background-color: var(--bg-input) !important;
  border-color: var(--border-mid) !important;
  border-radius: 3px !important;
  color: var(--text-primary) !important;
  font-family: var(--font-body) !important;
}
[data-baseweb="select"] span {
  color: var(--text-primary) !important;
  font-family: var(--font-body) !important;
  font-size: 0.95rem !important;
}

/* ── Checkbox ─────────────────────────────────────────────────────────────── */
.stCheckbox label,
.stCheckbox label p {
  color: var(--text-secondary) !important;
  font-family: var(--font-body) !important;
  font-size: 0.92rem !important;
}

/* ── Expanders ────────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
  border: 1px solid var(--border) !important;
  border-radius: 4px !important;
  background: var(--bg-card) !important;
}
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary p {
  font-family: var(--font-body) !important;
  font-size: 0.92rem !important;
  color: var(--text-secondary) !important;
  letter-spacing: 0.02em;
}
[data-testid="stExpander"] summary:hover,
[data-testid="stExpander"] summary:hover p { color: var(--gold) !important; }

/* ── Alerts — FULL OVERRIDE (covers all Streamlit alert variants) ─────────── */
div[data-testid="stAlert"],
div[role="alert"],
.stAlert,
[data-baseweb="notification"] {
  font-family: var(--font-body) !important;
  font-size: 0.92rem !important;
  border-radius: 4px !important;
  border-width: 1px !important;
  border-style: solid !important;
}

/* Info banner — replace teal with slate-navy */
div[data-testid="stAlert"][kind="info"],
div[data-testid="stAlert"].st-emotion-cache-1clstc5,
[data-baseweb="notification"][kind="info"],
div[role="alert"]:has(svg[data-testid="stIconMaterial-info"]) {
  background: #0e1a2a !important;
  border-color: #1e3a5a !important;
  color: #a8c4dc !important;
}
div[data-testid="stAlert"][kind="info"] p,
div[data-testid="stAlert"][kind="info"] svg { color: #6a9abf !important; }

/* Warning banner — replace Streamlit's olive/yellow with warm amber */
div[data-testid="stAlert"][kind="warning"],
[data-baseweb="notification"][kind="warning"],
div[role="alert"]:has(svg[data-testid="stIconMaterial-warning"]) {
  background: var(--amber-bg) !important;
  border-color: #4a3010 !important;
  color: var(--amber-text) !important;
}
div[data-testid="stAlert"][kind="warning"] p,
div[data-testid="stAlert"][kind="warning"] svg { color: var(--amber-text) !important; }

/* Error banner */
div[data-testid="stAlert"][kind="error"],
[data-baseweb="notification"][kind="error"],
div[role="alert"]:has(svg[data-testid="stIconMaterial-error"]) {
  background: var(--red-bg) !important;
  border-color: #4a1818 !important;
  color: var(--red-text) !important;
}
div[data-testid="stAlert"][kind="error"] p,
div[data-testid="stAlert"][kind="error"] svg { color: var(--red-text) !important; }

/* Success banner */
div[data-testid="stAlert"][kind="success"],
[data-baseweb="notification"][kind="success"],
div[role="alert"]:has(svg[data-testid="stIconMaterial-check_circle"]) {
  background: var(--green-bg) !important;
  border-color: #1e4428 !important;
  color: var(--green-text) !important;
}

/* Nuclear override — catches any class-name Streamlit might generate */
div[data-testid="stAlert"] * {
  font-family: var(--font-body) !important;
}

/* ── Dataframe ────────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"],
[data-testid="stDataFrame"] * {
  font-family: var(--font-body) !important;
  font-size: 0.90rem !important;
}

/* ── Spinner ──────────────────────────────────────────────────────────────── */
[data-testid="stSpinner"] p {
  color: var(--text-muted) !important;
  font-family: var(--font-body) !important;
  font-style: italic;
}

/* ── Toast ────────────────────────────────────────────────────────────────── */
[data-testid="stToast"],
[data-testid="stToast"] * {
  background: var(--bg-card) !important;
  border: 1px solid var(--border-mid) !important;
  color: var(--text-primary) !important;
  font-family: var(--font-body) !important;
  border-radius: 4px !important;
}

/* ── Markdown body ────────────────────────────────────────────────────────── */
.stMarkdown p, .stMarkdown li {
  color: var(--text-secondary) !important;
  font-family: var(--font-body) !important;
  font-size: 0.97rem;
  font-weight: 400;
  line-height: 1.8;
}
.stMarkdown strong {
  color: var(--text-primary) !important;
  font-weight: 600;
}
.stMarkdown em { color: var(--text-secondary) !important; }
.stMarkdown a {
  color: var(--gold-dim) !important;
  text-decoration: underline;
  text-underline-offset: 3px;
}
.stMarkdown a:hover { color: var(--gold) !important; }
.stMarkdown code {
  background: #1e1c16 !important;
  color: var(--gold) !important;
  border: 1px solid var(--border-mid) !important;
  border-radius: 2px;
  padding: 1px 6px;
  font-size: 0.85em;
}

/* ── Scrollbars ───────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-main); }
::-webkit-scrollbar-thumb { background: var(--border-rule); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--gold-faint); }

</style>
""", unsafe_allow_html=True)

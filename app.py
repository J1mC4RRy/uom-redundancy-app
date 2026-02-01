# app.py
from dataclasses import dataclass
from datetime import date
from typing import Optional
import time
import random

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

# ----------------------------
# Page setup
# ----------------------------
st.set_page_config(
    page_title="UoM PASO Redundancy Calculator",
    page_icon="💼",
    layout="wide",
)

# ----------------------------
# CSS
# ----------------------------
st.markdown(
    """
<style>
.block-container { padding-top: 1.2rem; padding-bottom: 2.5rem; }
h1, h2, h3 { letter-spacing: -0.02em; }
small { opacity: 0.85; }

/* Remove header anchor/link icons */
a[data-testid="stHeaderActionElements"] { display: none !important; }

/* Hide Deploy button (keep the top-right menu available for theme switching, etc.) */
[data-testid="stDeployButton"] { display: none !important; }

/* Hide tooltip/help bubble icon */
[data-testid="stTooltipIcon"] { display: none !important; }

/* Expander look */
div[data-testid="stExpander"] details {
  border-radius: 14px;
  border: 1px solid rgba(120,120,120,0.22);
  background: rgba(255,255,255,0.03);
}

/* KPI cards */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
  margin: 10px 0 6px 0;
}
.kpi-card{
  border: 1px solid rgba(120,120,120,0.22);
  border-radius: 14px;
  padding: 12px 14px;
  background: rgba(255,255,255,0.03);
}
.kpi-label{
  font-size: 13px;
  opacity: 0.75;
  margin-bottom: 6px;
}
.kpi-value{
  font-size: 26px;
  font-weight: 750;
  letter-spacing: -0.02em;
  line-height: 1.15;
}

/* Gold emphasis for Gross + Net */
.kpi-gold .kpi-value{
  color: #C9A227;
  font-style: italic;
  font-weight: 900;
}
.kpi-gold .kpi-label{
  opacity: 0.85;
}
</style>
""",
    unsafe_allow_html=True,
)

# ----------------------------
# Header
# ----------------------------
st.title("UoM PASO redundancy payout calculator")
st.caption("Standard professional, admin, support. Base salary only. Super excluded.")

# ----------------------------
# Defaults
# ----------------------------
FY_CAPS = {
    "2025-26": {"base": 13100.0, "service": 6552.0},
    "2024-25": {"base": 12524.0, "service": 6264.0},
    "2023-24": {"base": 11985.0, "service": 5994.0},
}

DEFAULTS = {
    "notice_weeks": 8.0,
    "leave_withholding": 0.32,
    "etp_tax_under_pres": 0.32,
    "etp_tax_over_pres": 0.17,
    "annual_leave_loading_pct": 0.175,
}

LINK_VIC_LSL = "https://business.vic.gov.au/business-information/staff-and-hr/long-service-leave-victoria/calculate-long-service-leave"
LINK_ATO_ETP = "https://www.ato.gov.au/tax-rates-and-codes/key-superannuation-rates-and-thresholds/employment-termination-payments#ato-Taxfreepartofgenuineredundancyandearlyretirementschemepayments"

# ----------------------------
# Helpers
# ----------------------------
def pretty_date(d: date) -> str:
    return d.strftime("%d %B %Y")

def money(x: float) -> str:
    return f"${x:,.2f}"

def weekly_pay(annual_salary: float) -> float:
    return annual_salary / 52.0

def full_months_between(start: date, end: date) -> int:
    if end < start:
        return 0
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(0, months)

def years_and_months_from_total(total_months: int):
    years = total_months // 12
    months = total_months % 12
    return years, months

def age_on(dob: date, on_date: date) -> int:
    years = on_date.year - dob.year
    if (on_date.month, on_date.day) < (dob.month, dob.day):
        years -= 1
    return years

def redundancy_weeks_paso_standard(start: date, notice_date: date, dob: date):
    total_months = full_months_between(start, notice_date)
    yrs, mos = years_and_months_from_total(total_months)

    base_weeks = 3.0 * yrs + 0.25 * mos
    a = age_on(dob, notice_date)
    is_45_plus = a >= 45

    weeks = base_weeks + (2.0 if is_45_plus else 0.0)
    if weeks > 0:
        weeks = max(14.0, min(52.0, weeks))

    return weeks, yrs, mos, a, is_45_plus

def tax_free_cap(
    fy: str,
    completed_years: int,
    base_override: Optional[float],
    svc_override: Optional[float],
) -> float:
    base = base_override if base_override is not None else FY_CAPS.get(fy, {}).get("base", 0.0)
    svc = svc_override if svc_override is not None else FY_CAPS.get(fy, {}).get("service", 0.0)
    return float(base + svc * completed_years)

def donut_chart(df: pd.DataFrame, title: str):
    chart_df = df[df["Gross"] > 0].copy()
    total = float(chart_df["Gross"].sum())

    if total <= 0 or chart_df.empty:
        return None

    colors = [
        "#1D4ED8",  # blue
        "#F59E0B",  # amber
        "#DC2626",  # red
        "#10B981",  # green
        "#7C3AED",  # violet
        "#0EA5E9",  # cyan
    ]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=chart_df["Type"],
                values=chart_df["Gross"],
                hole=0.5,
                sort=False,
                direction="clockwise",
                textposition="outside",
                texttemplate="%{label}<br>$%{value:,.2f} (%{percent:.1%})",
                textfont=dict(color="black", size=13),
                marker=dict(colors=colors),
                showlegend=False,
                hovertemplate="%{label}<br>$%{value:,.2f} (%{percent:.1%})<extra></extra>",
            )
        ]
    )

    fig.add_annotation(
        x=0.5,
        y=0.5,
        text=f"Total<br>{money(total)}",
        showarrow=False,
        font=dict(color="black", size=13),
    )

    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center"),
        width=480,
        height=480,
        margin=dict(l=50, r=50, t=50, b=50),
        uniformtext_minsize=9,
        uniformtext_mode="hide",
    )

    return fig

def fmt_currency(v: float) -> str:
    return f"${v:,.2f}"

def fmt_float(v: float, dp: int = 2) -> str:
    return f"{v:.{dp}f}"

def kpi_card_html(label: str, value: str, gold: bool = False) -> str:
    cls = "kpi-card kpi-gold" if gold else "kpi-card"
    return f"""
    <div class="{cls}">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{value}</div>
    </div>
    """

def animate_number(placeholder, label: str, old: float, new: float, kind: str, gold: bool):
    frames = 14
    duration = 0.45
    sleep_s = duration / frames

    span = abs(new - old)
    wobble = max(span * 0.08, 1.0)

    for i in range(frames):
        t = (i + 1) / frames
        val = old + (new - old) * t

        jitter_scale = (1.0 - t) ** 1.6
        val = val + random.uniform(-wobble, wobble) * jitter_scale

        if kind == "currency":
            s = fmt_currency(max(0.0, val))
        else:
            s = fmt_float(val, 2)

        placeholder.markdown(kpi_card_html(label, s, gold=gold), unsafe_allow_html=True)
        time.sleep(sleep_s)

    final = fmt_currency(new) if kind == "currency" else fmt_float(new, 2)
    placeholder.markdown(kpi_card_html(label, final, gold=gold), unsafe_allow_html=True)

@dataclass
class Results:
    weekly: float
    day_rate: float
    service_years: int
    service_months: int
    age: int
    is_45_plus: bool
    redundancy_weeks: float
    redundancy_gross: float
    notice_gross: float
    al_gross: float
    lsl_gross: float
    al_loading_gross: float
    leave_gross: float
    etp_gross: float
    cap: float
    etp_taxable: float
    etp_tax: float
    leave_tax: float
    notice_tax: float
    total_gross: float
    total_tax: float
    total_net: float

# ----------------------------
# Sidebar inputs
# ----------------------------
st.sidebar.markdown("## Inputs")
st.sidebar.caption("Fill what you know. Leave the rest as zero.")

annual_salary = st.sidebar.number_input(
    "Base salary (annual, ex super)",
    min_value=0.0,
    value=158000.0,
    step=500.0,
)

DOB_MIN = date(1950, 1, 1)
TODAY = date.today()
NOTICE_MAX = date(TODAY.year + 30, 12, 31)

dob = st.sidebar.date_input(
    "Date of birth (for 45+ rule)",
    value=date(1992, 8, 12),
    min_value=DOB_MIN,
    max_value=TODAY,
)
st.sidebar.caption(f"Selected: **{pretty_date(dob)}**")

start_date = st.sidebar.date_input(
    "Start date (continuous service)",
    value=date(2021, 10, 11),
    min_value=DOB_MIN,
    max_value=TODAY,
)
st.sidebar.caption(f"Selected: **{pretty_date(start_date)}**")

notice_date = st.sidebar.date_input(
    "Notice of redundancy date",
    value=date(TODAY.year + 1, TODAY.month, min(TODAY.day, 28)),
    min_value=DOB_MIN,
    max_value=NOTICE_MAX,
)
st.sidebar.caption(f"Selected: **{pretty_date(notice_date)}**")

st.sidebar.markdown("---")
st.sidebar.markdown("### Cash components")

notice_weeks = st.sidebar.number_input("Notice pay (weeks)", min_value=0.0, value=DEFAULTS["notice_weeks"], step=0.5)
notice_paid_in_lieu = st.sidebar.toggle("Notice paid in lieu", value=True)

al_days = st.sidebar.number_input("Unused annual leave (days)", min_value=0.0, value=5.0, step=0.5)
lsl_weeks = st.sidebar.number_input("Unused LSL (weeks)", min_value=0.0, value=4.0, step=1.0)

include_al_loading = st.sidebar.toggle("Include annual leave loading", value=False)
al_loading_pct = st.sidebar.number_input(
    "Annual leave loading %",
    min_value=0.0,
    max_value=1.0,
    value=DEFAULTS["annual_leave_loading_pct"],
    step=0.005,
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Tax estimate (simple)")

fy = st.sidebar.selectbox("Income year for tax free cap", options=list(FY_CAPS.keys()), index=0)
cap_base = st.sidebar.number_input("Cap base amount", min_value=0.0, value=float(FY_CAPS[fy]["base"]), step=100.0)
cap_service = st.sidebar.number_input("Cap per completed year", min_value=0.0, value=float(FY_CAPS[fy]["service"]), step=100.0)

under_pres = st.sidebar.toggle("Under preservation age", value=True)
etp_tax_u = st.sidebar.number_input(
    "ETP tax rate (under preservation age)",
    0.0,
    1.0,
    DEFAULTS["etp_tax_under_pres"],
    0.01,
)
etp_tax_o = st.sidebar.number_input(
    "ETP tax rate (at/over preservation age)",
    0.0,
    1.0,
    DEFAULTS["etp_tax_over_pres"],
    0.01,
)
leave_withholding = st.sidebar.number_input("Leave withholding rate", 0.0, 1.0, DEFAULTS["leave_withholding"], 0.01)

# ----------------------------
# Compute
# ----------------------------
w = weekly_pay(annual_salary)
day_rate = w / 5.0

red_weeks, svc_years, svc_months, age, is_45_plus = redundancy_weeks_paso_standard(start_date, notice_date, dob)

redundancy_gross = red_weeks * w
notice_gross = notice_weeks * w

al_gross = al_days * day_rate
lsl_gross = lsl_weeks * w
al_loading_gross = (al_loading_pct * al_gross) if include_al_loading else 0.0
leave_gross = al_gross + lsl_gross + al_loading_gross

etp_gross = redundancy_gross + (notice_gross if notice_paid_in_lieu else 0.0)
cap = tax_free_cap(fy, svc_years, cap_base, cap_service)
etp_taxable = max(0.0, etp_gross - cap)

etp_rate = etp_tax_u if under_pres else etp_tax_o
etp_tax = etp_taxable * etp_rate

leave_tax = leave_gross * leave_withholding
notice_tax = 0.0
if not notice_paid_in_lieu:
    notice_tax = notice_gross * leave_withholding

total_gross = redundancy_gross + notice_gross + leave_gross
total_tax = etp_tax + leave_tax + notice_tax
total_net = total_gross - total_tax

unused_al_weeks = al_days / 5.0

res = Results(
    weekly=w,
    day_rate=day_rate,
    service_years=svc_years,
    service_months=svc_months,
    age=age,
    is_45_plus=is_45_plus,
    redundancy_weeks=red_weeks,
    redundancy_gross=redundancy_gross,
    notice_gross=notice_gross,
    al_gross=al_gross,
    lsl_gross=lsl_gross,
    al_loading_gross=al_loading_gross,
    leave_gross=leave_gross,
    etp_gross=etp_gross,
    cap=cap,
    etp_taxable=etp_taxable,
    etp_tax=etp_tax,
    leave_tax=leave_tax,
    notice_tax=notice_tax,
    total_gross=total_gross,
    total_tax=total_tax,
    total_net=total_net,
)

# ----------------------------
# Gamified KPI cards (reordered)
# weekly, redundancy, unused AL, unused LSL, gross, net
# ----------------------------
col1, col2, col3, col4, col5, col6 = st.columns(6)
p1, p2, p3, p4, p5, p6 = col1.empty(), col2.empty(), col3.empty(), col4.empty(), col5.empty(), col6.empty()

kpi_now = {
    "weekly_pay": float(res.weekly),
    "redundancy_weeks": float(res.redundancy_weeks),
    "unused_al_weeks": float(unused_al_weeks),
    "unused_lsl_weeks": float(lsl_weeks),
    "gross_total": float(res.total_gross),
    "net_total": float(res.total_net),
}

if "kpi_prev" not in st.session_state:
    st.session_state["kpi_prev"] = kpi_now.copy()

kpi_prev = st.session_state["kpi_prev"]

def render_kpi(placeholder, key, label, kind, gold=False):
    old = float(kpi_prev.get(key, kpi_now[key]))
    new = float(kpi_now[key])

    if old != new:
        animate_number(placeholder, label, old, new, kind=kind, gold=gold)
    else:
        val = fmt_currency(new) if kind == "currency" else fmt_float(new, 2)
        placeholder.markdown(kpi_card_html(label, val, gold=gold), unsafe_allow_html=True)

render_kpi(p1, "weekly_pay", "Weekly pay", "currency", gold=False)
render_kpi(p2, "redundancy_weeks", "Redundancy weeks", "float", gold=False)
render_kpi(p3, "unused_al_weeks", "Unused annual leave (weeks)", "float", gold=False)
render_kpi(p4, "unused_lsl_weeks", "Unused LSL (weeks)", "float", gold=False)
render_kpi(p5, "gross_total", "Gross total", "currency", gold=True)
render_kpi(p6, "net_total", "Estimated net", "currency", gold=True)

st.session_state["kpi_prev"] = kpi_now.copy()

st.markdown("---")

# ----------------------------
# Rules section
# ----------------------------
with st.expander("Clauses that matter for redundancy (PASO)", expanded=False):
    st.markdown(
        f"""
### The process bits
**1.40 Consultation on major change**  
- Redundancy counts as a "significant effect".  
- Uni should consult, share info, and listen.  
- A consult window is common.

**1.42 Grievance and dispute process**  
- You can dispute process issues.  
- You can escalate steps if it stays messy.

### What redundancy is and what Uni must try first
**1.45 What counts as redundancy, and what Uni must try first**  
- Sets the redundancy triggers.  
- Uni must try reasonable alternatives under 1.46 before involuntary separation.

**1.46 Redeployment and alternatives**  
- Defines "Suitable Alternative Position".  
- Covers salary maintenance rules.  
- Covers early separation and temporary redeployment.  
- You cannot unreasonably decline a suitable role.

### Notice
**1.47 Redundancy notice**  
- Uni tells you the role is redundant.  
- The 8-week notice starts.  
- Uni should still try redeployment during notice.  
- Early separation can trigger pay in lieu of remaining notice plus redundancy pay.

**3.25 Normal termination notice**  
- Does not apply to redundancy.  
- Redundancy notice is handled by 1.47.

### The money formula
**3.27 PASO redundancy pay formula**  
- 3 weeks per completed year.  
- Add 0.25 weeks per completed month.  
- Add 2 weeks if you are 45+ on the notice date.  
- Min 14 weeks, max 52 weeks.

**3.27.4 What "salary/pay" includes**  
- Base salary + allowances/loadings.  
- Excludes additional hours and super.

**3.27.5 When redundancy pay is not payable**  
- Offered a suitable alternative role (and the rule applies).  
- Accept alternative arrangements.  
- Serious misconduct.

### Leave and salary sacrifice protections
**1.19.6 Annual leave payout**  
- Unused annual leave is paid out at termination.

**1.20.5 LSL payout on redundancy**  
- Pro-rata LSL after 1 year if employment ends due to redundancy.  
- Vic calculator: {LINK_VIC_LSL}

**1.11.8 / 1.12.2 Salary sacrifice protection**  
- Termination payments are calculated on salary as if you never salary-sacrificed.

### Tax info (for context only)
- ATO ETP and tax-free cap explainer: {LINK_ATO_ETP}
"""
    )

st.markdown("---")

# ----------------------------
# Service + age cards (under clauses)
# ----------------------------
c1, c2 = st.columns(2)

service_text = f"{res.service_years} years, {res.service_months} months"
age_text = f"{res.age} years"
age_badge = "Meets 45+ rule ✅" if res.is_45_plus else "Does not meet 45+ rule ❌"

with c1:
    st.markdown(
        f"""
        <div class="kpi-card">
          <div class="kpi-label">Length of service (as at notice date)</div>
          <div class="kpi-value">{service_text}</div>
          <div class="kpi-label" style="margin-top:8px; opacity:0.65;">
            Start: {pretty_date(start_date)} · Notice: {pretty_date(notice_date)}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c2:
    st.markdown(
        f"""
        <div class="kpi-card {'kpi-gold' if res.is_45_plus else ''}">
          <div class="kpi-label">Age at redundancy (notice date)</div>
          <div class="kpi-value">{age_text}</div>
          <div class="kpi-label" style="margin-top:8px; opacity:0.65;">
            {age_badge}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")

# ----------------------------
# Cash components (donut LEFT, table RIGHT)
# ----------------------------
st.markdown("## Cash components")

rows = [
    {"Type": "Redundancy pay", "Rate": money(res.weekly), "Qty": f"{res.redundancy_weeks:.2f} weeks", "Gross": res.redundancy_gross},
    {"Type": "Notice pay", "Rate": money(res.weekly), "Qty": f"{notice_weeks:.2f} weeks", "Gross": res.notice_gross},
    {"Type": "Annual leave payout", "Rate": money(res.day_rate), "Qty": f"{al_days:.1f} days", "Gross": res.al_gross},
    {"Type": "LSL payout", "Rate": money(res.weekly), "Qty": f"{lsl_weeks:.2f} weeks", "Gross": res.lsl_gross},
    {"Type": "Annual leave loading", "Rate": "", "Qty": f"{al_loading_pct:.3f}" if include_al_loading else "Off", "Gross": res.al_loading_gross},
]
df_components = pd.DataFrame(rows)

# Percent share of gross (hide when total is 0)
total_gross_components = float(df_components["Gross"].sum())
if total_gross_components > 0:
    df_components["Percent"] = (df_components["Gross"] / total_gross_components) * 100
else:
    df_components["Percent"] = 0.0

# Display formatting
df_components_display = df_components.copy()
df_components_display["Gross"] = df_components_display["Gross"].apply(money)
df_components_display = df_components.copy()
df_components_display["Gross"] = df_components_display["Gross"].apply(money)
df_components_display["Percent"] = df_components_display["Percent"].round(1).astype(str) + "%"
st.markdown("### Donut chart")
fig = donut_chart(df_components[["Type", "Gross"]], "Share of gross payout")
if fig is None:
    st.info("Nothing to chart yet. Add at least one cash component.")
else:
    # Optional: keep the chart from stretching too wide on huge screens
    c1, c2, c3 = st.columns([1, 3, 1])
    with c2:
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

st.markdown("### Breakdown table")
st.dataframe(df_components_display, use_container_width=True, hide_index=True)

st.markdown("---")

# ----------------------------
# Tax estimate
# ----------------------------
st.markdown("## Tax estimate (simple)")
st.caption("This is a rough net estimate. Payroll can differ.")

tax_rows = [
    {"Bucket": "ETP pool gross (redundancy + notice in lieu)", "Amount": res.etp_gross},
    {"Bucket": "Tax free cap", "Amount": res.cap},
    {"Bucket": "Taxable ETP", "Amount": res.etp_taxable},
    {"Bucket": f"ETP tax (@ {etp_rate:.0%})", "Amount": res.etp_tax},
    {"Bucket": "Leave gross (AL + LSL + loading)", "Amount": res.leave_gross},
    {"Bucket": f"Leave withholding (@ {leave_withholding:.0%})", "Amount": res.leave_tax},
]
if not notice_paid_in_lieu:
    tax_rows.append({"Bucket": f"Notice withholding (@ {leave_withholding:.0%})", "Amount": notice_tax})

df_tax = pd.DataFrame(tax_rows)
df_tax_display = df_tax.copy()
df_tax_display["Amount"] = df_tax_display["Amount"].apply(money)
st.dataframe(df_tax_display, use_container_width=True, hide_index=True)

st.markdown("---")

# ----------------------------
# Export
# ----------------------------
st.markdown("## Export")

df_components_out = df_components.copy()
df_tax_out = df_tax.copy()

df_components_out["Gross"] = df_components_out["Gross"].round(2)
df_tax_out["Amount"] = df_tax_out["Amount"].round(2)

csv_out = pd.concat(
    [
        df_components_out.assign(Section="Cash components").rename(columns={"Gross": "Value"}),
        df_tax_out.assign(Section="Tax model").rename(columns={"Amount": "Value"}),
    ],
    ignore_index=True,
)

st.download_button(
    "Download CSV",
    data=csv_out.to_csv(index=False).encode("utf-8"),
    file_name="uom_redundancy_breakdown.csv",
    mime="text/csv",
)

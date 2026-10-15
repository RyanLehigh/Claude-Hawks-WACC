"""The WACC card.

Run from the repo root:   streamlit run app.py

Owner: the product manager. This works today on the FAKE numbers, so you can build
the page before the real numbers exist. When the developer's pull request is merged,
outputs/wacc.csv appears and the app switches to it automatically.

The app only reads files from outputs/ and inputs/. The extra charts (rolling beta,
returns scatter, peers) appear only when code/wacc.py has written their files.
"""
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title='WACC card', layout='wide')

BLUE, ORANGE, GRAY = '#2a78d6', '#eb6834', '#8a8984'
OUT = Path('outputs')


def read_optional(name, **kw):
    p = OUT / name
    return pd.read_csv(p, **kw) if p.exists() else None


def wacc_of(beta, rf, mrp, rd, tax, w_d):
    return (1 - w_d) * (rf + beta * mrp) + w_d * rd * (1 - tax)


# ---------- data ----------
real = OUT / 'wacc.csv'
card = pd.read_csv(real if real.exists() else OUT / 'wacc_FAKE.csv').iloc[0]
inputs = pd.read_csv('inputs/assumptions.csv', index_col='item')
rets = read_optional('returns.csv', index_col='date', parse_dates=True)
roll = read_optional('rolling_beta.csv', index_col='date', parse_dates=True)
peers = read_optional('peers.csv')
tkr = card['ticker']

if not real.exists():
    st.warning('Showing FAKE numbers. Run `python code/wacc.py` to make outputs/wacc.csv.')
placeholders = inputs.index[inputs['source'].str.contains('TODO', na=False)].tolist()
if placeholders:
    st.info(f"Placeholder assumptions still awaiting a source: **{', '.join(placeholders)}**. "
            'Treat the WACC as illustrative until the analyst fills them in.')

# ---------- sidebar: what-if ----------
st.sidebar.header('What if?')
st.sidebar.caption('Move an input and the WACC is recomputed live. The base case comes from outputs/wacc.csv.')
s_beta = st.sidebar.slider('Beta', 0.2, 2.0, float(round(card['beta'], 2)), 0.01)
s_rf = st.sidebar.slider('Risk-free rate', 0.0, 0.08, float(card['rf']), 0.0025, format='%.4f')
s_mrp = st.sidebar.slider('Market risk premium', 0.03, 0.08, float(card['mrp']), 0.0025, format='%.4f')
s_rd = st.sidebar.slider('Pre-tax cost of debt', 0.02, 0.12, float(card['rd']), 0.0025, format='%.4f')
s_tax = st.sidebar.slider('Tax rate', 0.0, 0.35, float(card['tax']), 0.01)
s_wd = st.sidebar.slider('Debt weight (w_d)', 0.0, 0.8, float(card['w_d']), 0.01)

base = float(card['wacc'])
live = wacc_of(s_beta, s_rf, s_mrp, s_rd, s_tax, s_wd)
live_ke = s_rf + s_beta * s_mrp
changed = abs(live - base) >= 0.5e-4  # ignore slider rounding (under half a bp)

# ---------- header ----------
st.title(f'WACC card: {tkr}')
st.caption(f"Madison Square Garden Sports Corp. · beta from daily returns vs. SPY, 5 years through {card['asof']}")

st.markdown(
    f"#### New projects at {tkr} need to return at least **{base:.1%}** a year to create value "
    f"for investors. A project with the same risk as the business that earns less than that destroys value.")

c1, c2, c3, c4 = st.columns(4)
c1.metric('WACC (base)', f'{base:.2%}')
c2.metric('WACC (your inputs)', f'{live:.2%}', f'{(live - base) * 1e4:+.0f} bp' if changed else None,
          delta_color='inverse')
c3.metric('Cost of equity', f"{card['cost_of_equity']:.2%}")
c4.metric('Equity beta', f"{card['beta']:.2f}")

tab_build, tab_sens, tab_beta, tab_peers, tab_inputs = st.tabs(
    ['How it is built', 'Sensitivity', 'Is the beta stable?', 'Peers', 'Inputs and sources'])

# ---------- build ----------
with tab_build:
    eq_part = card['w_e'] * card['cost_of_equity']
    debt_pre = card['w_d'] * card['rd']
    shield = debt_pre * card['tax']
    steps = pd.DataFrame({
        'step': ['Equity: w_e × cost of equity', 'Debt: w_d × rd (pre-tax)', 'Tax shield on debt', 'WACC'],
        'value': [eq_part, debt_pre, -shield, base]})
    steps['end'] = [eq_part, eq_part + debt_pre, base, base]
    steps['start'] = [0, eq_part, eq_part + debt_pre, 0]
    steps['top'] = steps[['start', 'end']].max(axis=1)
    steps['kind'] = ['add', 'add', 'subtract', 'total']
    steps['label'] = [f'{v:+.2%}' if k != 'total' else f'{v:.2%}' for v, k in zip(steps['value'], steps['kind'])]
    order = steps['step'].tolist()
    bars = alt.Chart(steps).mark_bar(cornerRadius=4, size=46).encode(
        x=alt.X('step:N', sort=order, title=None, axis=alt.Axis(labelAngle=0, labelLimit=220)),
        y=alt.Y('start:Q', title='Contribution to WACC', axis=alt.Axis(format='%')),
        y2='end:Q',
        color=alt.Color('kind:N', scale=alt.Scale(domain=['add', 'subtract', 'total'],
                                                  range=[BLUE, ORANGE, '#184f95']), legend=None),
        tooltip=[alt.Tooltip('step:N', title='Step'), alt.Tooltip('value:Q', title='Amount', format='+.2%')])
    text = alt.Chart(steps).mark_text(dy=-9, fontSize=13, color=GRAY).encode(
        x=alt.X('step:N', sort=order), y='top:Q', text='label:N')
    left, right = st.columns([3, 2])
    left.altair_chart((bars + text).properties(height=340), width='stretch')
    right.markdown(f"""
**Reading the build**

- Equity funds **{card['w_e']:.0%}** of the firm and costs **{card['cost_of_equity']:.2%}**,
  so it adds **{eq_part:.2%}** to the WACC (**{eq_part / base:.0%}** of the total).
- Debt is cheaper after tax: {card['rd']:.2%} × (1 − {card['tax']:.0%}) = **{card['rd'] * (1 - card['tax']):.2%}**.
- The tax shield on interest takes **{shield * 1e4:.0f} bp** off the WACC.
- With a beta of {card['beta']:.2f}, investors treat {tkr} as **{'less' if card['beta'] < 1 else 'more'} risky than
  the market**, so its cost of equity sits {'below' if card['beta'] < 1 else 'above'} the
  {card['rf'] + card['mrp']:.1%} expected market return.
""")

# ---------- sensitivity ----------
with tab_sens:
    st.markdown('Which input moves the answer most? Each bar moves one input across a plausible range and holds the others at the base case.')
    b = dict(beta=card['beta'], rf=card['rf'], mrp=card['mrp'], rd=card['rd'], tax=card['tax'], w_d=card['w_d'])
    ranges = {'Beta (±0.25)': ('beta', -0.25, 0.25), 'Market risk premium (±1pt)': ('mrp', -0.01, 0.01),
              'Risk-free rate (±1pt)': ('rf', -0.01, 0.01), 'Debt weight (±10pt, min 0)': ('w_d', -0.10, 0.10),
              'Cost of debt (±1pt)': ('rd', -0.01, 0.01), 'Tax rate (±5pt)': ('tax', -0.05, 0.05)}
    rows = []
    for label, (k, lo, hi) in ranges.items():
        w_lo = wacc_of(**{**b, k: max(0.0, b[k] + lo)}) - base  # no negative rates or weights
        w_hi = wacc_of(**{**b, k: b[k] + hi}) - base
        rows.append({'input': label, 'low': min(w_lo, w_hi), 'high': max(w_lo, w_hi), 'swing': abs(w_hi - w_lo)})
    tor = pd.DataFrame(rows).sort_values('swing', ascending=False)
    torn = alt.Chart(tor).mark_bar(cornerRadius=4, size=22, color=BLUE).encode(
        y=alt.Y('input:N', sort=tor['input'].tolist(), title=None, axis=alt.Axis(labelLimit=240)),
        x=alt.X('low:Q', title='Change in WACC vs. base', axis=alt.Axis(format='+.1%')),
        x2='high:Q',
        tooltip=[alt.Tooltip('input:N', title='Input'), alt.Tooltip('low:Q', format='+.2%', title='Low'),
                 alt.Tooltip('high:Q', format='+.2%', title='High')])
    zero = alt.Chart(pd.DataFrame({'x': [0]})).mark_rule(color=GRAY).encode(x='x:Q')
    st.altair_chart((torn + zero).properties(height=280), width='stretch')
    top = tor.iloc[0]
    st.caption(f"Biggest lever: **{top['input']}**, a swing of {top['swing'] * 1e4:.0f} bp in the WACC.")

    st.markdown('##### WACC across beta and leverage')
    betas = np.round(np.arange(0.3, 1.31, 0.1), 2)
    wds = np.round(np.arange(0.0, 0.61, 0.1), 2)
    grid = pd.DataFrame([(bb, wd, wacc_of(bb, s_rf, s_mrp, s_rd, s_tax, wd)) for bb in betas for wd in wds],
                        columns=['beta', 'w_d', 'wacc'])
    heat = alt.Chart(grid).mark_rect(stroke='white', strokeWidth=2).encode(
        x=alt.X('beta:O', title='Equity beta', axis=alt.Axis(labelAngle=0)),
        y=alt.Y('w_d:O', title='Debt weight', sort='descending', axis=alt.Axis(format='.0%')),
        color=alt.Color('wacc:Q', scale=alt.Scale(range=['#cde2fb', '#104281']), legend=alt.Legend(format='.0%', title='WACC')),
        tooltip=[alt.Tooltip('beta:O', title='Beta'), alt.Tooltip('w_d:O', format='.0%', title='Debt weight'),
                 alt.Tooltip('wacc:Q', format='.2%', title='WACC')])
    labels = alt.Chart(grid).mark_text(fontSize=11).encode(
        x='beta:O', y=alt.Y('w_d:O', sort='descending'), text=alt.Text('wacc:Q', format='.1%'),
        color=alt.condition(alt.datum.wacc > float(grid['wacc'].median()), alt.value('white'), alt.value('#0b0b0b')))
    st.altair_chart((heat + labels).properties(height=320), width='stretch')
    st.caption('Uses the rf, MRP, cost of debt and tax rate from the sidebar. With a low beta, adding debt '
               'lowers the WACC only a little, because equity is already cheap. (The grid holds beta fixed; '
               'in practice more debt also raises the equity beta.)')

# ---------- beta ----------
with tab_beta:
    if roll is None or rets is None:
        st.info('Run `python code/wacc.py` to write outputs/returns.csv and outputs/rolling_beta.csv.')
    else:
        b5 = float(card['beta'])
        lo_b, hi_b = roll['beta'].min(), roll['beta'].max()
        k1, k2, k3 = st.columns(3)
        k1.metric('5-year beta', f'{b5:.2f}')
        k2.metric('1-year beta range', f'{lo_b:.2f} – {hi_b:.2f}')
        k3.metric('WACC range from that beta range',
                  f"{wacc_of(lo_b, card['rf'], card['mrp'], card['rd'], card['tax'], card['w_d']):.2%} – "
                  f"{wacc_of(hi_b, card['rf'], card['mrp'], card['rd'], card['tax'], card['w_d']):.2%}")

        rb = roll.reset_index()
        hover = alt.selection_point(fields=['date'], nearest=True, on='pointerover', empty=False)
        line = alt.Chart(rb).mark_line(color=BLUE, strokeWidth=2).encode(
            x=alt.X('date:T', title=None), y=alt.Y('beta:Q', title='Trailing 1-year beta', scale=alt.Scale(zero=False)))
        pts = line.mark_point(size=60, filled=True, color=BLUE).encode(
            opacity=alt.condition(hover, alt.value(1), alt.value(0)),
            tooltip=[alt.Tooltip('date:T', title='Date'), alt.Tooltip('beta:Q', format='.2f', title='1y beta')]
        ).add_params(hover)
        ref = alt.Chart(pd.DataFrame({'y': [b5], 'lab': [f'5-year beta {b5:.2f}']}))
        rule = ref.mark_rule(color=ORANGE, strokeDash=[6, 4], strokeWidth=2).encode(y='y:Q')
        rule_txt = ref.mark_text(align='left', dx=4, dy=-8, color=ORANGE).encode(
            y='y:Q', x=alt.value(0), text='lab:N')
        st.altair_chart((line + pts + rule + rule_txt).properties(height=320), width='stretch')

        # regression view
        x, y = rets['SPY'], rets[tkr]
        r2 = x.corr(y) ** 2
        vol_s, vol_m = y.std() * np.sqrt(252), x.std() * np.sqrt(252)
        st.markdown('##### Daily returns: ' + tkr + ' vs. SPY')
        left, right = st.columns([3, 2])
        sc = rets.reset_index()
        dots = alt.Chart(sc).mark_circle(size=14, opacity=0.35, color=BLUE).encode(
            x=alt.X('SPY:Q', title='SPY daily return', axis=alt.Axis(format='%')),
            y=alt.Y(f'{tkr}:Q', title=f'{tkr} daily return', axis=alt.Axis(format='%')),
            tooltip=[alt.Tooltip('date:T', title='Date'), alt.Tooltip('SPY:Q', format='.2%'),
                     alt.Tooltip(f'{tkr}:Q', format='.2%')])
        alpha = y.mean() - b5 * x.mean()
        xs = np.linspace(x.min(), x.max(), 2)
        fit = alt.Chart(pd.DataFrame({'SPY': xs, tkr: alpha + b5 * xs})).mark_line(color=ORANGE, strokeWidth=2).encode(
            x='SPY:Q', y=f'{tkr}:Q')
        left.altair_chart((dots + fit).properties(height=340), width='stretch')
        right.markdown(f"""
**What the scatter says**

- The orange line's slope is the beta: **{b5:.2f}**. On a day SPY moves 1%, {tkr} tends to move about {b5:.2f}%.
- R² is only **{r2:.0%}**: the market explains a small share of {tkr}'s daily moves.
  Most of its risk is company-specific (team results, media deals, deal news), which diversified
  investors don't get paid for, so it doesn't raise the cost of equity.
- Annualized volatility: **{vol_s:.0%}** for {tkr} vs. **{vol_m:.0%}** for SPY. More volatile than the market, yet a lower beta.
- The 1-year beta has ranged from {lo_b:.2f} to {hi_b:.2f}. That's why we use a 5-year window.
""")

# ---------- peers ----------
with tab_peers:
    if peers is None:
        st.info('Run `python code/wacc.py` to write outputs/peers.csv.')
    else:
        pr = peers.copy()
        pr['is_client'] = np.where(pr['ticker'] == tkr, tkr, 'Peer')
        pr['ke'] = card['rf'] + pr['beta'] * card['mrp']
        pr['label'] = pr['ticker'] + ' · ' + pr['name']
        order = pr.sort_values('beta', ascending=False)['label'].tolist()
        pbar = alt.Chart(pr).mark_bar(cornerRadius=4, size=22).encode(
            y=alt.Y('label:N', sort=order, title=None, axis=alt.Axis(labelLimit=260)),
            x=alt.X('beta:Q', title='Equity beta vs. SPY (daily, up to 5 years)'),
            color=alt.Color('is_client:N', scale=alt.Scale(domain=[tkr, 'Peer'], range=[ORANGE, BLUE]),
                            legend=alt.Legend(title=None, orient='top')),
            tooltip=[alt.Tooltip('name:N', title='Company'), alt.Tooltip('beta:Q', format='.2f', title='Beta'),
                     alt.Tooltip('ke:Q', format='.2%', title='Implied cost of equity'),
                     alt.Tooltip('start:N', title='Data from')])
        ptxt = alt.Chart(pr).mark_text(align='left', dx=4, color=GRAY).encode(
            y=alt.Y('label:N', sort=order), x='beta:Q', text=alt.Text('beta:Q', format='.2f'))
        one = alt.Chart(pd.DataFrame({'x': [1.0]})).mark_rule(color=GRAY, strokeDash=[4, 4]).encode(x='x:Q')
        st.altair_chart((pbar + ptxt + one).properties(height=300), width='stretch')
        med = pr.loc[pr['ticker'] != tkr, 'beta'].median()
        ke_med = card['rf'] + med * card['mrp']
        st.markdown(f"""
- {tkr}'s beta (**{card['beta']:.2f}**) is {'below' if card['beta'] < med else 'above'} the peer median (**{med:.2f}**).
  The dashed line marks the market (beta = 1).
- Team-owning companies (MSGS, the Braves, Manchester United) cluster at low betas: franchise values and
  long media contracts don't move with the economy. Venue and ticketing businesses (Sphere, Live Nation, MSG Entertainment)
  depend on discretionary spending and run higher.
- With the peer-median beta instead, {tkr}'s cost of equity would be **{ke_med:.2%}** and its WACC
  **{wacc_of(med, card['rf'], card['mrp'], card['rd'], card['tax'], card['w_d']):.2%}**.
""")
        st.caption('Peer betas are raw equity betas, not adjusted for differences in leverage. '
                   'MSGE only has data since its 2023 spin-off.')

# ---------- inputs ----------
with tab_inputs:
    show = inputs.copy()
    show['value'] = show['value'].map(lambda v: f'{v:.2%}')
    st.dataframe(show, width='stretch')
    st.markdown('**Formulas**  \nCost of equity = rf + beta × MRP  \n'
                'WACC = w_e × cost of equity + w_d × rd × (1 − tax)')
    st.dataframe(card.astype(str).to_frame('value'), width='stretch')

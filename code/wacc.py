"""Estimate the client's WACC.

Run from the repo root:   python code/wacc.py
Reads:  inputs/assumptions.csv
Writes: outputs/wacc.csv (one row; the columns are listed in README.md)
        plus extras for the app: outputs/returns.csv, outputs/rolling_beta.csv, outputs/peers.csv

Owner: the developer. Fill in the three TODO functions (your agent can help),
then run it and check the numbers make sense before you open a pull request.
"""
import pandas as pd
import yfinance as yf

CLIENT = 'MSGS'  # Madison Square Garden Sports Corp. (set by the CEO in README.md)
MKT = 'SPY'
YEARS = 5
ROLL = 252  # trading days in the rolling-beta window (about 1 year)
# Listed sports / live-entertainment comparables, for context in the app
PEERS = {'MSGE': 'MSG Entertainment', 'SPHR': 'Sphere Entertainment', 'BATRK': 'Atlanta Braves Holdings',
         'FWONK': 'Formula One Group', 'MANU': 'Manchester United', 'LYV': 'Live Nation'}


def get_returns(ticker, mkt=MKT, years=YEARS):
    """Daily returns for the client and the market over the last `years` years.
    Returns a DataFrame with two columns, named ticker and mkt, and no missing values."""
    end = pd.Timestamp.today().normalize()
    start = end - pd.DateOffset(years=years)
    px = yf.download([ticker, mkt], start=start, end=end, auto_adjust=True, progress=False)['Close']
    assert ticker in px.columns and mkt in px.columns, f'download failed for {ticker} or {mkt}'
    rets = px[[ticker, mkt]].pct_change().dropna()
    assert not rets.empty, 'no returns downloaded'
    return rets


def estimate_beta(rets, ticker, mkt=MKT):
    """Equity beta: cov(stock, market) / var(market)."""
    cov = rets[ticker].cov(rets[mkt])
    return float(cov / rets[mkt].var())


def compute_wacc(beta, a):
    """a is a dict of assumptions: rf, mrp, rd, tax, w_e, w_d.
    Returns a dict with cost_of_equity and wacc (and the inputs), matching the README's columns."""
    cost_of_equity = a['rf'] + beta * a['mrp']
    wacc = a['w_e'] * cost_of_equity + a['w_d'] * a['rd'] * (1 - a['tax'])
    return {'rf': a['rf'], 'mrp': a['mrp'], 'cost_of_equity': cost_of_equity,
            'rd': a['rd'], 'tax': a['tax'], 'w_e': a['w_e'], 'w_d': a['w_d'], 'wacc': wacc}


def rolling_beta(rets, ticker, mkt=MKT, window=ROLL):
    """Beta over a trailing window of daily returns."""
    roll = rets[ticker].rolling(window)
    return (roll.cov(rets[mkt]) / rets[mkt].rolling(window).var()).dropna().rename('beta')


def peer_betas(peers=PEERS, mkt=MKT, years=YEARS):
    """5y daily beta vs. the market for each peer. Peers that fail to download are skipped."""
    rows = []
    for t, name in peers.items():
        try:
            r = get_returns(t, mkt, years)
        except AssertionError:
            print(f'skipping peer {t}: download failed')
            continue
        rows.append({'ticker': t, 'name': name, 'beta': estimate_beta(r, t, mkt), 'start': r.index.min().date()})
    return pd.DataFrame(rows)


if __name__ == '__main__':
    a = pd.read_csv('inputs/assumptions.csv', index_col='item')['value'].to_dict()
    assert abs(a['w_e'] + a['w_d'] - 1) < 1e-6, 'weights must sum to 1'

    rets = get_returns(CLIENT)
    assert len(rets) > 1000, 'expected about 5 years of daily returns'

    beta = estimate_beta(rets, CLIENT)
    out = compute_wacc(beta, a)
    out = {'ticker': CLIENT, 'asof': rets.index.max().date(), 'beta': beta, **out}

    assert 0 < out['wacc'] < 0.25, 'WACC outside 0-25%: check the inputs'
    cols = ['ticker', 'asof', 'beta', 'rf', 'mrp', 'cost_of_equity', 'rd', 'tax', 'w_e', 'w_d', 'wacc']
    pd.DataFrame([out])[cols].to_csv('outputs/wacc.csv', index=False)
    print(pd.DataFrame([out])[cols].T)

    # Extras for the app (the app reads these; it never downloads anything itself)
    rets.rename_axis('date').to_csv('outputs/returns.csv')
    rolling_beta(rets, CLIENT).rename_axis('date').to_csv('outputs/rolling_beta.csv')
    peers = peer_betas()
    peers = pd.concat([pd.DataFrame([{'ticker': CLIENT, 'name': 'Madison Square Garden Sports',
                                      'beta': beta, 'start': rets.index.min().date()}]), peers])
    peers.to_csv('outputs/peers.csv', index=False)
    print(peers)

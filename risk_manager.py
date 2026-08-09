#!/home/hedgefund/.openclaw/workspace/venv/bin/python3
"""
Risk Manager: Deep Rock Holdings
Deterministic Python-only risk engine. No LLM calls.

Runs every 15 min (cron) to update risk_state.json.
Also importable as a module; call eval_trade() before any order.

Rules:
  ATR sizing   : risk 1% of capital per trade, stop at 2x ATR
  Drawdown halt: portfolio drops >10% from peak  -> halt all trading
  VIX multiplier: CALM=1.0, CAUTION=0.75, FEAR=0.50, PANIC=0.0
  Exposure cap : max 70% of live capital in any single asset class
  Position cap : max 25% of allocation per trade, min $10
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

import requests

sys.path.insert(0, '/home/hedgefund/.openclaw/workspace/scripts')
from central_logger import log_error

# ── CONFIG ───────────────────────────────────────────────────────────────────

SCRIPTS_DIR    = '/home/hedgefund/.openclaw/workspace/scripts'
RISK_STATE_FILE   = f'{SCRIPTS_DIR}/risk_state.json'
MARKET_REGIME_FILE = f'{SCRIPTS_DIR}/market_regime.json'

LIVE_BOTS = {
    'DeFi Scalper':   {'start': 160.46, 'asset_class': 'crypto'},
    'ETH Macro (1D)': {'start': 175.00, 'asset_class': 'crypto'},
    'SOL Panic (4H)': {'start': 175.00, 'asset_class': 'crypto'},
}
LIVE_CAPITAL_START = sum(v['start'] for v in LIVE_BOTS.values())  # 510.46

RISK_PER_TRADE_PCT  = 0.01   # 1% of capital per trade
ATR_STOP_MULT       = 2.0    # Stop loss at 2× ATR
MAX_EXPOSURE_PCT    = 1.00   # Each bot has dedicated capital pool; no cross-class cap needed now
# NOTE: re-enable at 0.70 if Supervisor ever dynamically allocates across asset classes
MAX_POSITION_PCT    = 0.25   # Max single position = 25% of available capital
MIN_POSITION_USD    = 10.0
DRAWDOWN_HALT_PCT   = 0.20   # Halt at 20% drawdown from peak (crypto-appropriate)

VIX_SIZING = {'CALM': 1.0, 'CAUTION': 0.75, 'FEAR': 0.50, 'PANIC': 0.0}

CRYPTO_PAIRS = ['BTC-USD', 'ETH-USD', 'SOL-USD']

from config import TELEGRAM_TOKEN, CHAT_ID
TELEGRAM_CHAT  = '1483935983'

logging.basicConfig(
    filename=f'{SCRIPTS_DIR}/risk_manager.log',
    level=logging.INFO,
    format='%(asctime)s [RISK] %(message)s',
)

def log(msg):
    logging.info(msg)
    print(msg)

# ── HELPERS ──────────────────────────────────────────────────────────────────

def load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def send_telegram(msg):
    try:
        requests.post(
            f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
            json={'chat_id': TELEGRAM_CHAT, 'text': msg, 'parse_mode': 'Markdown'},
            timeout=10,
        )
    except Exception:
        pass

# ── VIX / REGIME ─────────────────────────────────────────────────────────────

def get_regime():
    d = load_json(MARKET_REGIME_FILE)
    regime = d.get('regime', 'CALM')
    mult   = d.get('size_multiplier', VIX_SIZING.get(regime, 1.0))
    return regime, d.get('vix'), mult

# ── PORTFOLIO VALUE ───────────────────────────────────────────────────────────

def get_portfolio_value():
    """Sum live bot balances from DB. Falls back to starting capital.
    Uses 'or' pattern to handle explicit None values stored in DB.
    Logs each bot contribution for drawdown diagnostics.
    """
    try:
        from db_manager import DBManager
        db = DBManager()
        total = 0.0
        parts = []
        for bot_name, meta in LIVE_BOTS.items():
            state = db.load_state(bot_name)
            # Use 'or' not .get(key, default): handles explicit None in DB
            bal = float(state.get('balance') or meta['start'])
            total += bal
            parts.append(f'{bot_name}=${bal:.2f}')
        log(f'Portfolio breakdown: {" | ".join(parts)} = ${total:.2f}')
        return total
    except Exception as e:
        log(f'DB read error: {e}, using starting capital fallback')
        return LIVE_CAPITAL_START

def get_exposure(portfolio_value):
    """Returns {'crypto': usd, 'equity': usd} from live bot balances."""
    breakdown = {'crypto': 0.0, 'equity': 0.0}
    try:
        from db_manager import DBManager
        db = DBManager()
        for bot_name, meta in LIVE_BOTS.items():
            state = db.load_state(bot_name)
            bal = float(state.get('balance', meta['start']))
            breakdown[meta['asset_class']] += bal
    except Exception:
        breakdown['crypto'] = portfolio_value  # All live bots are crypto
    return breakdown

# ── ATR ───────────────────────────────────────────────────────────────────────

def get_crypto_atr(pair, period=14):
    """Fetch daily OHLCV from Coinbase Advanced Trade, compute ATR(14)."""
    try:
        end_ts   = int(time.time())
        start_ts = end_ts - (period + 10) * 86400
        r = requests.get(
            f'https://api.exchange.coinbase.com/products/{pair}/candles',
            params={'granularity': 86400, 'start': start_ts, 'end': end_ts},
            headers={'User-Agent': 'DeepRockRiskManager/1.0'},
            timeout=10,
        )
        candles = r.json()
        if not candles or isinstance(candles, dict):
            return None, None
        # [time, low, high, open, close, volume], sort ascending
        candles = sorted(candles, key=lambda x: x[0])
        closes = [float(c[4]) for c in candles]
        highs  = [float(c[2]) for c in candles]
        lows   = [float(c[1]) for c in candles]
        if len(closes) < period + 1:
            return None, closes[-1] if closes else None
        trs = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i]  - closes[i - 1]),
            )
            trs.append(tr)
        atr   = sum(trs[-period:]) / period
        price = closes[-1]
        return round(atr, 4), round(price, 4)
    except Exception as e:
        log(f'Crypto ATR error ({pair}): {e}')
        return None, None

def get_equity_atr(ticker, period=14):
    """Fetch daily OHLCV from yfinance, compute ATR(14)."""
    try:
        import yfinance as yf
        df = yf.download(ticker, period='30d', interval='1d',
                         progress=False, auto_adjust=True)
        if df is None or len(df) < period + 1:
            return None, None
        closes = df['Close'].values.flatten().tolist()
        highs  = df['High'].values.flatten().tolist()
        lows   = df['Low'].values.flatten().tolist()
        trs = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i]  - closes[i - 1]),
            )
            trs.append(tr)
        atr   = sum(trs[-period:]) / period
        price = closes[-1]
        return round(atr, 4), round(price, 4)
    except Exception as e:
        log(f'Equity ATR error ({ticker}): {e}')
        return None, None

# ── TRADE EVALUATION (importable API) ────────────────────────────────────────

def _normalize_symbol(symbol, asset_class):
    """
    Normalize symbol to the format used by ATR lookups.
    ccxt format (ETH/USDC) → Coinbase candle format (ETH-USD)
    """
    if asset_class == 'crypto' and '/' in symbol:
        base = symbol.split('/')[0]
        return f'{base}-USD'
    return symbol

def eval_trade(symbol, direction, capital, asset_class='equity'):
    """
    Evaluate a proposed trade and return sizing recommendation.

    Args:
        symbol     : ticker or pair  (e.g. 'NVDA', 'ETH/USDC', 'SOL-USD')
        direction  : 'BUY' or 'SELL'
        capital    : available capital for this bot/account (USD)
        asset_class: 'equity' or 'crypto'

    Returns dict:
        approved          : bool
        reason            : str
        suggested_size_usd: float
        atr               : float or None
        price             : float or None
        sizing_mult       : float
    """
    result = {
        'symbol': symbol, 'direction': direction,
        'approved': False, 'reason': '',
        'suggested_size_usd': 0.0,
        'atr': None, 'price': None, 'sizing_mult': 1.0,
    }

    # 1. Global halt check
    risk_state = load_json(RISK_STATE_FILE)
    if risk_state.get('halt_active'):
        result['reason'] = f"HALT: {risk_state.get('halt_reason', 'unknown')}"
        return result

    # 2. VIX multiplier
    regime, _, mult = get_regime()
    result['sizing_mult'] = mult
    if mult == 0.0:
        result['reason'] = 'VIX PANIC: no new trades'
        return result

    # 3. ATR sizing
    atr_symbol = _normalize_symbol(symbol, asset_class)
    if asset_class == 'crypto':
        atr, price = get_crypto_atr(atr_symbol)
    else:
        atr, price = get_equity_atr(atr_symbol)

    result['atr']   = atr
    result['price'] = price

    if atr is None or not price:
        # Fallback: flat 5% risk without ATR
        raw = capital * 0.05
        size = max(MIN_POSITION_USD, min(raw * mult, capital * MAX_POSITION_PCT))
        result['approved'] = True
        result['reason']   = 'ATR unavailable: flat 5% risk fallback'
        result['suggested_size_usd'] = round(size, 2)
        return result

    # stop_distance = ATR_STOP_MULT × ATR
    # dollar_risk   = capital × RISK_PER_TRADE_PCT
    # units         = dollar_risk / stop_distance
    # size_usd      = units × price
    stop_distance = ATR_STOP_MULT * atr
    dollar_risk   = capital * RISK_PER_TRADE_PCT
    units         = dollar_risk / stop_distance
    size_usd      = units * price * mult

    size_usd = max(MIN_POSITION_USD, min(size_usd, capital * MAX_POSITION_PCT))

    result['approved']           = True
    result['reason']             = (f'ATR={atr:.4f} stop={stop_distance:.4f} '
                                    f'risk=${dollar_risk:.2f} mult={mult}')
    result['suggested_size_usd'] = round(size_usd, 2)
    return result

# ── DRAWDOWN TRACKING ────────────────────────────────────────────────────────

def check_drawdown(current_value, risk_state):
    """Update peak and set halt_active if drawdown > threshold."""
    peak = risk_state.get('portfolio_peak', current_value)
    if current_value > peak:
        peak = current_value
    risk_state['portfolio_peak'] = round(peak, 2)

    if peak > 0:
        dd_pct = (current_value - peak) / peak
        risk_state['portfolio_drawdown_pct'] = round(dd_pct * 100, 2)

        if dd_pct < -DRAWDOWN_HALT_PCT:
            was_halted = risk_state.get('halt_active', False)
            risk_state['halt_active'] = True
            risk_state['halt_reason'] = (
                f'Drawdown {dd_pct*100:.1f}% exceeds -{DRAWDOWN_HALT_PCT*100:.0f}% limit'
            )
            if not was_halted:
                # 24h cooldown: only log/alert once per day
                last_logged = risk_state.get('halt_last_logged_ts', 0)
                if time.time() - last_logged > 86400:
                    log(f'DRAWDOWN HALT triggered: {dd_pct*100:.1f}%')
                    log_error('RiskManager', f'DRAWDOWN HALT: {dd_pct*100:.1f}% drawdown (peak ${peak:.2f} now ${current_value:.2f})')
                    send_telegram(
                        f'🚨 *RISK MANAGER ? DRAWDOWN HALT*\n'
                        f'Portfolio: ${current_value:.2f} (peak ${peak:.2f})\n'
                        f'Drawdown: {dd_pct*100:.1f}%\nAll trading suspended.'
                    )
                    risk_state['halt_last_logged_ts'] = time.time()
                else:
                    log(f'DRAWDOWN active: {dd_pct*100:.1f}% (cooldown, last logged {(time.time()-last_logged)/3600:.1f}h ago)')
        else:
            # Auto-clear drawdown halts only (not manual halts)
            if risk_state.get('halt_active') and \
               risk_state.get('halt_reason', '').startswith('Drawdown'):
                risk_state['halt_active'] = False
                risk_state['halt_reason'] = None
                log('Drawdown recovered; halt cleared')
    return risk_state

# ── MAIN CRON UPDATE ──────────────────────────────────────────────────────────

def update_risk_state():
    risk_state = load_json(RISK_STATE_FILE, {})

    portfolio_value = get_portfolio_value()
    exposure        = get_exposure(portfolio_value)
    regime, vix_val, mult = get_regime()

    # Drawdown check (updates halt_active if needed)
    risk_state = check_drawdown(portfolio_value, risk_state)

    # Crypto ATRs
    atrs = {}
    for pair in CRYPTO_PAIRS:
        atr, price = get_crypto_atr(pair)
        if atr is not None:
            atrs[pair] = {'atr': atr, 'price': price}

    # Exposure percentages
    c_pct = round(exposure['crypto'] / portfolio_value * 100, 1) if portfolio_value else 0
    e_pct = round(exposure['equity'] / portfolio_value * 100, 1) if portfolio_value else 0

    risk_state.update({
        'timestamp':            datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'portfolio_value_usd':  round(portfolio_value, 2),
        'vix_regime':           regime,
        'vix_value':            vix_val,
        'sizing_multiplier':    mult,
        'crypto_exposure_usd':  round(exposure['crypto'], 2),
        'equity_exposure_usd':  round(exposure['equity'], 2),
        'crypto_exposure_pct':  c_pct,
        'equity_exposure_pct':  e_pct,
        'atrs':                 atrs,
    })

    save_json(RISK_STATE_FILE, risk_state)

    status = '🚨 HALT' if risk_state.get('halt_active') else '✅ OK'
    log(
        f'{status} | portfolio=${portfolio_value:.2f} '
        f'| dd={risk_state.get("portfolio_drawdown_pct", 0):.1f}% '
        f'| regime={regime} mult={mult} '
        f'| crypto={c_pct}%'
    )

if __name__ == '__main__':
    update_risk_state()

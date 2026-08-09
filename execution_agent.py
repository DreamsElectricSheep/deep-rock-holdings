#!/home/hedgefund/.openclaw/workspace/venv/bin/python3
"""
Execution Agent: Deep Rock Holdings
Centralized order routing with risk gate.

Routes to: Coinbase (ccxt) | Jupiter (Solana) | Alpaca (equities, paper)

Usage:
    from execution_agent import execute_trade
    result = execute_trade(
        bot_name='ETH Macro (1D)',
        symbol='ETH/USDC',
        direction='BUY',
        capital=175.0,
        asset_class='crypto',
        exchange_type='coinbase',
    )
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

import requests

sys.path.insert(0, '/home/hedgefund/.openclaw/workspace/scripts')

# ── CONFIG ───────────────────────────────────────────────────────────────────

SCRIPTS_DIR       = '/home/hedgefund/.openclaw/workspace/scripts'
from config import TELEGRAM_TOKEN, CHAT_ID
TELEGRAM_CHAT     = '1483935983'
ALPACA_PAPER_MODE = True   # Keys rotated 2026-05-03. Gate: 10 sessions → canary, 20 sessions → full live (supervisor.py controls)

SOL_MINT  = 'So11111111111111111111111111111111111111112'
USDC_MINT = 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'
JUPITER_QUOTE = 'https://api.jup.ag/swap/v1/quote'
JUPITER_SWAP  = 'https://api.jup.ag/swap/v1/swap'
SLIPPAGE_BPS  = 500

logging.basicConfig(
    filename=f'{SCRIPTS_DIR}/execution_agent.log',
    level=logging.INFO,
    format='%(asctime)s [EXEC] %(message)s',
)

def log(msg):
    logging.info(msg)
    print(msg)

def send_telegram(msg, is_live=False):
    label = '💰 *LIVE FUNDS*' if is_live else '📋 *PAPER*'
    try:
        requests.post(
            f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
            json={'chat_id': TELEGRAM_CHAT, 'text': f'{label}\n{msg}', 'parse_mode': 'Markdown'},
            timeout=10,
        )
    except Exception:
        pass

def _db_log_trade(bot_name, symbol, direction, price, amount):
    try:
        from db_manager import DBManager
        DBManager().log_trade(bot_name, symbol, direction, price, amount)
    except Exception as e:
        log(f'DB trade log error: {e}')

# ── COINBASE (ccxt) ──────────────────────────────────────────────────────────

def _coinbase_keys():
    with open(os.path.expanduser('~/.config/coinbase/keys.json')) as f:
        k = json.load(f)
    return k['api_key'], k['api_secret'].replace('\\n', '\n')

def _execute_coinbase(bot_name, symbol, direction, size_usd, dry_run=False):
    """
    Market order on Coinbase via ccxt.
    symbol: ccxt format, e.g. 'ETH/USDC', 'SOL/USDC', 'BTC/USDC'
    """
    import ccxt
    api_key, api_secret = _coinbase_keys()
    exchange = ccxt.coinbase({
        'apiKey': api_key, 'secret': api_secret, 'enableRateLimit': True,
        'options': {'createMarketBuyOrderRequiresPrice': False},
    })

    try:
        exchange.load_markets()  # Required for amount_to_precision; also validates auth early
    except Exception as e:
        return {'success': False, 'error': f'Coinbase load_markets failed: {e}', 'price': None}

    try:
        ticker = exchange.fetch_ticker(symbol)
        price  = ticker['last']
    except Exception as e:
        return {'success': False, 'error': f'Ticker fetch failed: {e}', 'price': None}

    if not price or price <= 0:
        return {'success': False, 'error': 'Invalid ticker price', 'price': None}

    amount = size_usd / price  # Base currency units (raw, precision applied below)

    if dry_run:
        log(f'[DRY RUN] {direction} {amount:.6f} {symbol} @ ${price:.2f} (${size_usd:.2f})')
        return {'success': True, 'order_id': 'DRY_RUN', 'price': price,
                'size_usd': size_usd, 'amount': amount, 'dry_run': True}

    try:
        if direction == 'BUY':
            # Pass cost in quote currency (USD); Coinbase Advanced Trade uses quote_size for market buys
            order = exchange.create_market_buy_order(symbol, size_usd)
        else:
            # SELL: apply exchange precision to avoid rejection on too many decimals
            precise_amount = float(exchange.amount_to_precision(symbol, amount))
            order = exchange.create_market_sell_order(symbol, precise_amount)

        filled_price  = float(order.get('average') or order.get('price') or price)
        filled_amount = float(order.get('amount') or amount)  # or handles explicit None
        order_id      = str(order.get('id', 'unknown'))

        _db_log_trade(bot_name, symbol, direction, filled_price, filled_amount)
        return {'success': True, 'order_id': order_id,
                'price': filled_price, 'size_usd': filled_price * filled_amount,
                'amount': filled_amount, 'dry_run': False}
    except Exception as e:
        return {'success': False, 'error': str(e), 'price': price}

# ── JUPITER (Solana) ──────────────────────────────────────────────────────────

def _rpc_post(payload, timeout=8):
    for url in ['https://api.mainnet-beta.solana.com', 'https://rpc.ankr.com/solana']:
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            d = r.json()
            if 'result' in d:
                return d
        except Exception:
            continue
    return None

def _load_sol_keypair():
    import ast
    from solders.keypair import Keypair
    wallet_file = os.path.expanduser('~/.config/solana/bot_wallet.json')
    with open(wallet_file) as f:
        data = f.read().strip()
    if data.startswith('['):
        return Keypair.from_bytes(bytes(ast.literal_eval(data)))
    return Keypair.from_base58_string(data)

def _execute_jupiter(bot_name, direction, size_usd, dry_run=False):
    """
    SOL/USDC swap via Jupiter.
    BUY = USDC→SOL  |  SELL = SOL→USDC
    """
    import base64
    from solders.transaction import VersionedTransaction

    # Get SOL price for logging
    try:
        qr = requests.get(
            f'{JUPITER_QUOTE}?inputMint={SOL_MINT}&outputMint={USDC_MINT}'
            f'&amount=1000000000&slippageBps={SLIPPAGE_BPS}',
            timeout=5,
        ).json()
        sol_price = float(qr['outAmount']) / 1_000_000
    except Exception as e:
        return {'success': False, 'error': f'SOL price fetch failed: {e}'}

    if dry_run:
        log(f'[DRY RUN] {direction} ${size_usd:.2f} SOL @ ${sol_price:.2f}')
        return {'success': True, 'order_id': 'DRY_RUN', 'price': sol_price,
                'size_usd': size_usd, 'dry_run': True}

    keypair = _load_sol_keypair()

    if direction == 'BUY':   # USDC → SOL
        in_mint, out_mint = USDC_MINT, SOL_MINT
        amount_units = int(size_usd * 1_000_000)
    else:                    # SOL → USDC
        in_mint, out_mint = SOL_MINT, USDC_MINT
        amount_units = int((size_usd / sol_price) * 1_000_000_000)

    try:
        quote = requests.get(
            f'{JUPITER_QUOTE}?inputMint={in_mint}&outputMint={out_mint}'
            f'&amount={amount_units}&slippageBps={SLIPPAGE_BPS}',
            timeout=10,
        ).json()
        if 'error' in quote:
            return {'success': False, 'error': quote['error']}

        swap = requests.post(JUPITER_SWAP, json={
            'quoteResponse': quote, 'userPublicKey': str(keypair.pubkey()),
            'wrapAndUnwrapSol': True, 'dynamicComputeUnitLimit': True,
            'prioritizationFeeLamports': 'auto',
        }, timeout=15).json()

        if 'swapTransaction' not in swap:
            return {'success': False, 'error': f'Swap API: {swap}'}

        raw_tx  = base64.b64decode(swap['swapTransaction'])
        tx      = VersionedTransaction.from_bytes(raw_tx)
        signed  = VersionedTransaction(tx.message, [keypair])
        encoded = base64.b64encode(bytes(signed)).decode('utf-8')

        resp = requests.post(
            'https://api.mainnet-beta.solana.com',
            json={'jsonrpc': '2.0', 'id': 1, 'method': 'sendTransaction',
                  'params': [encoded, {'encoding': 'base64', 'skipPreflight': False,
                                       'preflightCommitment': 'confirmed', 'maxRetries': 3}]},
            timeout=30,
        ).json()

        if 'result' not in resp:
            return {'success': False, 'error': f'RPC: {resp.get("error")}'}

        tx_id = resp['result']
        _db_log_trade(bot_name, 'SOL/USDC', direction, sol_price, size_usd / sol_price)
        return {'success': True, 'order_id': tx_id, 'price': sol_price,
                'size_usd': size_usd, 'dry_run': False}

    except Exception as e:
        return {'success': False, 'error': str(e)}

# ── ALPACA (equities) ────────────────────────────────────────────────────────

def _execute_alpaca(bot_name, symbol, direction, size_usd, dry_run=False):
    """
    Notional dollar order on Alpaca (paper mode only until keys regenerated).
    symbol: plain ticker, e.g. 'NVDA', 'AAPL', etc.
    """
    if dry_run:
        log(f'[DRY RUN] {direction} ${size_usd:.2f} of {symbol} via Alpaca (paper={ALPACA_PAPER_MODE})')
        return {'success': True, 'order_id': 'DRY_RUN', 'price': None,
                'size_usd': size_usd, 'dry_run': True}

    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
    from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus

    try:
        with open(os.path.expanduser('~/.config/alpaca/keys.json')) as f:
            keys = json.load(f)
        if not keys.get('api_key') or keys.get('api_key') == 'YOUR_KEY':
            return {'success': False, 'error': 'Alpaca keys not configured: regenerate at alpaca.markets'}
    except Exception as e:
        return {'success': False, 'error': f'Alpaca keys load error: {e}'}

    try:
        client = TradingClient(keys['api_key'], keys['api_secret'], paper=ALPACA_PAPER_MODE)

        if direction == 'SELL':
            # For sells, get current position qty and sell all
            try:
                pos = client.get_open_position(symbol)
                qty = float(pos.qty)
                order = client.submit_order(MarketOrderRequest(
                    symbol=symbol, qty=qty, side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY,
                ))
            except Exception:
                # No position, try notional sell anyway
                order = client.submit_order(MarketOrderRequest(
                    symbol=symbol, notional=round(size_usd, 2),
                    side=OrderSide.SELL, time_in_force=TimeInForce.DAY,
                ))
        else:
            order = client.submit_order(MarketOrderRequest(
                symbol=symbol, notional=round(size_usd, 2),
                side=OrderSide.BUY, time_in_force=TimeInForce.DAY,
            ))

        order_id = str(order.id)
        _db_log_trade(bot_name, symbol, direction, None, size_usd)
        return {'success': True, 'order_id': order_id, 'price': None,
                'size_usd': size_usd, 'dry_run': False}

    except Exception as e:
        return {'success': False, 'error': str(e)}

# ── MAIN API ─────────────────────────────────────────────────────────────────

def execute_trade(bot_name, symbol, direction, capital, asset_class, exchange_type, dry_run=False):
    """
    Execute a trade through the appropriate exchange with risk gate.

    Args:
        bot_name     : str   : calling bot name (for DB logging + Telegram)
        symbol       : str   : 'ETH/USDC', 'SOL-USD', 'NVDA', etc.
        direction    : str   : 'BUY' or 'SELL'
        capital      : float : available capital for this bot (USD)
        asset_class  : str   : 'crypto' or 'equity'
        exchange_type: str   : 'coinbase' | 'jupiter' | 'alpaca'
        dry_run      : bool  : if True skip actual exchange calls

    Returns dict:
        success, order_id, price, size_usd,
        approved_by_risk, risk_reason, error, timestamp
    """
    result = {
        'bot_name': bot_name, 'symbol': symbol, 'direction': direction,
        'success': False, 'order_id': None, 'price': None, 'size_usd': 0.0,
        'approved_by_risk': False, 'risk_reason': '', 'error': None,
        'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }

    # ── 1. Risk gate ─────────────────────────────────────────────────────────
    try:
        from risk_manager import eval_trade
        risk = eval_trade(symbol, direction, capital, asset_class)
        result['approved_by_risk'] = risk['approved']
        result['risk_reason']      = risk['reason']
        result['size_usd']         = risk['suggested_size_usd']
        if not risk['approved']:
            result['error'] = f'Risk gate blocked: {risk["reason"]}'
            log(f'[{bot_name}] BLOCKED: {risk["reason"]}')
            return result
    except Exception as e:
        log(f'Risk manager error: {e}, using 5% capital fallback')
        result['size_usd']         = round(capital * 0.05, 2)
        result['approved_by_risk'] = True
        result['risk_reason']      = f'risk_manager unavailable: {e}'

    size_usd = result['size_usd'] or 0.0
    is_live  = exchange_type in ('coinbase', 'jupiter')

    log(f'[{bot_name}] {direction} {symbol} ${size_usd:.2f} via {exchange_type}'
        f'{" [DRY]" if dry_run else ""}')

    # ── 2. Route to exchange ─────────────────────────────────────────────────
    if exchange_type == 'coinbase':
        exec_r = _execute_coinbase(bot_name, symbol, direction, size_usd, dry_run)
    elif exchange_type == 'jupiter':
        exec_r = _execute_jupiter(bot_name, direction, size_usd, dry_run)
    elif exchange_type == 'alpaca':
        exec_r = _execute_alpaca(bot_name, symbol, direction, size_usd, dry_run)
    else:
        result['error'] = f'Unknown exchange_type: {exchange_type}'
        return result

    result.update(exec_r)

    # ── 3. Telegram ──────────────────────────────────────────────────────────
    if result.get('success'):
        if is_live and not dry_run:
            p_str = f'${result["price"]:.2f}' if result.get('price') else 'market'
            send_telegram(
                f'✅ *{bot_name}* {direction} {symbol}\n'
                f'Size: ${size_usd:.2f} @ {p_str}\nOrder: `{result.get("order_id","?")}`',
                is_live=True,
            )
    else:
        send_telegram(
            f'❌ *{bot_name}* {direction} FAILED\n{symbol} ${size_usd:.2f}\n'
            f'`{result.get("error","unknown")}`',
            is_live=is_live,
        )

    log(f'[{bot_name}] {"✅" if result["success"] else "❌"} '
        f'order={result.get("order_id")} err={result.get("error")}')
    return result

if __name__ == '__main__':
    # Self-test: dry-run on all exchange types
    print('=== Execution Agent self-test (dry_run=True) ===')
    tests = [
        ('ETH Macro (1D)', 'ETH/USDC', 'BUY',  175.0, 'crypto', 'coinbase'),
        ('DeFi Scalper',   'SOL-USD',  'BUY',  155.0, 'crypto', 'jupiter'),
        ('Equity Trader',  'NVDA',     'BUY',  500.0, 'equity', 'alpaca'),
    ]
    for t in tests:
        r = execute_trade(*t, dry_run=True)
        ok = '✅' if r['success'] else '❌'
        detail = r.get('error') or f"${r['size_usd']:.2f} risk_ok={r['approved_by_risk']}"
        print(f'{ok} {t[2]} {t[1]} via {t[5]}: {detail}')

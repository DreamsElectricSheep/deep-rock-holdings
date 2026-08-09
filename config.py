#!/usr/bin/env python3
"""
config.py: Deep Rock Holdings shared configuration
Reads sensitive values from ~/.config/deeprock/secrets.json
Never hardcode tokens/passwords in scripts; import from here instead.
"""
import json, os

_SECRETS_FILE = os.path.expanduser('~/.config/deeprock/secrets.json')

def _load_secrets():
    try:
        with open(_SECRETS_FILE) as f:
            return json.load(f)
    except Exception as e:
        raise RuntimeError(f"Cannot load secrets from {_SECRETS_FILE}: {e}")

_s = _load_secrets()
TELEGRAM_TOKEN = _s['telegram_token']
CHAT_ID        = _s['chat_id']
DB_URL         = _s['db_url']  # no fallback -- a missing value should fail loud, not connect somewhere silently

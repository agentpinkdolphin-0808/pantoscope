"""
CSV data engine — pure Python parsing over dummy data CSVs.
No AI calls here; returns plain dicts for Dream and other consumers.
"""
import csv
from datetime import date, datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "dummy data"


def _read(filename):
    with open(DATA_DIR / filename, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _parse_date(s):
    if not s:
        return None
    try:
        return date.fromisoformat(s.strip())
    except ValueError:
        return None


def _days_ago(d: date) -> int:
    return (date.today() - d).days


# -------------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------------

def get_accounts():
    return _read("accounts.csv")


def get_orders():
    return _read("orders.csv")


def get_quotes():
    return _read("quotes.csv")


def get_equipment_quotes():
    return _read("equipment_quotes.csv")


def accounts_by_id():
    return {a["account_id"]: a for a in get_accounts()}


def top_accounts_by_spend(n=200):
    """
    Return top N accounts ranked by total order spend.
    """
    orders = get_orders()
    acc_spend = {}
    for o in orders:
        acc_id = o["account_id"]
        try:
            amt = float(o["total_amount"])
        except (ValueError, KeyError):
            amt = 0.0
        acc_spend[acc_id] = acc_spend.get(acc_id, 0.0) + amt

    # Sort descending
    ranked = sorted(acc_spend.items(), key=lambda x: x[1], reverse=True)[:n]
    acc_map = accounts_by_id()
    result = []
    for acc_id, total in ranked:
        a = acc_map.get(acc_id, {})
        result.append({
            "account_id": acc_id,
            "account_name": a.get("account_name", acc_id),
            "state": a.get("state", ""),
            "account_manager": a.get("account_manager", ""),
            "total_spend": total,
        })
    return result


def last_order_per_account():
    """Map account_id -> most recent order_date."""
    orders = get_orders()
    last = {}
    for o in orders:
        acc_id = o["account_id"]
        d = _parse_date(o["order_date"])
        if d and (acc_id not in last or d > last[acc_id]):
            last[acc_id] = d
    return last


def tardy_accounts(top_accounts, tardy_days=35):
    """
    Return accounts from top_accounts whose last order is > tardy_days ago.
    """
    last_order = last_order_per_account()
    today = date.today()
    result = []
    for a in top_accounts:
        acc_id = a["account_id"]
        lo = last_order.get(acc_id)
        if lo is None:
            days = 9999
        else:
            days = (today - lo).days
        if days > tardy_days:
            result.append({
                **a,
                "last_order_date": lo.isoformat() if lo else None,
                "days_since_order": days,
            })
    return result


def stale_quotes(stale_days=30):
    """
    Return open standard quotes older than stale_days.
    """
    quotes = get_quotes()
    acc_map = accounts_by_id()
    today = date.today()
    result = []
    for q in quotes:
        if q.get("status", "").lower() != "open":
            continue
        created = _parse_date(q.get("created_date"))
        if not created:
            continue
        days_open = (today - created).days
        if days_open > stale_days:
            acc = acc_map.get(q["account_id"], {})
            result.append({
                "quote_id": q["quote_id"],
                "account_id": q["account_id"],
                "account_name": acc.get("account_name", q["account_id"]),
                "amount": float(q.get("amount", 0)),
                "created_date": q.get("created_date"),
                "days_open": days_open,
                "state": acc.get("state", ""),
            })
    return result


def new_equipment_quotes(states, days=7):
    """
    Equipment quotes created within the last `days` days, in the given states.
    'ALL' means no state filter.
    """
    eq_quotes = get_equipment_quotes()
    acc_map = accounts_by_id()
    today = date.today()
    state_list = None if states == "ALL" else [s.strip() for s in states.split(",")]
    result = []
    for q in eq_quotes:
        if q.get("status", "").lower() != "open":
            continue
        created = _parse_date(q.get("created_date"))
        if not created:
            continue
        if (today - created).days > days:
            continue
        acc = acc_map.get(q["account_id"], {})
        acc_state = acc.get("state", "")
        if state_list and acc_state not in state_list:
            continue
        result.append({
            "quote_id": q["quote_id"],
            "account_id": q["account_id"],
            "account_name": acc.get("account_name", q["account_id"]),
            "amount": float(q.get("amount", 0)),
            "created_date": q.get("created_date"),
            "state": acc_state,
        })
    return result


def expired_equipment_quotes(states, expired_days=30):
    """
    Equipment quotes whose expires_date is more than expired_days ago, in given states.
    """
    eq_quotes = get_equipment_quotes()
    acc_map = accounts_by_id()
    today = date.today()
    state_list = None if states == "ALL" else [s.strip() for s in states.split(",")]
    result = []
    for q in eq_quotes:
        expires = _parse_date(q.get("expires_date"))
        if not expires:
            continue
        days_expired = (today - expires).days
        if days_expired <= expired_days:
            continue
        acc = acc_map.get(q["account_id"], {})
        acc_state = acc.get("state", "")
        if state_list and acc_state not in state_list:
            continue
        result.append({
            "quote_id": q["quote_id"],
            "account_id": q["account_id"],
            "account_name": acc.get("account_name", q["account_id"]),
            "amount": float(q.get("amount", 0)),
            "expires_date": q.get("expires_date"),
            "days_expired": days_expired,
            "state": acc_state,
        })
    return result

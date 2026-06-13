"""
Dream engine — pure Python analysis over CSVs.
No AI calls for data work; AI (Haiku) only if a narrative summary is needed.
"""
from datetime import datetime
import data as D


def run_dream(username: str, role: str, states: str, cfg: dict) -> dict:
    tardy_days      = cfg.get("tardy_days_threshold", 35)
    top_n           = cfg.get("top_accounts_count", 200)
    quote_stale     = cfg.get("quote_stale_days", 30)
    new_equip_days  = cfg.get("new_equipment_days", 7)
    equip_expired   = cfg.get("equipment_expired_days", 30)

    top_accs = D.top_accounts_by_spend(n=top_n)

    report = {
        "username": username,
        "role": role,
        "states": states,
        "run_at": datetime.utcnow().isoformat() + "Z",
        "tardy_days": tardy_days,
        "quote_stale_days": quote_stale,
        "new_equipment_days": new_equip_days,
        "equipment_expired_days": equip_expired,
        "top_accounts_analyzed": len(top_accs),
        "tokens_used": 0,
    }

    # Tardy orders (applies to both roles from top accounts)
    report["tardy_accounts"] = D.tardy_accounts(top_accs, tardy_days=tardy_days)

    # Stale standard quotes (internal sees all; external sees their states)
    all_stale = D.stale_quotes(stale_days=quote_stale)
    if role == "internal" or states == "ALL":
        report["stale_quotes"] = all_stale
    else:
        state_list = [s.strip() for s in states.split(",")]
        report["stale_quotes"] = [q for q in all_stale if q.get("state") in state_list]

    # Equipment quotes — new (last N days) in territory
    report["new_equipment_quotes"] = D.new_equipment_quotes(states, days=new_equip_days)

    # Equipment quotes — expired > threshold in territory
    report["expired_equipment_quotes"] = D.expired_equipment_quotes(states, expired_days=equip_expired)

    return report

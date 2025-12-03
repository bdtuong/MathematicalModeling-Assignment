# reachable_marking_optimization.py

import time

def compute_objective(marking, weights):
    val = 0
    for p, tokens in marking.items():
        w = weights.get(p, 0)
        val += w * tokens
    return val


def optimize_over_reachable(net, reachable_markings, weights):
    """
    Returns:
        {
          "status": "OPTIMAL" | "NO_REACHABLE_STATE",
          "best_marking": dict | None,
          "best_value": int | None,
          "runtime_sec": float,
          "num_states": int
        }
    """
    start = time.time()

    if not reachable_markings:
        return {
            "status": "NO_REACHABLE_STATE",
            "best_marking": None,
            "best_value": None,
            "runtime_sec": 0.0,
            "num_states": 0
        }

    best_val = None
    best_mark = None

    for m in reachable_markings:
        val = compute_objective(m, weights)
        if best_val is None or val > best_val:
            best_val = val
            best_mark = m

    end = time.time()

    return {
        "status": "OPTIMAL",
        "best_marking": best_mark,
        "best_value": best_val,
        "runtime_sec": end - start,
        "num_states": len(reachable_markings),
    }

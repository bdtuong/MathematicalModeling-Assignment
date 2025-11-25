# ilp_deadlock.py
import time
import pulp

def build_pre_post(net):
    places = [p["id"] for p in net["places"]]
    transitions = [t["id"] for t in net["transitions"]]

    pre = {t: {} for t in transitions}
    post = {t: {} for t in transitions}

    for arc in net["arcs"]:
        src = arc["src"]
        tgt = arc["target"]
        w = arc.get("weight", 1)

        if src in places and tgt in transitions:
            pre[tgt][src] = w
        elif src in transitions and tgt in places:
            post[src][tgt] = w

    return places, transitions, pre, post


def solve_deadlock_ilp(net, max_firing_bound=None):
    """
    net: dict từ parser.parse_pnml + xử lý trong main.py
    Return:
        {
          "status": str,
          "deadlock_marking": dict | None,
          "runtime_sec": float,
          "num_vars": int,
          "num_constraints": int
        }
    """
    places, transitions, pre, post = build_pre_post(net)

    # Bound firing amount:
    if max_firing_bound is None:
        max_firing_bound = len(places)

    # --- ILP Problem ---
    prob = pulp.LpProblem("Deadlock_Detection", pulp.LpMinimize)

    # Variable for arking m_p
    m = {
        p: pulp.LpVariable(f"m_{p}", lowBound=0, upBound=1, cat="Binary")
        for p in places
    }

    # Variable for firing sigma_t
    sigma = {
        t: pulp.LpVariable(f"sigma_{t}", lowBound=0, upBound=max_firing_bound, cat="Integer")
        for t in transitions
    }

    # To minimize total firing attempts
    prob += pulp.lpSum(sigma[t] for t in transitions)

    # Find M0 in net["places"]
    M0 = {p["id"]: p["m0"] for p in net["places"]}


    for p in places:
        inflow = pulp.lpSum(post[t].get(p, 0) * sigma[t] for t in transitions)
        outflow = pulp.lpSum(pre[t].get(p, 0) * sigma[t] for t in transitions)

        prob += (
            m[p] == M0[p] + inflow - outflow,
            f"state_eq_{p}"
        )

    # --- Ràng buộc deadlock: với mỗi transition, tổng m_p <= |Pre(t)| - 1 ---
    for t in transitions:
        pre_places = list(pre[t].keys())
        if not pre_places:
            # Nếu có transition không có input thì thực tế luôn enabled.
            # Tùy bạn: có thể để net "không deadlock", hoặc bỏ qua ràng buộc.
            continue

        prob += (
            pulp.lpSum(m[p] for p in pre_places) <= len(pre_places) - 1,
            f"deadlock_{t}"
        )

    # --- Giải ILP ---
    start = time.time()
    status = prob.solve()        # dùng solver mặc định của PuLP
    end = time.time()

    status_str = pulp.LpStatus[status]

    result = {
        "status": status_str,
        "deadlock_marking": None,
        "runtime_sec": end - start,
        "num_vars": len(prob.variables()),
        "num_constraints": len(prob.constraints),
    }

    if status_str not in ("Optimal", "Feasible"):
        return result

    # Lấy marking
    marking = {p: int(round(m[p].value())) for p in places}
    result["deadlock_marking"] = marking

    return result

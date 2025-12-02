import time
from collections import defaultdict, deque

#Have to install pulp
# Common helpers (same net as ILP)

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

def get_M0(net):
    return {p["id"]: int(p.get("m0", 0)) for p in net["places"]}

def is_safe_net(pre, post):
    for t in pre:
        for _, w in pre[t].items():
            if w not in (0, 1): return False
    for t in post:
        for _, w in post[t].items():
            if w not in (0, 1): return False
    return True

#1) BDD MODE (if available) 
def _try_import_bdd():
    try:
        from dd.autoref import BDD
        return BDD
    except Exception:
        return None

class _BDDSolver:
    def __init__(self, net):
        self.net = net
        self.places, self.transitions, self.pre, self.post = build_pre_post(net)
        if not is_safe_net(self.pre, self.post):
            raise ValueError("Non-safe net (arc weight >1). BDD mode assumes 0/1 tokens.")

        BDD = _try_import_bdd()
        if BDD is None:
            raise ImportError("dd not installed")

        self.bdd = BDD()
        order = [f"x_{p}" for p in self.places] + [f"x_{p}_n" for p in self.places]
        self.bdd.declare(*order)
        self.vars = {p: f"x_{p}" for p in self.places}
        self.vars_n = {p: f"x_{p}_n" for p in self.places}

        self.enabled_t = {}
        self.rel_t = {}
        self._build_transitions()

        self.R_any = self.bdd.false
        for t in self.transitions:
            self.R_any = self.bdd.apply("or", self.R_any, self.rel_t[t])

        self.rename = {self.vars_n[p]: self.vars[p] for p in self.places}

    def lit(self, var, val):
        v = self.bdd.var(var)
        return v if val else self.bdd.apply("not", v)

    def _eq(self, v, w):
        # v == w  <=> (v & w) | (~v & ~w)
        a = self.bdd.apply("and", v, w)
        b = self.bdd.apply("and", self.bdd.apply("not", v), self.bdd.apply("not", w))
        return self.bdd.apply("or", a, b)

    def _enabled(self, t):
        if not self.pre[t]:
            return self.bdd.true
        node = self.bdd.true
        for p in self.pre[t]:
            node = self.bdd.apply("and", node, self.bdd.var(self.vars[p]))
        return node

    def _frame_place(self, p, t):
        preP  = p in self.pre[t]
        postP = p in self.post[t]
        if preP and not postP:
            return self.lit(self.vars_n[p], False)      # consume -> 0
        elif postP and not preP:
            return self.lit(self.vars_n[p], True)       # produce -> 1
        else:
            return self._eq(self.bdd.var(self.vars[p]), self.bdd.var(self.vars_n[p]))

    def _build_transitions(self):
        for t in self.transitions:
            en = self._enabled(t)
            frame = self.bdd.true
            for p in self.places:
                frame = self.bdd.apply("and", frame, self._frame_place(p, t))
            self.enabled_t[t] = en
            self.rel_t[t] = self.bdd.apply("and", en, frame)

    def _exist_cur(self, node):
        for p in self.places:
            node = self.bdd.quantify(node, {self.vars[p]}, forall=False)
        return node

    def _rename_next_to_cur(self, node):
        return self.bdd.let(self.rename, node)

    def initial_node(self):
        M0 = get_M0(self.net)
        node = self.bdd.true
        for p in self.places:
            node = self.bdd.apply("and", node, self.lit(self.vars[p], bool(M0[p])))
        return node

    def post(self, S):
        conj = self.bdd.apply("and", S, self.R_any)
        nxt = self._exist_cur(conj)
        return self._rename_next_to_cur(nxt)

    def reachable(self):
        S = self.initial_node()
        while True:
            newS = self.bdd.apply("or", S, self.post(S))
            if newS == S:
                break
            S = newS
        return S

    def deadlock_set(self, Reach):
        no_en = self.bdd.true
        for t in self.transitions:
            no_en = self.bdd.apply("and", no_en, self.bdd.apply("not", self.enabled_t[t]))
        return self.bdd.apply("and", Reach, no_en)

    def sample(self, node, limit=10):
        res = []
        for assign in self.bdd.sat_iter(node):
            m = {p: int(assign.get(self.vars[p], 0)) for p in self.places}
            res.append(m)
            if len(res) >= limit: break
        return res

    def solve(self, sample_limit=10):
        Reach = self.reachable()
        Dead  = self.deadlock_set(Reach)
        listed = self.sample(Dead, sample_limit)
        try:
            reach_cnt = int(Reach.count(len(self.places)))
        except Exception:
            reach_cnt = None
        return {
            "status": "NO_DEADLOCK" if not listed else "OK",
            "deadlock_markings": listed,
            "num_deadlocks_listed": len(listed),
            "reachable_states_est": reach_cnt,
            "bdd_nodes": self.bdd.dag_size(Reach),
        }

# 2) FALLBACK EXPLICIT BFS MODE 
# Works for safe nets (0/1). No external libs needed.

def _enabled_explicit(M, pre_t):
    # transition enabled iff all its preset places have token==1
    for p, w in pre_t.items():
        if w != 1:   # safe net only
            return False
        if M.get(p, 0) < 1:
            return False
    return True

def _fire_explicit(M, pre_t, post_t):
    # produce next marking for safe net (0/1)
    N = dict(M)
    for p in pre_t:
        N[p] = 0
    for p in post_t:
        N[p] = 1
    return N

def _to_tuple(M, places):
    return tuple(int(M.get(p,0)) for p in places)

def _from_tuple(tpl, places):
    return {p: tpl[i] for i,p in enumerate(places)}

def explicit_bfs_deadlocks(net, pre, post, limit=10):
    places = [p["id"] for p in net["places"]]
    M0 = get_M0(net)

    seen = set()
    q = deque()

    t0 = _to_tuple(M0, places)
    q.append(t0)
    seen.add(t0)

    deadlocks = []

    while q:
        cur_t = q.popleft()
        M = _from_tuple(cur_t, places)

        # successors
        succ = []
        for t in post.keys():
            if _enabled_explicit(M, pre[t]):
                N = _fire_explicit(M, pre[t], post[t])
                succ.append(_to_tuple(N, places))

        if not succ:
            deadlocks.append(M)
            if len(deadlocks) >= limit:
                break
        else:
            for n in succ:
                if n not in seen:
                    seen.add(n)
                    q.append(n)

    return deadlocks, len(seen)

# PUBLIC API 
def solve_deadlock_bdd(net, sample_limit=10):
    """
    Returns:
        {
          "status": "OK" | "NO_DEADLOCK",
          "deadlock_markings": [ {place:int, ...}, ... ],
          "num_deadlocks_listed": int,
          "reachable_states_est": int | None,
          "bdd_nodes": int | None,
          "runtime_sec": float
        }
    """
    start = time.time()

    # Try BDD mode first
    try:
        BDD = _try_import_bdd()
        if BDD is not None and is_safe_net(*build_pre_post(net)[2:4]):
            solver = _BDDSolver(net)
            out = solver.solve(sample_limit)
            mode = "BDD"
            bdd_nodes = out["bdd_nodes"]
            reach_est = out["reachable_states_est"]
            listed = out["deadlock_markings"]
            status = out["status"]
        else:
            raise Exception("Use explicit")
    except Exception:
        # Fallback explicit BFS (safe net assumption)
        places, transitions, pre, post = build_pre_post(net)
        if not is_safe_net(pre, post):
            raise ValueError("Non-safe net (arc weight >1) and 'dd' not available. "
                             "Please install 'dd' or provide a safe net.")
        listed, reach_cnt = explicit_bfs_deadlocks(net, pre, post, limit=sample_limit)
        mode = "EXPLICIT"
        bdd_nodes = None
        reach_est = reach_cnt
        status = "NO_DEADLOCK" if not listed else "OK"

    end = time.time()
    return {
        "status": status,
        "deadlock_markings": listed,
        "num_deadlocks_listed": len(listed),
        "reachable_states_est": reach_est,
        "bdd_nodes": bdd_nodes,
        "runtime_sec": end - start,
        "mode": mode,
    }

# Quick run
if __name__ == "__main__":
    # tiny safe PN
    net = {
        "places": [{"id": "p1", "m0": 1}, {"id": "p2", "m0": 0}],
        "transitions": [{"id": "t1"}],
        "arcs": [
            {"src": "p1", "target": "t1", "weight": 1},
            {"src": "t1", "target": "p2", "weight": 1},
        ],
    }
    print(solve_deadlock_bdd(net))

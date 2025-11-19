import json
from dd.autoref import BDD
from pympler import asizeof
import time
import csv
import os

def run_symbolic_reachability(net, fname, csv_file=None):
    """
    Run symbolic reachability using BDD for a given net.
    Optionally, load explicit markings from CSV to compute memory/state compression.
    Returns a dict with results.
    """
    result = {}

    print("\n=== Running symbolic reachability on:", fname,"===")

    # ----- Extract places -----
    places = [p["id"] for p in net["places"]]
    initial_marking = {p: p_m["m0"] for p, p_m in zip(places, net["places"])}

    # ----- Transitions -----
    trans_ids = [t["id"] for t in net["transitions"]]
    transitions = {t: {"pre": [], "post": []} for t in trans_ids}

    # Extract arcs
    for arc in net["arcs"]:
        src = arc["src"]
        tgt = arc["target"]
        if src in places and tgt in trans_ids:
            transitions[tgt]["pre"].append(src)
        if src in trans_ids and tgt in places:
            transitions[src]["post"].append(tgt)

    # ----- BDD setup -----
    bdd = BDD()
    for p in places:
        bdd.declare(p)
        bdd.declare(p + "'")

    def encode_marking(m):
        node = bdd.true
        for p, v in m.items():
            node &= bdd.var(p) if v == 1 else ~bdd.var(p)
        return node

    Reach = encode_marking(initial_marking)
    Frontier = Reach

    # Build transition relations
    def build_transition_relation(pre, post):
        R = bdd.true
        for p in pre:
            R &= bdd.var(p)
        for p in pre:
            R &= ~bdd.var(p + "'")
        for p in post:
            R &= bdd.var(p + "'")
        for p in places:
            if p not in pre and p not in post:
                same = (bdd.var(p) & bdd.var(p+"'")) | (~bdd.var(p) & ~bdd.var(p+"'"))
                R &= same
        return R

    transition_relations = [build_transition_relation(defs["pre"], defs["post"])
                            for t, defs in transitions.items()]

    # Image operator
    current_vars = set(places)
    rename_map = {p+"'": p for p in places}

    def image(X):
        res = bdd.false
        for R in transition_relations:
            part = bdd.exist(current_vars, X & R)
            res |= part
        res = bdd.let(rename_map, res)
        return res

    # ----- Fixed-point iteration -----
    start_time = time.time()
    iteration = 0
    while Frontier != bdd.false:
        print(f"[Iteration {iteration}] Frontier BDD nodes = {Frontier.dag_size}")
        New = image(Frontier) & ~Reach
        Reach |= New
        Frontier = New
        iteration += 1
    end_time = time.time()
    bdd_time = end_time - start_time

    # ----- Compute BDD statistics -----
    try:
        total_bdd = Reach.count(len(places))
    except Exception:
        total_bdd = None

    bdd_mem = asizeof.asizeof(Reach)

    result["bdd"] = {
        "num_reachable_states": int(total_bdd) if total_bdd is not None else None,
        "bdd_memory_bytes": bdd_mem,
        "execution_time_sec": round(bdd_time, 6),
        "bdd_nodes": Reach.dag_size
    }

    # ----- Optional explicit CSV -----
    if csv_file and os.path.exists(csv_file):
        explicit_states = []
        with open(csv_file, newline='') as f:
            reader = csv.DictReader(f, delimiter=',')
            if reader.fieldnames is None:
                raise ValueError(f"CSV header not found in {csv_file}")
            token_columns = [p for p in reader.fieldnames if p not in ["State_ID", "Depth"]]
            for row in reader:
                explicit_states.append([int(row[p]) for p in token_columns])

        explicit_mem = asizeof.asizeof(explicit_states)
        explicit_total = len(explicit_states)

        result["explicit"] = {
            "num_reachable_states": explicit_total,
            "memory_bytes": explicit_mem,
            "state_compression_ratio": explicit_total / total_bdd if total_bdd else None,
            "memory_compression_ratio": explicit_mem / bdd_mem if bdd_mem else None
        }
    else:
        result["explicit"] = None

    return result

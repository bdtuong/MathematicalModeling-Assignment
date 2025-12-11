# Petri Net Analysis Toolkit (Mathematical Modeling Assignment)

A small toolkit to analyze safe Petri nets from PNML files. It parses PNML, builds the net, and performs:
- Explicit-state reachability via BFS with depth tracking
- Symbolic reachability using BDDs (if `dd` is installed)
- Deadlock detection via
  - Integer Linear Programming (ILP) using PuLP
  - BDD-based method (with fallback to explicit search for safe nets)
- Simple optimization over reachable markings (linear objective over tokens)

Outputs are written next to each PNML input as JSON/CSV with stats and reachability data.


## Repository structure
- src/
  - parser.py — PNML parser (1-safe check, IDs validation)
  - bfs.py — explicit BFS over markings with depth
  - bdd_reachability.py — symbolic reachability using BDDs; compares memory vs explicit CSV
  - ilp_deadlock.py — ILP model to find a deadlock marking
  - bdd_deadlock.py — BDD-based (or explicit) deadlock detection for safe nets
  - reachable_marking_optimization.py — scan reachable markings to maximize a weighted sum
  - main.py — end-to-end pipeline and CLI
- examples/ — sample PNMLs and generated outputs (.json, .csv, .png)
- figures/ — images for examples
- tests/ — basic test cases


## Requirements
- Python 3.9+
- Recommended packages:
  - rich
  - dd (for BDDs)
  - pympler (for memory measurement)
  - pulp (for ILP)

Install dependencies:

```
pip install rich dd pympler pulp
```


## Usage
Run the pipeline on one or more PNML files. For each input `X.pnml`, the tool writes:
- `X_net.json` — parsed Petri net
- `X_reachability.csv` — reachable markings with BFS depth
- `X_stats.json` — summary stats including BFS, BDD, ILP, and optimization

Command:

```
python src/main.py examples/sample_01.pnml examples/sample_02.pnml examples/sample_03.pnml
```

You can pass any PNML path(s). The pipeline normalizes arc inscription fields to a `weight` attribute and forces the initial marking m0 = 1 for places whose IDs look like starts (contain "start" or are one of p0, line1_in, line2_in). This overrides PNML if present, as implemented in src/main.py.


## What the pipeline does
1) Parse PNML
- Validates IDs and arcs
- Enforces 1-safe initial tokens
- Produces `{places, transitions, arcs, M0}` and basic counts

2) Quick transition simulation
- Prints whether each transition is enabled and the marking after firing once (when enabled)

3) BFS reachability (explicit)
- Explores all reachable markings and records the shortest-path depth for each
- Saves `*_reachability.csv` with columns: `State_ID, Depth, <place ids...>`

4) Optimization over reachable markings
- Maximizes a weighted sum over tokens; by default, places whose IDs include `collector`, `end`, or `qc` get weight 5, others weight 1
- Reports best marking and objective

5) Symbolic reachability (BDD)
- Builds a Boolean BDD model for safe nets
- Reports estimated number of reachable states, BDD nodes, time, and memory footprint
- If CSV is present, compares explicit memory vs BDD memory

6) Deadlock detection
- BDD-based method (safe nets), falls back to explicit search if BDD lib is missing
- ILP model via PuLP using the state equation with deadlock constraints. The firing bound is set to the BFS max depth

All results are summarized into `*_stats.json`.


## Example outputs
Examples are provided under `examples/`:
- `sample_01.pnml`, `sample_02.pnml`, `sample_03.pnml`
- After running, you will see corresponding `*_net.json`, `*_reachability.csv`, and `*_stats.json` files created


## Notes and assumptions
- Nets are assumed 1-safe; parser raises on places with initial tokens > 1
- Arc inscription is treated as non-negative integer weight (defaults to 1)
- BDD-based analyses assume safe nets (0/1)
- ILP uses a simple objective (minimize total firing) and encodes deadlock as “each transition has at least one unmarked input place”


## Troubleshooting
- Module not found: install extras via `pip install dd pympler pulp rich`
- BDD warnings or fallbacks: if `dd` is not installed or the net is not safe, BDD mode is skipped and explicit search is used where applicable
- Large nets: explicit BFS can be expensive; prefer BDD mode for large safe nets
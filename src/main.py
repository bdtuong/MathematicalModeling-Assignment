import sys
import json
import csv
import time
from parser import parse_pnml
from rich import print_json
from rich.console import Console
from pathlib import Path
from transition import enabled, fire
from bfs import bfs_reachable_markings_with_depth
from bdd_reachability import run_symbolic_reachability
from ilp_deadlock import solve_deadlock_ilp
from bdd_deadlock import solve_deadlock_bdd
from reachable_marking_optimization import optimize_over_reachable


console = Console()

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 src/main.py <pnml_file>")
        sys.exit(1)
   
    for pnml_path in sys.argv[1:]:
        pnml_file = Path(pnml_path)
        base_name = pnml_file.stem
        output_json = pnml_file.with_name(f"{base_name}_net.json")
        output_csv = pnml_file.with_name(f"{base_name}_reachability.csv")
        output_stats = pnml_file.with_name(f"{base_name}_stats.json")
        
        console.print(f"\n[bold green]Processing:[/bold green] {pnml_file}")
        try:
            result = parse_pnml(str(pnml_file))

            # --- RENAME 'ins' → 'weight' ---
            for arc in result["arcs"]:
                if 'ins' in arc:
                    arc['weight'] = arc.pop('ins')

            # --- Auto adjustment m0 ---
            for place in result["places"]:
                pid = place["id"].lower()
                if "start" in pid or pid in ("p0", "line1_in", "line2_in"):
                    place["m0"] = 1
                else:
                    place["m0"] = place.get("m0", 0)
            result["M0"] = [p["m0"] for p in result["places"]]

            print_json(data=result)
            with open(output_json, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            console.print(f"[bold blue]Exported Petri net to:[/bold blue] {output_json}")

            # --- Simulate fire ---
            marking = {p["id"]: p["m0"] for p in result["places"]}
            for t in result["transitions"]:
                transition = t["id"]
                if enabled(result["transitions"], result["places"], result["arcs"], marking, transition):
                    print(f"Transition {transition} is enabled.")
                    new_marking = fire(result["transitions"], result["places"], result["arcs"], marking, transition)
                    print("New marking after firing:", new_marking)
                else:
                    print(f"Transition {transition} is not enabled.")

            # --- BFS với đo thời gian, depth, số trạng thái ---
            console.print("\n[bold yellow]Running BFS to find all reachable markings...[/bold yellow]")
            start_time = time.time()

            # Gọi BFS với depth tracking
            reachable_with_depth = bfs_reachable_markings_with_depth(result)
            reachable_markings = reachable_with_depth["markings"]  # list dict
            depth_map = reachable_with_depth["depth"]              # dict: marking_str -> depth

            end_time = time.time()
            bfs_time = end_time - start_time
            num_states = len(reachable_markings)

            # --- Optimization over reachable markings ---
            console.print("\n[bold yellow]Running optimization over reachable markings (Task 5)...[/bold yellow]")

            weights = {p["id"]: 1 for p in result["places"]}
            for p in result["places"]:
                pid = p["id"].lower()
                #print(pid)
                if "collector" in pid or "end" in pid or "qc" in pid:
                    weights[p["id"]] = 5
                else:
                    weights[p["id"]] = 1

            opt_result = optimize_over_reachable(result, reachable_markings, weights)

            console.print(f"[bold white]Optimization status:[/bold white] {opt_result['status']}")
            if opt_result["status"] == "OPTIMAL":
                console.print(f"  • Best objective value: {opt_result['best_value']}")
                console.print(f"  • Best marking:")
                console.print(f"    {opt_result['best_marking']}")
                console.print(f"  • Optimization runtime: {opt_result['runtime_sec']:.6f}s")
            else:
                console.print("[bold red]No reachable state found for optimization.[/bold red]")


            # --- Lưu CSV: trạng thái + depth ---
            with open(output_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["State_ID", "Depth"] + [p["id"] for p in result["places"]])
                for i, mark in enumerate(reachable_markings):
                    state_id = f"S{i}"
                    depth = depth_map.get(json.dumps(mark, sort_keys=True), 0)
                    row = [state_id, depth] + [mark.get(p["id"], 0) for p in result["places"]]
                    writer.writerow(row)
            console.print(f"[bold cyan]Saved reachability graph to:[/bold cyan] {output_csv}")

            # --- Lưu stats JSON (dùng cho so sánh BDD) ---
            stats = {
                "file": str(pnml_file),
                "num_places": len(result["places"]),
                "num_transitions": len(result["transitions"]),
                "num_arcs": len(result["arcs"]),
                "initial_marking": result["M0"],
                "bfs": {
                    "num_reachable_states": num_states,
                    "execution_time_sec": round(bfs_time, 6),
                    "max_depth": max(depth_map.values()) if depth_map else 0
                }
            }
            # --- Run BDD symbolic reachability after BFS ---
            console.print("\n[bold yellow]Running BDD symbolic reachability...[/bold yellow]")
            start_bdd = time.time()
            #total_bdd, bdd_mem = run_symbolic_reachability(result, str(pnml_file))
            bdd_result = run_symbolic_reachability(result, str(pnml_file), csv_file=str(output_csv))
            end_bdd = time.time()
            bdd_time = end_bdd - start_bdd

                        # --- BDD-based Deadlock detection ---
            console.print("\n[bold yellow]Running BDD-based deadlock detection...[/bold yellow]")

            bdd_deadlock = solve_deadlock_bdd(result, sample_limit=5)

            console.print(f"[bold white]BDD-deadlock status:[/bold white] {bdd_deadlock['status']}")
            console.print(f"  • mode: {bdd_deadlock['mode']}")
            console.print(f"  • runtime: {bdd_deadlock['runtime_sec']:.6f}s")
            console.print(f"  • reachable states (est): {bdd_deadlock['reachable_states_est']}")
            console.print(f"  • BDD nodes (if BDD mode): {bdd_deadlock['bdd_nodes']}")

            if bdd_deadlock["deadlock_markings"]:
                console.print("[bold green]Some deadlock markings (BDD):[/bold green]")
                for m in bdd_deadlock["deadlock_markings"]:
                    console.print(f"    {m}")
            else:
                console.print("[bold cyan]No deadlock reachable (BDD / explicit mode).[/bold cyan]")

        
            # --- ILP Deadlock detection ---
            console.print("\n[bold yellow]Running ILP deadlock detection...[/bold yellow]")

            # Bound sigma_t with max depth from BFS
            max_depth = stats["bfs"]["max_depth"]

            ilp_result = solve_deadlock_ilp(result, max_firing_bound=max_depth)

            console.print(f"[bold white]ILP status:[/bold white] {ilp_result['status']}")
            if ilp_result["deadlock_marking"] is not None:
                console.print(f"[bold green]Deadlock marking (ILP):[/bold green] {ilp_result['deadlock_marking']}")
            else:
                console.print("[bold red]No deadlock found by ILP (or model infeasible).[/bold red]")

            console.print(f"  • ILP runtime: {ilp_result['runtime_sec']:.6f}s")
            console.print(f"  • #vars: {ilp_result['num_vars']}")
            console.print(f"  • #constraints: {ilp_result['num_constraints']}")

            # Write into stats.json
            stats["ilp"] = {
                "status": ilp_result["status"],
                "deadlock_marking": ilp_result["deadlock_marking"],
                "runtime_sec": round(ilp_result["runtime_sec"], 6),
                "num_vars": ilp_result["num_vars"],
                "num_constraints": ilp_result["num_constraints"]
            }

             # Write BDD deadlock stats
            stats["bdd_deadlock"] = {
            "status": bdd_deadlock["status"],
            "mode": bdd_deadlock["mode"],
            "runtime_sec": round(bdd_deadlock["runtime_sec"], 6),
            "num_deadlocks_listed": bdd_deadlock["num_deadlocks_listed"],
            "reachable_states_est": bdd_deadlock["reachable_states_est"],
            "bdd_nodes": bdd_deadlock["bdd_nodes"],
            }

            stats["opt"] = {
                "status": opt_result["status"],
                "objective_weights": weights,
                "best_value": opt_result["best_value"],
                "best_marking": opt_result["best_marking"],
                "runtime_sec": round(opt_result["runtime_sec"], 6),
                "num_states": opt_result["num_states"]
            }

            with open(output_stats, "w", encoding="utf-8") as f:
                json.dump(stats, f, indent=2)
            console.print(f"[bold magenta]Updated statistics (with ILP) to:[/bold magenta] {output_stats}")

            # --- Add BDD results to stats ---
            stats["bdd"] = {
                "num_reachable_states": bdd_result["bdd"]["num_reachable_states"],
                "bdd_memory_bytes": bdd_result["bdd"]["bdd_memory_bytes"],
                "execution_time_sec": bdd_result["bdd"]["execution_time_sec"],
                "bdd_nodes": bdd_result["bdd"]["bdd_nodes"]
            }

            # --- Save stats JSON after BDD ---
            with open(output_stats, "w", encoding="utf-8") as f:
                json.dump(stats, f, indent=2)
            console.print(f"[bold magenta]Saved statistics to:[/bold magenta] {output_stats}")

            # --- In tóm tắt ---
            console.print(f"\n[bold white]Summary:[/bold white]")
            console.print(f"  • Reachable states (BFS): {num_states}")
            console.print(f"  • BFS time: {bfs_time:.6f}s")
            console.print(f"  • Max depth: {stats['bfs']['max_depth']}")
            console.print(f"  • Reachable states (BDD): {bdd_result['bdd']['num_reachable_states']}")
            console.print(f"  • BDD memory (bytes): {bdd_result['bdd']['bdd_memory_bytes']}")
            console.print(f"  • BDD nodes: {bdd_result['bdd']['bdd_nodes']}")
            console.print(f"  • BDD time: {bdd_result['bdd']['execution_time_sec']:.6f}s")
            console.print(f"  • Optimization status: {opt_result['status']}")
            if opt_result["status"] == "OPTIMAL":
                console.print(f"  • Best objective value: {opt_result['best_value']}")

        except Exception as e:
            console.print(f"[bold red]Error processing {pnml_file}:[/bold red] {e}")
            continue

if __name__ == "__main__":
    main()
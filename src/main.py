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

        except Exception as e:
            console.print(f"[bold red]Error processing {pnml_file}:[/bold red] {e}")
            continue

if __name__ == "__main__":
    main()
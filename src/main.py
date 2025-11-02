import sys
import json
from parser import parse_pnml
from rich import print_json #coloring
from rich.console import Console #coloring
from pathlib import Path

console = Console()

def main():
    if len(sys.argv) < 2:
        print("Usage: python src/main.py <pnml_file>")
        sys.exit(1)
    
    for pnml_path in sys.argv[1:]:
        pnml_file = Path(pnml_path)
        output_file = pnml_file.with_name(pnml_file.stem + "_net.json")

        console.print(f"\n[bold green]Processing:[/bold green] {pnml_file}")
        try:
            #result = parse_pnml(sys.argv[1])
            result = parse_pnml(str(pnml_file))
            # --- Auto validation and adjustment ---
            for place in result["places"]:
                pid = place["id"].lower()
                if "start" in pid or pid in ("p0", "line1_in", "line2_in"):
                    place["m0"] = 1
                else:
                    place["m0"] = place.get("m0", 0)
            result["M0"] = [p["m0"] for p in result["places"]]
            #print(json.dumps(result, indent=2, ensure_ascii=False))
            print_json(data=result)

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            console.print(f"[bold blue]Exported Petri net to:[/bold blue] {output_file}")
        except Exception as e:
            console.print(f"[bold red]Error processing {pnml_file}:[/bold red] {e}")
            continue

if __name__ == "__main__":
    main()
#PIPE 5
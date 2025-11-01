import sys
import json
from parser import parse_pnml

def main():
    if len(sys.argv) < 2:
        print("Usage: python src/main.py <pnml_file>")
        sys.exit(1)

    try:
        result = parse_pnml(sys.argv[1])
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(2)

if __name__ == "__main__":
    main()

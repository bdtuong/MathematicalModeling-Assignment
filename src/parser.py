import xml.etree.ElementTree as ET
from pathlib import Path

def parse_pnml(file_path: str):
    """Parse PNML file (simplified: no name, no warnings)."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    tree = ET.parse(path) # XML parse file
    root = tree.getroot() # take root element such as <pnml>

    places, transitions, arcs = [], [], [] # Initialize lists

    # Parse every <net> in file
    for net in root.findall(".//net"):
        # Parse places
        for place in net.findall(".//place"):
            pId = place.get("id")
            marking_text = place.findtext("initialMarking/text", default="0").strip()
            try:
                m0 = int(marking_text)
                if m0 < 0:
                    raise ValueError
            except ValueError:
                raise ValueError(f"Invalid initialMarking for place {pId}: {marking_text}")
            places.append({"id": pId, "m0": m0})

        # Parse transitions 
        for transition in net.findall(".//transition"):
            tId = transition.get("id")
            transitions.append({"id": tId})

        # Parse arcs 
        for arc in net.findall(".//arc"):
            aId = arc.get("id")
            src = arc.get("source")
            target = arc.get("target")
            text_val = arc.findtext("inscription/text", default="1").strip()
            try:
                ins = int(text_val)
                if ins <= 0:
                    raise ValueError
            except ValueError:
                ins = 1
            arcs.append({"id": aId, "src": src, "target": target, "ins": ins})

    # Validation 
    place_ids = {p["id"] for p in places}
    trans_ids = {t["id"] for t in transitions}
    node_ids = place_ids | trans_ids

    # Check duplicate IDs
    all_ids = [p["id"] for p in places] + [t["id"] for t in transitions]
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("Duplicate IDs detected")

    # Check arc validity
    for arc in arcs:
        src, target = arc["src"], arc["target"]
        if src not in node_ids or target not in node_ids:
            raise ValueError(f"Arc {arc['id']} references unknown node")
        if (src in place_ids and target in place_ids) or (src in trans_ids and target in trans_ids):
            raise ValueError(f"Invalid arc direction in {arc['id']}: {src} → {target}")

    # Compute M0 vector 
    M0 = [p["m0"] for p in places]

    # Return final structure 
    return {
        "places": places,
        "transitions": transitions,
        "arcs": arcs,
        "M0": M0,
        "Places": len(places),
        "Transitions": len(transitions),
        "Arcs": len(arcs),
    }

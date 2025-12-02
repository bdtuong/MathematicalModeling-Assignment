import xml.etree.ElementTree as ET
import re
from pathlib import Path

def parse_pnml(file_path: str):
    """Parse PNML file (simplified: no name, no warnings)."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    #tree = ET.parse(path) # XML parse file
    #root = tree.getroot() # take root element such as <pnml>

    with open(path, 'r', encoding='utf-8') as f:
        xml_content = f.read()

    xml_content = re.sub(r'\sxmlns="[^"]+"', '', xml_content, count=1)
    
    root = ET.fromstring(xml_content)

    places, transitions, arcs = [], [], [] # Initialize lists

    # Parse every <net> in file
    for net in root.findall(".//net"):
        # Parse places
        for place in net.findall(".//place"):
            pId = place.get("id")

            name_tag = place.find(".//name/text")
            pName = name_tag.text if name_tag is not None else pId

            marking_text = place.findtext("initialMarking/text", default="0").strip()
            try:
                m0 = int(marking_text)
                if m0 < 0:
                    raise ValueError
            except ValueError:
                raise ValueError(f"Invalid initialMarking for place {pId}: {marking_text}")
            #places.append({"id": pId, "m0": m0})
            places.append({"id": pId, "name": pName, "m0": m0})

        # Parse transitions 
        for transition in net.findall(".//transition"):
            tId = transition.get("id")
            name_tag = transition.find(".//name/text")
            tName = name_tag.text if name_tag is not None else tId
            #transitions.append({"id": tId})
            transitions.append({"id": tId, "name": tName})

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

    # Check duplicate IDs between places and transitions
    all_ids = [p["id"] for p in places] + [t["id"] for t in transitions]
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("Duplicate IDs detected detected between places and transitions")

    # Check duplicate arc IDs
    arc_ids = [a["id"] for a in arcs]
    if len(arc_ids) != len(set(arc_ids)):
        raise ValueError("Duplicate arc IDs detected")
    
    # Check arc validity
    for arc in arcs:
        src, target = arc["src"], arc["target"]
        if src not in node_ids or target not in node_ids:
            raise ValueError(f"Arc {arc['id']} references unknown node")
        if (src in place_ids and target in place_ids) or (src in trans_ids and target in trans_ids):
            raise ValueError(f"Invalid arc direction in {arc['id']}: {src} → {target}")

    # Check for isolated nodes (warning)
    connected_nodes = {a["src"] for a in arcs} | {a["target"] for a in arcs}
    unconnected_nodes = node_ids - connected_nodes
    if unconnected_nodes:
        print(f"[Warning] Isolated nodes detected (not connected to any arc): {unconnected_nodes}")
    
    # Compute M0 vector 
    M0 = [p["m0"] for p in places]


    # --- 1-safe check ---
    for p in places:
        if p["m0"] > 1:
            raise ValueError(f"Place {p['id']} has {p['m0']} tokens initially, violating 1-safe property")


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

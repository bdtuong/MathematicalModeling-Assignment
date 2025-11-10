# bfs.py
from collections import deque
import json

def bfs_reachable_markings_with_depth(petri_net, initial_marking=None):
    """
    BFS + trả về depth của mỗi trạng thái.
    Output:
        {
            "markings": [dict, ...],
            "depth": {marking_json_str: depth}
        }
    """
    if initial_marking is None:
        initial_marking = {p["id"]: p["m0"] for p in petri_net["places"]}
    
    place_ids = [p["id"] for p in petri_net["places"]]
    
    # Build input/output arcs
    trans_inputs = {}
    trans_outputs = {}
    for arc in petri_net.get("arcs", []):
        src = arc["src"]
        tgt = arc["target"]
        w = arc.get("weight", 1)
        if src in place_ids:
            trans_inputs.setdefault(tgt, {})[src] = w
        else:
            trans_outputs.setdefault(src, {})[tgt] = w
    
    # BFS
    reachable = set()
    depth_map = {}
    queue = deque()
    
    init_mark = initial_marking.copy()
    init_key = json.dumps(init_mark, sort_keys=True)
    queue.append(init_mark)
    reachable.add(init_key)
    depth_map[init_key] = 0

    markings_list = [init_mark]

    while queue:
        current = queue.popleft()
        curr_key = json.dumps(current, sort_keys=True)
        curr_depth = depth_map[curr_key]

        for t in petri_net.get("transitions", []):
            trans_id = t["id"]
            inputs = trans_inputs.get(trans_id, {})
            if not all(current.get(p, 0) >= w for p, w in inputs.items()):
                continue

            new_mark = current.copy()
            for p, w in inputs.items():
                new_mark[p] -= w
            for p, w in trans_outputs.get(trans_id, {}).items():
                new_mark[p] = new_mark.get(p, 0) + w

            new_key = json.dumps(new_mark, sort_keys=True)
            if new_key not in reachable:
                reachable.add(new_key)
                depth_map[new_key] = curr_depth + 1
                queue.append(new_mark)
                markings_list.append(new_mark)

    return {
        "markings": markings_list,
        "depth": depth_map
    }
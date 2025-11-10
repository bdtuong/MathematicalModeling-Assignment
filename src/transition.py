# transition.py
def enabled(transitions, places, arcs, marking, transition):
    input_arcs = [arc for arc in arcs if arc['target'] == transition]
    for arc in input_arcs:
        place = arc['src']           # Sửa: 'source' → 'src'
        required_tokens = arc.get('weight', 1)
        if marking.get(place, 0) < required_tokens:
            return False
    return True

def fire(transitions, places, arcs, marking, transition):
    if not enabled(transitions, places, arcs, marking, transition):
        return marking

    new_marking = marking.copy()

    input_arcs = [arc for arc in arcs if arc['target'] == transition]
    for arc in input_arcs:
        place = arc['src']  # Sửa: 'source' → 'src'
        tokens_to_remove = arc.get('weight', 1)
        new_marking[place] -= tokens_to_remove

    output_arcs = [arc for arc in arcs if arc['src'] == transition]  # 'src' là đúng
    for arc in output_arcs:
        place = arc['target']
        tokens_to_add = arc.get('weight', 1)
        new_marking[place] = new_marking.get(place, 0) + tokens_to_add

    return new_marking
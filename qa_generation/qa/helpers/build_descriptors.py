
import random

from qa.uniqueness.unique_node_descriptors import build_node_descriptor, _extract_unique_edge_anchors


def allow_pointers_for_vehicles(text):
    """True if a description points at a vehicle by its marker (e.g. "...that contains the bus marked with ...")."""
    vehicles = ["regular vehicle", "bus", "large vehicle", "school bus", "box truck", "truck", "bicyclist", "motorcyclist"]
    for vehicle in vehicles:
        if f"that contains the {vehicle} marked with" in text:
            return True
    return False


def build_descriptors_and_select(graph_specs, node_label, n_items=1, allow_positions=False, allow_vehicle_pointers=False, special_selector=None, allow_non_unique=False, position_only=False, max_hops=2):
    edge_anchors = _extract_unique_edge_anchors(graph_specs.G)
    descs = build_node_descriptor(graph_specs, node_label, edge_anchors, max_hops=max_hops)
    if not allow_non_unique:
        descs = [d for d in descs if d.is_unique]
    if special_selector!=None:
        descs = [d for d in descs if not special_selector(d)]
    if not descs:
        return [], []
    positions = [s for s in descs if "position_" in s.text]
    nopositions = [s for s in descs if (not "position_" in s.text or (allow_vehicle_pointers and allow_pointers_for_vehicles(s.text)))]
    
    random.shuffle(positions)
    random.shuffle(nopositions)
    if not position_only:
        descs = nopositions 
        if allow_positions: descs += positions
        descs = descs[:n_items]
        other_descs = [d for d in nopositions if d.text not in [dd.text for dd in descs]]
    else: 
        descs = positions
        other_descs = []
    return descs, other_descs


def _format_lane_set(graph_specs, lane_ids, max_hops=2):

    def discard(d):
        if "the lane marked with" in d.text: return True
        else: return False

    descriptors = []
    for lane_id in lane_ids:
        descs, _ = build_descriptors_and_select(graph_specs, lane_id, n_items=1, allow_positions=False, allow_vehicle_pointers=False, special_selector=discard, max_hops=max_hops)
        if len(descs)>0:
            descriptors.append({"text": descs[0].text.capitalize(), "node_label": lane_id, "desc": descs[0]})
        else: 
            return None
    if len(descriptors)==0: return None
    return descriptors

def prune_edges(G, targets, source, relation, inverse_relation):
    for edge in G.edges(data=True):
        for target in targets:
            if edge[0]==target and edge[1]==source and edge[2]["relation"]==relation: 
                edge[2]["is_unique"] = False
                
            if edge[1]==target and edge[0]==source and edge[2]["relation"]==inverse_relation: 
                edge[2]["is_unique"] = False
                
    return G    

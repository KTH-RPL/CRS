from core.graph_builder import collect_matches
from qa.uniqueness.unique_node_descriptors import build_node_descriptor, _extract_unique_edge_anchors
from qa.helpers.definitions import idx_to_cardinal

def retreive_all_lanes(graph_specs, nodes):
    descs = []
    edge_anchors = _extract_unique_edge_anchors(graph_specs.G)
    ego_node = None
    for m in nodes:
        desc = build_node_descriptor(graph_specs, m, edge_anchors, max_hops=1)
        ego_match = collect_matches(graph_specs.G, "lane", "ego", lambda x: x=="contains")
        if ego_match: 
            ego_match = [m[0] for m in ego_match]
           
        selection_list = [d for d in desc if not "marked with" in d.text and not True in ["lane"==D["type"] for D in d.dependants]]
        is_anchor = len(selection_list)>0
        if m in ego_match: ego_node = {"desc": desc, "is_anchor": is_anchor}
        else: descs.append({"desc": desc, "is_anchor": is_anchor})
        
    descs = sorted(descs, key=lambda x: x["is_anchor"], reverse=True)
    has_ego = False
    if ego_node != None:
        descs = [ego_node] + descs
        has_ego = True
    return descs, has_ego   

def get_intro_sentence(node_label, idx, G, old_node_labels, is_ego):
    if is_ego: intro_sentence = " I start from the ego lane, "
    else:
        intro_sentence = f" Looking ahead, I detect a {idx_to_cardinal[idx]} lane, "
        if old_node_labels:
            intro_sentence = ""
            for idx_, old_node_label in enumerate(old_node_labels):
                for _, v, d in G.out_edges(old_node_label, data=True):
                    if v == node_label:
                        rel = d.get("relation")
                        if rel == "is left of": 
                            if intro_sentence=="": intro_sentence = f"To the right of Lane {idx_+1}"
                            else: intro_sentence+=f" and to the right of Lane {idx_+1}"
                        if rel == "is right of": 
                            if intro_sentence=="": intro_sentence= f"To the left of Lane {idx_+1}"
                            else: intro_sentence+=f" and to the left of Lane {idx_+1}"
                        break
            if intro_sentence=="": intro_sentence = " Looking ahead"
            intro_sentence+=", I detect another lane, "
    return intro_sentence
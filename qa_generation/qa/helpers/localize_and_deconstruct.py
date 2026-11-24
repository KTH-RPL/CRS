

from core.hierarchy_schema import DESCRIPTION_HIERARCHY
from core.process_geometry import poly_to_grounding_box, IMG_SIZE_BY_CAM
from qa.helpers.definitions import join_with_and
from qa.helpers.definitions import ACTOR_TYPES
import random
import re   

def extract_view_per_cam(node_attrs, with_pointing):
    hits = {"cameras": [], "bboxes": []}
    pos = node_attrs["properties"].get("click_position", {})
    type = node_attrs["type"]
    views = []
    for cam_key in ["ring_front_left", "ring_front_center", "ring_front_right"]:
        if cam_key in pos:
            w, h = IMG_SIZE_BY_CAM[cam_key]
            bbox, _ = poly_to_grounding_box(pos[cam_key]["polygon"], w, h, type)
            if bbox!=None:    
                hits["cameras"].append(cam_key.replace('ring_front_', ''))
                if len(bbox)==4:
                    hits["bboxes"].append(f"<box>({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]})</box>")
                if len(bbox)==2: 
                    hits["bboxes"].append(f"<point>({bbox[0]},{bbox[1]})</point>")
    if with_pointing:
        views = [f"{c.upper()} view at {b}" for c,b in zip(hits["cameras"], hits["bboxes"])]  
    else:              
        views = [f"{c.upper()} view" for c,b in zip(hits["cameras"], hits["bboxes"])]  
    return views

def format_visibility_verbose(visibility_dict):
    view_groups = {}
    for frame, views in visibility_dict.items():
        view_tuple = tuple(sorted(views))
        if view_tuple not in view_groups:
            view_groups[view_tuple] = []
        view_groups[view_tuple].append(frame)

    clauses = []
    for views, frames in view_groups.items():
        if not views:
            continue
            
        if len(views) > 1:
            view_str = f"{' and '.join(views)}s"
        else:
            view_str = f"{views[0]}"

        if len(frames) == 1:
            frame_str = f"Frame {frames[0]}"
        else:
            frame_list = [f"Frame {f}" for f in frames]
            frame_str = f"{', '.join(frame_list[:-1])}, and {frame_list[-1]}"

        clauses.append(f"{view_str} in {frame_str}")

    if not clauses:
        return "CENTER frame"

    return ", and ".join(clauses)

def extract_views(node_label, graph_specs, is_cot=True):
    attrs = graph_specs.G.nodes[node_label]
    if graph_specs.temporal:
        views_per_frame = {}
        for idx in range(4):
            G_last = graph_specs.G_old[idx]
            last_node_id = G_last.nodes.get(node_label, None)
            if last_node_id==None: continue
            views = extract_view_per_cam(last_node_id, with_pointing=graph_specs.with_pointing_cot if is_cot else graph_specs.with_pointing_qa)
            views_per_frame[idx]=views
        return format_visibility_verbose(views_per_frame)
    else:
        views = extract_view_per_cam(attrs, with_pointing=graph_specs.with_pointing_cot if is_cot else graph_specs.with_pointing_qa)
        return join_with_and(views)
        
def sort_key(s):
    numbers = re.findall(r'\d+', s)
    y1, x1, _, _ = map(int, numbers)
    return (x1, y1)

def sort_traffic_lights_left_to_right(coords):
    sorted_coords = sorted(coords, key=sort_key)
    return sorted_coords
            
def deconstruct_nested_descriptors(reasoning_steps, stepcount, desc, graph_specs, with_step_string=True):
    node_attrs = graph_specs.G.nodes[desc.node_label]
    if desc.dependants and not desc.text == "the ego lane":   
        dependants = desc.dependants
        dependants = sorted(dependants, key=lambda x: x["n_hops"])
        for idx, dependant in enumerate(dependants):
            if not reasoning_steps: step_string = f"Step {stepcount}: " 
            else: step_string = ""
            if not with_step_string: step_string=""
            if dependant["type"]=="ego": continue
            if idx == 1 and "Lane-" in dependant["node"] and dependants[0]["relation"][0] == "contains" and dependants[0]["type"] in ACTOR_TYPES: 
                last_relation = dependant["relation"][0]    
                continue
            if "marked with" in dependant["text"] and dependant["n_hops"]==0:
                reasoning_steps.append(f"{step_string}Identify the location of point_1 in the last frame.")
                views = extract_views(dependant["node"], graph_specs)
                reasoning_steps.append(f"The marker is visible in the {views}")
                other_descs_dependant = [od.text for od in dependant["other_descs"] if od.n_hops==0 and not "marked with" in od.text]
                if other_descs_dependant: 
                    reasoning_steps[-1] = reasoning_steps[-1] + f" and marks a {other_descs_dependant[0]}."
                    last_type = other_descs_dependant[0]  
                else: 
                    reasoning_steps[-1] = reasoning_steps[-1] + f" and marks a {dependant['type']}."
                    
                    last_type = "the " + dependant["type"]   
                     
                if graph_specs.temporal: 
                    view_string = extract_views(dependant["node"], graph_specs)
                    reasoning_steps.append(f"{last_type.capitalize()} is visible in the {view_string}.")    
            else: 
                if dependant["type"] == "intersection":
                    dist_to_ego = graph_specs.G.nodes[dependant["node"]]["properties"]["distance_to_ego"]
                    if dist_to_ego == 0:
                        reasoning_steps.append(f"{step_string}The ego is currently traversing an intersection.")
                    else: reasoning_steps.append(f"{step_string}The ego is currently approaching the intersection ahead.")
                else: 
                    views_string = extract_views(dependant["node"], graph_specs)
                    if not views_string: reasoning_steps.append(f"{step_string}Identify {dependant['text']}.")    
                    else: reasoning_steps.append(f"{step_string}Identify {dependant['text']}, which is visible in the {views_string}.")    
                      
                last_type = "that "+dependant["type"] if dependant["type"] not in ACTOR_TYPES else dependant["text"]
            last_relation = dependant["relation"][0]    
        stepcount+=1   
        step_string =  f"\n\nStep {stepcount}: " if with_step_string else ""
        reasoning_steps.append(f"{step_string}The {node_attrs['type']} in question is the {node_attrs['type']} that {last_relation} {last_type},")
    else: 
        step_string =  f"\n\nStep {stepcount}: " if with_step_string else ""
        if not "marked with" in desc.text:
            reasoning_steps.append(f"{step_string}The {node_attrs['type']} in question is the {desc.text},")
        else:
            views = []   
            reasoning_steps.append(f"{step_string}Identify the location of point_1 in the last frame.")
            view_string = extract_views(desc.node_label, graph_specs)
            reasoning_steps.append(f"The {graph_specs.G.nodes[desc.node_label]['type']} is visible in the {view_string}.")    
            
                
    stepcount+=1   
    return stepcount, reasoning_steps


def ensure_hierarchy_complete(node_attrs, hierarchy):
    node_type = (node_attrs.get("type") or "").lower()
    if node_type not in hierarchy:
        raise ValueError(f"No hierarchy defined for node type '{node_type}'")

    spec = hierarchy[node_type]
    if "properties" not in spec:
        raise ValueError(f"Hierarchy for node type '{node_type}' is missing 'properties'")
    if "edges" not in spec:
        raise ValueError(f"Hierarchy for node type '{node_type}' is missing 'edges'")

    return spec


def extract_node_descriptions(desc, graph_specs, original_property=None, original_relation=None,  max_node_properties=1, max_edges=1, max_target_properties=2):
    G = graph_specs.G

    num_intersections = len([
        (n, attrs) for n, attrs in graph_specs.G.nodes(data=True)
        if (attrs.get("type") or "").lower() == "intersection"
    ])
    if type(desc)==str: node_label = desc
    else: node_label = desc.node_label
    
    if type(original_property)==str: original_property = [original_property]
    elif original_property==None: original_property = []
    if type(original_relation)!=list: 
        original_relation = [original_relation]
    elif original_relation==None: original_relation = []
    neighbors = list(G.predecessors(node_label)) + list(G.successors(node_label))
    sub_nodes = list(dict.fromkeys(neighbors + [node_label]))
    subgraph = G.subgraph(sub_nodes)

    hierarchy = DESCRIPTION_HIERARCHY

    if node_label not in subgraph:
        raise ValueError(f"Node '{node_label}' not found in subgraph")

    node_attrs = subgraph.nodes[node_label]
    node_type = (node_attrs.get("type") or "").lower()
    spec = ensure_hierarchy_complete(node_attrs, hierarchy)

    props_spec = spec["properties"]
    edges_spec = spec["edges"]

    skip_properties = {"is_occluded", "is_unique", "uuid", "click_position", "unique_properties", "distance_to_ego"}

    property_candidates = []
    props = node_attrs.get("properties", {})

    for prop_name, prop_value in props.items():
        if prop_name in skip_properties or prop_value is None or prop_name in original_property:
            continue
        
        if prop_name not in props_spec:
            raise ValueError(
                f"Missing property priority for node type '{node_type}', property '{prop_name}'"
            )

        property_candidates.append({
            "priority": props_spec[prop_name],
            "prop_name": prop_name,
            "prop_value": prop_value,
            "text": f'{prop_name} is {prop_value}',
        })

    random.shuffle(property_candidates)
    property_candidates.sort(key=lambda x: (x["priority"]))
    property_candidates_high_prio = [p for p in property_candidates if p["priority"]==0]
    if len(property_candidates_high_prio)>max_node_properties:
        selected_properties = property_candidates_high_prio
    else: selected_properties = property_candidates[:max_node_properties]

    edge_candidates = []
    for _, target_label, edge_attrs in subgraph.out_edges(node_label, data=True):
        target_attrs = subgraph.nodes[target_label]
        target_type = (target_attrs.get("type") or "").lower()
        
        
        relation = edge_attrs.get("relation")
        if (relation,target_label) in original_relation: continue
        if (relation, target_type) in original_relation: continue
        edge_key = (relation, target_type)
        if edge_key not in edges_spec:
            raise ValueError(
                f"Missing edge priority for node type '{node_type}', edge {edge_key}"
            )
        if target_type == "ego": 
            edge_candidates.append({
                "priority": 0,
                "relation": relation,
                "target_type": target_type,
                "target_text": " ",
                "text": f'{relation} the ego',
                "key": edge_key,
            })
            continue
        target_spec = ensure_hierarchy_complete(target_attrs, hierarchy)
        target_props_spec = target_spec["properties"]

        target_property_candidates = []
        target_props = target_attrs.get("properties", {})

        for prop_name, prop_value in target_props.items():
            if prop_name in skip_properties or prop_value is None:
                continue

            if prop_name not in target_props_spec:
                raise ValueError(
                    f"Missing property priority for target node type '{target_type}', property '{prop_name}'"
                )

            target_property_candidates.append({
                "priority": target_props_spec[prop_name],
                "prop_name": prop_name,
                "prop_value": prop_value,
            })

        random.shuffle(target_property_candidates)
        target_property_candidates.sort(key=lambda x: (x["priority"]))
        target_property_candidates_high_prio = [p for p in target_property_candidates if p["priority"]==0]
        if len(target_property_candidates_high_prio)>max_target_properties:
            selected_target_properties = target_property_candidates_high_prio
        else: selected_target_properties = target_property_candidates[:max_target_properties]
        if selected_target_properties:
            parts = [
                f'{item["prop_name"]} {item["prop_value"]}'
                for item in selected_target_properties
            ]
            target_text = f'{target_type} with ' + " and ".join(parts)
        else:
            target_text = target_type
        loc=None    
        if graph_specs.with_pointing_cot and graph_specs.pointing_style=="all": 
            if target_attrs["type"]=="intersection" and num_intersections==1: location=None      
            else: location =  extract_views(target_label, graph_specs)   
            if location:
                loc = location
        edge_candidates.append({
            "priority": edges_spec[edge_key],
            "relation": relation,
            "target_type": target_type,
            "target_text": target_text,
            "text": f'{relation} a {target_text}{f" located in {loc}" if loc!=None else ""}',
            "key": edge_key,
        })
    random.shuffle(edge_candidates)
    edge_candidates.sort(key=lambda x: (x["priority"]))
    
    edge_candidates_high_prio = [p for p in edge_candidates if p["priority"]==0]
    if len(edge_candidates_high_prio)>max_edges:
        selected_edges = edge_candidates_high_prio
    else: selected_edges = edge_candidates[:max_edges]
    
    descriptions = []
    if selected_properties:
        descriptions.append({
            "priority": [item["priority"] for item in selected_properties],
            "text": f"The {node_type}'s {join_with_and([item['text'] for item in selected_properties])}.",
        
        })
    if selected_edges:    
        descriptions.append({
            "priority": [item["priority"] for item in selected_edges],
            "text": f"The {node_type} {join_with_and([item['text'] for item in selected_edges])}.",
        
        })

    return descriptions



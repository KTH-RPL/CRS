
from qa.helpers.build_descriptors import build_descriptors_and_select
from core.graph_builder import collect_matches
import random
from qa.helpers.definitions import VERBOSE_LANES
from qa.helpers.helpers_lane import build_lane_type_evidence
from qa.helpers.localize_and_deconstruct import deconstruct_nested_descriptors, extract_node_descriptions, extract_views
from core.graph_builder import lane_split_in_frame


def format_cot_answer(desc, property, correct_val, formulated_answer, graph_specs):
    reasoning_steps = []
    stepcount = 1
    
    stepcount, reasoning_steps = deconstruct_nested_descriptors(reasoning_steps, stepcount, desc, graph_specs)
    
    view_string = extract_views(desc.node_label, graph_specs)
    if view_string:
        reasoning_steps[-1] = reasoning_steps[-1] + f". Looking at the images, the lane is visible in the {view_string}."
    
    descriptors = extract_node_descriptions(desc, graph_specs, original_property=[property, desc.property], original_relation=desc.relation)
    reasoning_steps.append(f"\n\nStep {stepcount}: ")
    stepcount += 1
    for descriptor in descriptors:
        reasoning_steps.append(descriptor["text"])
        
        
    evidence = build_lane_type_evidence(correct_val)
    reasoning_steps.append(f"\n\nStep {stepcount}: {evidence}")
    stepcount += 1

    final_label = VERBOSE_LANES.get(correct_val, "standard travel lane")
    if formulated_answer != "None of the above":
        reasoning_steps.append(f"\n\nConclusion: Therefore, I classify this lane as a {final_label}.")
    else: reasoning_steps.append(f" Since the specific type '{final_label}' is not provided in the primary choices, the correct selection is None of the above.")
        
    return " ".join(reasoning_steps)

def generate_lane_type_questions(graph_specs):
    qa = []
    if lane_split_in_frame(graph_specs.G): return qa
    
    intersection_nodes = [
        (n, attrs) for n, attrs in graph_specs.G.nodes(data=True)
        if (attrs.get("type") or "").lower() == "intersection"
    ]
    
    allowed_nodes = [node_label for node_label, _ in graph_specs.G.nodes(data=True)]
    if intersection_nodes:
        distance_to_intersection = graph_specs.G.nodes[intersection_nodes[0][0]]["properties"]["distance_to_ego"]
        
        if distance_to_intersection > 2:
            relations = ["leads up to", "leaves"]
        if distance_to_intersection < 2: 
            relations = ["leaves behind of", "approaches behind of", "leaves to the left", "approaches to the left", "approaches to the right", "leaves to the right"]       
        matches = []
        for relation in relations:
            matches += collect_matches(graph_specs.G,"lane", "intersection", lambda x: x == relation)
        allowed_nodes = [n[0] for n in matches]
        

    
    for node_label, attrs in graph_specs.G.nodes(data=True):
        if node_label not in allowed_nodes: continue
        node_type = attrs["type"]
        if node_type not in ["lane"]: continue
        props = attrs["properties"]
        is_occluded = props["is_occluded"]
        if is_occluded: continue
  
        def discard(desc):
            if "that contains the road marking whose meaning is 'bikes share lane with vehicles'" in desc.text: return True
            return False            
    
        descs, _ = build_descriptors_and_select(graph_specs, node_label, n_items=1, allow_positions=True, allow_vehicle_pointers=True, special_selector=discard)

        prop_key = "type"
        
        for desc in descs:
            correct_value = props.get(prop_key, None)
            if correct_value == None:
                continue
            if (correct_value == "VEHICLE" and random.random() < 0.9):
                continue
            if correct_value == "VEHICLE share the road with BIKES":
                see_sharrow=False
                for node in graph_specs.G.nodes():
                    attrs_ = graph_specs.G.nodes[node]
                    if attrs_["type"]=="road_marking":
                        if attrs_["properties"]["meaning"] == "bikes share lane with vehicles": see_sharrow=True
            if correct_value == "VEHICLE share the road with BIKES" and not see_sharrow: continue     
             
            none_of_the_above = False
            if random.random() > 0.9: none_of_the_above = True
            
            ops = [VERBOSE_LANES[a] for a in VERBOSE_LANES.keys() if a != correct_value and (none_of_the_above==False or a != "None of the above")]
            options = random.sample(ops, 3)
            q = f"What lane is {desc.text}?"
            formulated_answer = VERBOSE_LANES[correct_value]  if not none_of_the_above else "None of the above" 
            options.append(formulated_answer)
            
            random.shuffle(options)
            
            cot_reasoning = format_cot_answer(
                desc=desc,
                formulated_answer=formulated_answer,
                graph_specs=graph_specs,
                correct_val=correct_value,
                property=prop_key
                )
            
            qa.append({
                "q": q,
                "a": formulated_answer,
                "options": options, 
                "cot_reasoning": cot_reasoning
            })

    return qa

import random
from core.graph_builder import collect_matches
from qa.helpers.localize_and_deconstruct import deconstruct_nested_descriptors, extract_node_descriptions, extract_views
from qa.helpers.build_descriptors import build_descriptors_and_select

def format_cot_answer(desc, property, formulated_answer, graph_specs):
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
        
    reasoning_steps.append(f"\n\nConclusion: Synthesizing the lane's position, potential markings, and current traffic, I conclude the direction is {formulated_answer}.")
    
    return " ".join(reasoning_steps), True


def discard_descs(desc):
    forbidden_descriptors = [
        "the lane that is right of the lane that contains the ego", "the lane that is right of the ego lane",
        "the lane that contains the ego", "the ego lane"
    ]
    forbidden_parts = [
        "the lane that approaches to the left of the intersection",
        "the lane that approaches to the right of the intersection",
        "the lane that leads up to the intersection",
        "the lane that approaches behind of the intersection",
        "the lane that leaves the intersection",
        "the lane that leaves behind of the intersection",
        "the lane that leaves to the right of the intersection",
        "the lane that leaves to the left of the intersection", 
        "one-way", "no entry", "of the double solid median", "leftmost lane", "rightmost lane", "right curb lane", "left curb lane"
        
    ]
    if desc.text in forbidden_descriptors: return True
    if "the lane marked with " in desc.text and not ("left of" in desc.text or "right of" in desc.text): return True
    discard = False
    for fp in forbidden_parts:
        if fp in desc.text: discard = True
    if discard == True: return True
    return False  


def generate_lane_direction_questions(graph_specs):
    qa = []
  
    relations = [("leaves to the left of", "approaches to the left of"), ("leaves to the right of", "approaches to the right of")]
    matches = []
    for relation in relations:
        matches += collect_matches(graph_specs.G, "lane", "intersection", lambda x: x == relation[0] or x == relation[1])
    lanes_to_discard = [m[0] for m in matches]
    
    intersection_nodes = [
        (n, attrs) for n, attrs in graph_specs.G.nodes(data=True)
        if (attrs.get("type") or "").lower() == "intersection"
    ]
    if intersection_nodes:
        dist_to_ego = intersection_nodes[0][1]["properties"]["distance_to_ego"]
        if dist_to_ego < 2: return qa
        
    for node_label, attrs in graph_specs.G.nodes(data=True):  
        props = attrs["properties"]
        if attrs["type"] != "lane" or node_label in lanes_to_discard or props["is_occluded"]:
            continue

        descs, _ = build_descriptors_and_select(graph_specs, node_label, n_items=1, allow_positions=False, allow_vehicle_pointers=True, special_selector=discard_descs)
        
        for desc in descs:
            correct_value = "same direction as ego" if props["direction"]=="same" else "opposite direction"
            options = ["same direction as ego","opposite direction"]
            
            q = f"What is the direction of {desc.text}?"
            a = correct_value  
            random.shuffle(options)
 
            cot_reasoning, valid = format_cot_answer(
                desc=desc,
                property="direction",
                formulated_answer=correct_value,
                graph_specs=graph_specs
            )
            
            if not valid: continue
            qa.append({
                "q": q,
                "a": a,
                "options": options, 
                "cot_reasoning": cot_reasoning
                
            })
           
            
    return qa
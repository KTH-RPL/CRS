import copy

from qa.helpers.definitions import ACTOR_TYPES
import random
from core.graph_builder import collect_matches
from qa.helpers.build_descriptors import build_descriptors_and_select, prune_edges, _format_lane_set
from core.graph_builder import lane_split_in_frame
from qa.helpers.localize_and_deconstruct import extract_node_descriptions, extract_views





def format_cot_answer(desc1, desc2, lane1, lane2, formulated_answer, relative_position, graph_specs):
    reasoning_steps = []
    stepcount=1
    reasoning_steps.append(f"Step {stepcount}: First, I need to identify the two actors:")
    stepcount+=1
    for idx, desc in enumerate([desc1, desc2]):
        if not desc.text == "the ego": 
            if "marked with" in desc.text and desc.n_hops==0:
                reasoning_steps.append(f"Actor_{idx+1} is the marked vehicle.")
            else:
                view_string = extract_views(desc.node_label, graph_specs)
                if view_string:
                    reasoning_steps.append(f"Actor_{idx+1} is {desc.text} visible in the {view_string}.")
                else: return "", False
        else: reasoning_steps.append(f"Actor_{idx+1} is the ego vehicle itself.")    
            
    reasoning_steps.append(f"\n\nStep {stepcount}: Next, I describe their respective lanes.")
    for idx, (desc, lane) in enumerate(zip([desc1, desc2], [lane1, lane2])):
        descriptors = extract_node_descriptions(lane.node_label, graph_specs, original_relation=lane.relation)
        view_string = extract_views(lane.node_label, graph_specs)
        if view_string:
            reasoning_steps.append(f"The lane that contains Actor_{idx+1} is visible in {view_string}.")
        else: return "", False
        for descriptor in descriptors:
            reasoning_steps.append(descriptor["text"])    
    
    if relative_position=="same":
        reasoning_steps.append(f"\n\nStep {stepcount}: Based on these observations, I infer the relative position of Actor_1 to be in the same lane as Actor_2.")
        reasoning_steps.append("This means yes, they are in the same lane.")
    else:
        reasoning_steps.append(f"\n\nStep {stepcount}: Based on these observations, I infer the relative position of Actor_1 to be {relative_position} of Actor_2.")
        reasoning_steps.append("Hence, they are not in the same lane.")

    reasoning_steps.append(f"\n\nConclusion: Hence, the correct answer is: {formulated_answer}.")
    return " ".join(reasoning_steps), True


        
def generate_pairwise_vehicle_comparison_questions(graph_specs):
    qa = []
    if lane_split_in_frame(graph_specs.G): return qa
    nodes_by_type = {}
    nodes_by_type["actors"] = ["Ego"]
    nodes_by_type["types"] = ["ego"]
 
    for node_label, attrs in graph_specs.G.nodes(data=True):
        if attrs["type"] not in ACTOR_TYPES:
            continue
        t = attrs.get("type")
        nodes_by_type["actors"].append(node_label)
        nodes_by_type["types"].append(t)

    nodes = nodes_by_type["actors"]
    types = nodes_by_type["types"]
    if len(nodes) < 2:
        return qa

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):

            n1, n2 = nodes[i], nodes[j]

            
            props1 = graph_specs.G.nodes[n1]["properties"]
            props2 = graph_specs.G.nodes[n2]["properties"]
            is_occluded_1 = props1["is_occluded"]
            is_occluded_2 = props2["is_occluded"]
            if is_occluded_1 or is_occluded_2: continue

            matches_ego = collect_matches(graph_specs.G, "lane", "ego", lambda x: x == "contains")
            matches_regular_vehicle = collect_matches(graph_specs.G, "lane", types[j], lambda x: x == "contains")
            if not matches_ego or not matches_regular_vehicle: 
                continue
            
            position_1 = [m[0] for m in matches_ego if m[1] == n1] + [m[0] for m in matches_regular_vehicle if m[1] == n1]
            position_2 = [m[0] for m in matches_ego if m[1] == n2] + [m[0] for m in matches_regular_vehicle if m[1] == n2]
            
            if not len(position_1)==1 or not len(position_2)==1: continue
            relative_position = "none"
            if position_1 == position_2: relative_position = "same"
            position_1 = position_1[0]
            position_2 = position_2[0]
            all_edges = copy.deepcopy(graph_specs.G)
            graph_specs.G = prune_edges(graph_specs.G, [n1], position_1, "is in", "contains")
            graph_specs.G = prune_edges(graph_specs.G, [n2], position_2, "is in", "contains")
            matches_ll = collect_matches(graph_specs.G, "lane", "lane", lambda x: x == "is left of")
            matches_rl = collect_matches(graph_specs.G, "lane", "lane", lambda x: x == "is right of")
            
            for m in matches_ll:
                if m[0] == position_1 and m[1] == position_2:
                    relative_position = "left"
                if m[1] == position_1 and m[0] == position_2:
                    relative_position = "right"
            for m in matches_rl:
                if m[0] == position_1 and m[1] == position_2:
                    relative_position = "right"
                if m[1] == position_1 and m[0] == position_2:
                    relative_position = "left"
                    
            decoy_lanes_l1 = []        
            for m in matches_ll:
                if m[1] == position_1 :
                    decoy_lanes_l1.append(m[0])
            for m in matches_rl:
                if m[1] == position_1 :
                    decoy_lanes_l1.append(m[0])
            decoy_lanes_l2 = []        
            for m in matches_ll:
                if m[1] == position_2 :
                    decoy_lanes_l2.append(m[0])
            for m in matches_rl:
                if m[1] == position_2 :
                    decoy_lanes_l2.append(m[0])
                    
            decoy_lanes_l1 = list(set([d for d in decoy_lanes_l1 if d != position_2]))
            decoy_lanes_l2 = list(set([d for d in decoy_lanes_l2 if d != position_1]))
            common_decoys = list(set(decoy_lanes_l1) & set(decoy_lanes_l2))
            
            decoy_l1  = _format_lane_set(graph_specs, decoy_lanes_l1)
            decoy_l2  = _format_lane_set(graph_specs, decoy_lanes_l2)
            decoy_c   = _format_lane_set(graph_specs, common_decoys)
            if decoy_l1: decoy_l1 = random.choice(decoy_l1)
            if decoy_l2: decoy_l2 = random.choice(decoy_l2)
            if decoy_c: decoy_c = random.choice(decoy_c)
            
            descs_l1, _ = build_descriptors_and_select(graph_specs, position_1, n_items=1, allow_positions=False, allow_vehicle_pointers=False)   
            descs_l2, _ = build_descriptors_and_select(graph_specs, position_2, n_items=1, allow_positions=False, allow_vehicle_pointers=False)      
            
            
            if n1 == "Ego": descs_l1 = [d for d in descs_l1 if d.text != "the ego lane"]
            if n2 == "Ego": descs_l2 = [d for d in descs_l2 if d.text != "the ego lane"]
            descs1, _ = build_descriptors_and_select(graph_specs, n1, n_items=1, allow_positions=True, allow_vehicle_pointers=True)      
            descs2, _ = build_descriptors_and_select(graph_specs, n2, n_items=1, allow_positions=True, allow_vehicle_pointers=True)      
                            
            if len(descs1)==0 or len(descs2)==0:
                continue 
            if len(descs_l1)==0 or len(descs_l2)==0:
                continue 
            
            descs_l1 = descs_l1[0]
            descs_l2 = descs_l2[0]
            for d1 in descs1:
                for d2 in descs2:
                    
                    q = f"Are {d1.text} and {d2.text} in the same lane?"
                    
                    option_list = [
                        f"Yes, they are in {descs_l1.text}.",
                        f"Yes, they are in {descs_l2.text}.",
                        f"No, {d1.text} is in the lane left of {d2.text}.",
                        f"No, {d1.text} is in the lane right of {d2.text}.",
                        f"No, {d1.text} is in {descs_l1.text} and {d2.text} is in {descs_l2.text}.",
                        f"No, {d1.text} is in {descs_l2.text} and {d2.text} is in {descs_l1.text}.",
                    
                    ]
                    if decoy_l1 != None:
                        option_list += [
                            f"Yes, they are in {decoy_l1['text'].lower()}."  ,  
                            f"No, {d1.text} is in {decoy_l1['text'].lower()} and {d2.text} is in {descs_l2.text}."  
                        ]
                        
                    if decoy_l2 != None:
                        option_list += [
                            f"Yes, they are in {decoy_l2['text'].lower()}." ,
                            f"No, {d1.text} is in {descs_l1.text} and {d2.text} is in {decoy_l2['text'].lower()}."
                        ]
                    if decoy_c != None:
                        option_list += [
                        f"Yes, they are in {decoy_c['text'].lower()}.",
                        f"No, {d1.text} is in {decoy_c['text'].lower()} and {d2.text} is in {descs_l2.text}.",
                        f"No, {d1.text} is in {descs_l1.text} and {d2.text} is in {decoy_c['text'].lower()}."
                        ]
                        
                    if decoy_l1 != decoy_l2 and decoy_l1 != None and decoy_l2 != None:
                        option_list.append(f"No, {d1.text} is in {decoy_l1['text'].lower()} and {d2.text} is in {decoy_l2['text'].lower()}.",)
                    if position_1 == position_2: 
                        correct = f"Yes, they are in {descs_l1.text}."
                        correct_opts = [correct]
                    else: 
                        correct_opts = [
                            f"No, {d1.text} is in {descs_l1.text} and {d2.text} is in {descs_l2.text}.",
                        ]    
                        if relative_position=="left": correct_opts.append( f"No, {d1.text} is in the lane left of {d2.text}.")
                        if relative_position=="right": correct_opts.append( f"No, {d1.text} is in the lane right of {d2.text}.")
                        correct = random.choice(correct_opts)
                    
                    options = list(set(option_list))
                    options = [o for o in options if o not in correct_opts]
                    
                    random.shuffle(options)
                    options = options[:3] + [correct]
                    random.shuffle(options)
                    
                    cot_reasoning, valid = format_cot_answer(
                    desc1=d1, 
                    desc2=d2, 
                    lane1=descs_l1, 
                    lane2=descs_l2,
                    formulated_answer=correct, 
                    relative_position=relative_position,
                    graph_specs=graph_specs
                    )
                    if not valid: continue
                    qa.append({
                        "q": q,
                        "a": correct,
                        "options": options,
                        "cot_reasoning": cot_reasoning
                    })
       
            graph_specs.G = all_edges
                        

    return qa
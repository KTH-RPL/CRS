
import copy

from qa.helpers.build_descriptors import build_descriptors_and_select, _format_lane_set, prune_edges
from qa.helpers.definitions import ACTOR_TYPES, idx_to_letter
import random
from core.graph_builder import collect_matches
from core.graph_builder import lane_split_in_frame
from qa.helpers.localize_and_deconstruct import deconstruct_nested_descriptors, extract_node_descriptions, extract_views


def format_cot_answer(desc, formulated_answer, options, graph_specs):
    reasoning_steps = []
    stepcount=1
    
    if not desc.text == "the ego" and not "marked with " in desc.text and desc.n_hops == 0: 
        reasoning_steps.append(f"Step {stepcount}: First, I need to identify {desc.text}.")
    
        stepcount+=1
        view_string = extract_views(desc.node_label, graph_specs)
        if view_string:
            reasoning_steps.append(f"Looking at the images, it is visible in the {view_string}.\n\n")
    else: 
        reasoning_steps.append(f"Step {stepcount}: The actor in question is the {'ego vehicle itself' if desc.text == 'the ego' else 'marked vehicle'}.")    
        stepcount+=1
    descriptors = extract_node_descriptions(formulated_answer["desc"], graph_specs, original_property=formulated_answer["desc"].property, original_relation=[("contains", desc.node_label)])
    reasoning_steps.append(f"Step {stepcount}: I now identify the target lane that contains the relevant vehicle.")
    view_string = extract_views(formulated_answer["node_label"], graph_specs)
    if view_string:
        reasoning_steps.append(f"The target lane is visible in {view_string}.")
        
    stepcount += 1
    for descriptor in descriptors:
        reasoning_steps.append(descriptor["text"])    
    
    reasoning_steps.append(f"\n\nStep {stepcount}: Next, I need to look at the options to determine which accurately describes that lane.")
    for idx, option in enumerate(options): 
        view_string = extract_views(option["node_label"], graph_specs)
        reasoning_steps.append(f"Lane_{idx_to_letter[idx]} is described as '{option['text']}'.")
        stepcount, reasoning_steps = deconstruct_nested_descriptors(reasoning_steps, stepcount, option["desc"], graph_specs, with_step_string=False)
        reasoning_steps[-1]+=f", which is visible in {view_string}."
        status = 'wrong' if option != formulated_answer else 'correct'
        if status == "correct":
            reasoning_steps.append(f"Hence, Lane_{idx_to_letter[idx]} accurately describes the target lane, and option {idx_to_letter[idx]} is {status}.")
        elif option.get("relation", "") != "":
            reasoning_steps.append(f"Hence, Lane_{idx_to_letter[idx]} is {option.get('relation', '')} of the target lane, and option {idx_to_letter[idx]} is {status}.")
        else:
            reasoning_steps.append(f"Hence, Lane_{idx_to_letter[idx]} is not an accurate description of the target lane, and option {idx_to_letter[idx]} is {status}.")
        if status == "correct": break
    
    return " ".join(reasoning_steps)


def generate_vehicle_position_questions(graph_specs):
    """
    Relation existence QA with full recursive descriptors and MCQ.
    """

    qa = []
    if lane_split_in_frame(graph_specs.G): return qa

    matches_lane = []
    for type in ["ego"] + ACTOR_TYPES:
        matches_lane += collect_matches(graph_specs.G, type, "lane", lambda x: x == "is in")
    
    for vehicles in matches_lane:
        correct_options_l = vehicles[1]
        all_edges = copy.deepcopy(graph_specs.G)
        graph_specs.G = prune_edges(graph_specs.G, [correct_options_l], vehicles[0], "contains", "is in")
        descs, _ = build_descriptors_and_select(graph_specs, vehicles[0], n_items=1, allow_positions=True)
        
        for descA in descs:
            
            q = f"Which lane is {descA.text} in?"
            
            if correct_options_l:
                left_neighbors = collect_matches(graph_specs.G, "lane", "lane", lambda x: x == "is left of")
                right_neighbors = collect_matches(graph_specs.G, "lane", "lane", lambda x: x == "is right of")
                left_n = [l[0] for l in left_neighbors if l[1] == correct_options_l] + [r[1] for r in right_neighbors if r[0] == correct_options_l] 
                right_n = [r[0] for r in right_neighbors if r[1] == correct_options_l] + [l[1] for l in left_neighbors if l[0] == correct_options_l]
                wrong_options_l=[]
                found_ids = []
                for l in left_n:
                    if l not in correct_options_l and l not in found_ids:
                        wrong_options_l.append({"node_label": l, "relation": "left"}) 
                        found_ids.append(l)
                        
                for r in right_n:
                    if r not in correct_options_l and r not in found_ids:
                        wrong_options_l.append({"node_label": r, "relation": "right"}) 
                        found_ids.append(r)
                                
                    
                wrong_options_v = []  
                vehicle_lanes = []  
                for actor in ["ego"] + ACTOR_TYPES:
                    vehicle_lanes += collect_matches(graph_specs.G, "lane", actor, lambda x: x == "contains")
                    
                for v in vehicle_lanes:
                    if v[0] not in correct_options_l and v[0] not in found_ids:
                        wrong_options_v.append({"node_label": v[0], "relation": ""}) 
                        found_ids.append(v[0])
           
                decoy_lanes = wrong_options_l + wrong_options_v
                all_nodes = [n["node_label"] for n in decoy_lanes]
                decoy_sets = decoy_lanes
                lanes = [{"node_label": n} for (n, attrs) in graph_specs.G.nodes(data=True) if attrs["type"]=="lane" and n != correct_options_l and n not in all_nodes]
                decoy_sets += lanes
            
                correct_text = _format_lane_set(graph_specs, [correct_options_l])
                if correct_text == None: continue
                else: correct_text = correct_text[0]
         
                decoy_texts = [{**_format_lane_set(graph_specs, [s["node_label"]])[0],"relation": s.get("relation", "")} for s in decoy_sets if _format_lane_set(graph_specs, [s["node_label"]]) is not None]
                decoy_texts = [d for d in decoy_texts if d["text"] != None]
                if not correct_text["text"]: continue
               
                options = decoy_texts
                
                if len(options) < 3:
                    continue
                
                random.shuffle(options)
                options = options[:3] + [correct_text]
                random.shuffle(options)
                
                cot_reasoning = format_cot_answer(
                    desc=descA, 
                    formulated_answer=correct_text, 
                    options=options, 
                    graph_specs=graph_specs
                    )
        
                qa.append({
                    "q": q,
                    "a": correct_text["text"],
                    "options": [o["text"] for o in options],
                    "cot_reasoning": cot_reasoning
                })
                
        graph_specs.G = all_edges       

    return qa
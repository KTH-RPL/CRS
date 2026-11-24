import copy

from qa.helpers.build_descriptors import build_descriptors_and_select, _format_lane_set, prune_edges
from qa.helpers.definitions import ACTOR_TYPES, idx_to_letter
from qa.helpers.definitions import join_with_and
from qa.helpers.localize_and_deconstruct import deconstruct_nested_descriptors, extract_node_descriptions, extract_views
import random
from core.graph_builder import collect_matches
from core.graph_builder import lane_split_in_frame
from qa.helpers.helpers_lane import _make_decoy_sets

def format_cot_answer(desc, formulated_answer, options, graph_specs):
    reasoning_steps = []
    stepcount=1
    
    if not desc.text == "the ego" and not "the sign marked with " in desc.text and not "the stop sign marked with " in desc.text: 
        reasoning_steps.append(f"Step {stepcount}: First, I need to identify {desc.text}.")
    
        stepcount+=1
        view_string = extract_views(desc.node_label, graph_specs)
        if view_string:
            reasoning_steps.append(f"Looking at the images, it is visible in the {view_string}.\n\n")
        
    
        reasoning_steps.append(f"Step {stepcount}: I now identify the lane(s) that are controlled by {desc.text}.")
    else: reasoning_steps.append(f"Step {stepcount}: I identify the lane(s) that are controlled by the marked sign.")
    target_lanes={}
    for idx, answer in enumerate(formulated_answer):    
        descriptors = extract_node_descriptions(answer["node_label"], graph_specs, original_property=answer["desc"].property, original_relation=[("is controlled by", desc.node_label)])

        view_string = extract_views(answer["node_label"], graph_specs)
        if view_string:
            reasoning_steps.append(f"Target lane {idx+1} is visible in {view_string}.")
        stepcount += 1
        target_lanes[answer["node_label"]]=f"target lane {idx+1}"
        for descriptor in descriptors:
            reasoning_steps.append(descriptor["text"])    
    
    
    reasoning_steps.append(f"\n\nStep {stepcount}: Next, I need to look at the options to determine which accurately describes the target lane{'s' if len(formulated_answer)>1 else ''}.")
    for idx, option in enumerate(options): 
        if len(option) != len(formulated_answer): 
            reasoning_steps.append(f"I can discard option {idx_to_letter[idx]} immediately because the sign controls {len(formulated_answer)} not {len(option)} lanes.")
        else: 
            reasoning_steps.append(f"Examining option {idx_to_letter[idx]}: ")
            jump=False
            for i, ops in enumerate(option):
                if not jump:
                    reasoning_steps.append(f"Lane_{idx_to_letter[idx]}{f'({i})' if len(option)>1 else ''} is described at '{ops['text']}'")
                    stepcount, reasoning_steps = deconstruct_nested_descriptors(reasoning_steps, stepcount, ops["desc"], graph_specs, with_step_string=False)
                    view_string = extract_views(ops["node_label"], graph_specs)
                    reasoning_steps[-1]+=f", which is visible in {view_string}."
                    if ops["node_label"] not in target_lanes.keys():
                        reasoning_steps.append(f"Lane_{idx_to_letter[idx]}{f'({i})' if len(option)>1 else ''} does not match {'any of the target lanes' if len(formulated_answer)>1 else 'the target lane'}. Hence, option {idx_to_letter[idx]} is wrong.")
                        jump=True
                    elif ops["node_label"] in target_lanes.keys():
                        reasoning_steps.append(f"Lane_{idx_to_letter[idx]}{f'({i})' if len(option)>1 else ''} correctly describes {target_lanes[ops['node_label']]}.")
                        
            if option == formulated_answer:
                reasoning_steps.append(f"Hence, option {idx_to_letter[idx]} is correct.\n")
                break
    
    return " ".join(reasoning_steps)


def generate_controlled_lane_mcq_sign(graph_specs):
    """
    Relation existence QA with full recursive descriptors and MCQ.
    """

    qa = []
    if "lane" not in graph_specs.complete_types: return qa
    intersection_nodes = [
        (n, attrs) for n, attrs in graph_specs.G.nodes(data=True)
        if (attrs.get("type") or "").lower() == "intersection"
    ]
    if intersection_nodes and len(intersection_nodes) != 1:
        return qa
    if lane_split_in_frame(graph_specs.G): return qa
    

    matches_lane = collect_matches(graph_specs.G, "sign", "lane", lambda x: x == "controls")
    matches_stop = collect_matches(graph_specs.G, "stop_sign", "lane", lambda x: x == "controls")

    nodes_sign = [n for n,a in graph_specs.G.nodes(data=True) if a["type"] == "sign"] + [n for n,a in graph_specs.G.nodes(data=True) if a["type"] == "stop_sign"]

    for sign in nodes_sign:
        correct_options_l = [m[1] for m in matches_lane if m[0] == sign] + [m[1] for m in matches_stop if m[0] == sign]
        all_edges = copy.deepcopy(graph_specs.G)
        graph_specs.G = prune_edges(graph_specs.G, correct_options_l, sign, "is controlled by", "controls")
            
        descA_list, _ = build_descriptors_and_select(graph_specs, sign, n_items=1, allow_positions=True, allow_vehicle_pointers=True)

        for descA in descA_list:
       
            q = f"Which lane(s) does {descA.text} control?"
            if correct_options_l:
                wrong_options_l = []
                for lane_label in correct_options_l:
                    left_neighbors = collect_matches(graph_specs.G, "lane", "lane", lambda x: x == "is left of")
                    left_n = [l[0] for l in left_neighbors if l[1] == lane_label] + [l[1] for l in left_neighbors if l[0] == lane_label]
                    right_neighbors = collect_matches(graph_specs.G, "lane", "lane", lambda x: x == "is right of")
                    right_n = [r[0] for r in right_neighbors if r[1] == lane_label] + [r[1] for r in right_neighbors if r[0] == lane_label]
                    wrong_options = [l for l in left_n if l not in correct_options_l] + [r for r in right_n if r not in correct_options_l]
                    wrong_options_l.append(wrong_options)
                vehicle_lanes = []  
                for actor in ["ego"] + ACTOR_TYPES:  
                    vehicle_lanes.append(collect_matches(graph_specs.G, "lane", actor, lambda x: x == "contains"))
              
                flat_wl = list(set([x for sub in wrong_options_l for x in sub]))
                flat_vl = list(set([x[0] for sub in vehicle_lanes for x in sub if x[0] not in correct_options_l]))
                decoy_lanes = list(set(flat_wl + flat_vl))
  
                decoy_sets = decoy_lanes
                lanes = [n for (n, attrs) in graph_specs.G.nodes(data=True) if attrs["type"]=="lane" ]
                decoy_sets += lanes
                decoy_sets = list(set(decoy_sets))
                decoy_sets = [d for d in decoy_sets if d != correct_options_l]
                decoy_sets = _make_decoy_sets(correct_options_l, decoy_sets)
                correct_text = _format_lane_set(graph_specs, correct_options_l)
                if correct_text == None: continue
                decoy_texts = [_format_lane_set(graph_specs, s) for s in decoy_sets]
                decoy_texts = [t for t in decoy_texts if t != None]
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
                    "a": join_with_and([c["text"].lower() for c in correct_text]).capitalize(),
                    "options": [join_with_and([o["text"].lower() for o in option]).capitalize() for option in options],
                    "cot_reasoning": cot_reasoning
                    })
                
        
        graph_specs.G = all_edges    

    return qa
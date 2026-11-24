
from qa.helpers.build_descriptors import build_descriptors_and_select

import random

from core.graph_builder import lane_split_in_frame
from qa.helpers.localize_and_deconstruct import extract_views
from qa.helpers.definitions import idx_to_letter
from qa.helpers.localize_and_deconstruct import extract_node_descriptions
import re


def format_cot_answer(desc, options, graph_specs):
    class Desc:
        def __init__(self, node_label):
            self.node_label = node_label
    reasoning_steps = []
    stepcount = 1
    
    reasoning_steps.append(f"Step {stepcount}: I am identifying the markers provided in the options to determine which one indicates {desc.text}.")
    stepcount += 1
    for idx, o in enumerate(options):
        desc_ = Desc(o["node_label"])
        
        descriptors = extract_node_descriptions(desc_, graph_specs)
        match = re.search(r"(.*?)-", desc_.node_label)
       
        if match:
            result = match.group(0)[:-1]
       
  
        reasoning_steps.append(f"\n\nStep {stepcount}: Option {idx_to_letter[idx]} points at a {result}.")
        stepcount+=1
        for descriptor in descriptors:
            reasoning_steps.append(descriptor["text"])
        if o["node_label"] == desc.node_label: 
            break
        else: reasoning_steps.append("This is not the object in question.") 
    reasoning_steps.append("This is the object the question asks about.")       
    reasoning_steps.append(f"\n\nConclusion: Hence, the correct marker is given in option {idx_to_letter[idx]}.")
        
    return " ".join(reasoning_steps)

interesting_types = ["sign", "traffic_light", "stop_sign", "road_marking", "construction_cone","construction_barrel","bike_rack", "bollard", "lane_divider", ]

def generate_pointing_questions(graph_specs):
    qa = []
    if lane_split_in_frame(graph_specs.G): return qa

    for node_label, attrs in graph_specs.G.nodes(data=True):
        node_type = attrs["type"]
        if node_type in ["intersection", "split"]: continue
        props = attrs["properties"]
        is_occluded = props["is_occluded"]
        if is_occluded: continue

        descs, other_descs = build_descriptors_and_select(graph_specs, node_label, n_items=1, allow_positions=False, allow_vehicle_pointers=False)
        if not descs: continue
        if node_type in ["lane", "crossing"]:
            candidates = [node_label for node_label, attrs in graph_specs.G.nodes(data=True) if attrs["type"]==node_type]
            if len(candidates)<2: continue
        if node_type in interesting_types:
            candidates = [node_label for node_label, attrs in graph_specs.G.nodes(data=True) if attrs["type"] in interesting_types]
            to_remove = []
            for cand in candidates:
                if cand == node_label: continue
                cand_desc, other_cand_descs = build_descriptors_and_select(graph_specs, cand, n_items=1, allow_positions=False, allow_vehicle_pointers=False)
                all_cand_desc = [c.text for c in cand_desc] + [c.text for c in other_cand_descs]
                all_desc = [descs[0].text]+ [c.text for c in other_descs]
                overlap = set(all_cand_desc) & set(all_desc)
                if overlap: 
                    to_remove.append(cand)
            candidates = [c for c in candidates if c not in to_remove]        
            if len(candidates)<2: continue
        else: continue    

        click_position = props.get("click_position", None)
        if click_position == None: continue
        
        for desc in descs:
            
            q = f"Where is {desc.text}?"
            view_string = extract_views(node_label, graph_specs, is_cot=False)
            
            a = view_string
            if view_string == "": continue
            
            options = [{"text": extract_views(o, graph_specs, is_cot=False), "node_label":o} for o in candidates if o!= node_label]
            options = [o for o in options if len(o["text"])>0]
            
            if len(options)<2: continue
            options = options[:3] + [{"text": a, "node_label": node_label}]
            random.shuffle(options)
            
            cot_reasoning = format_cot_answer(
                desc=desc,
                options=options, 
                graph_specs=graph_specs
                )
            
            qa.append({
                "q": q,
                "a": a,
                "options": [o["text"] for o in options], 
                "cot_reasoning": cot_reasoning
            })
            

    return qa
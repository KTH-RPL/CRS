import random

from qa.helpers.build_descriptors import build_descriptors_and_select
from core.temporal import build_property_timelines, property_changed
from qa.helpers.definitions import TL_TO_PEDESTRIAN
from core.graph_builder import collect_matches
from qa.helpers.definitions import join_with_and
from qa.helpers.localize_and_deconstruct import deconstruct_nested_descriptors, extract_view_per_cam, sort_traffic_lights_left_to_right


def format_cot_answer(desc, other_tls, is_pedestrian, formulated_answer, timeline, graph_specs):
    reasoning_steps = []
    stepcount = 1
    
    if "the traffic light marked with " in desc.text:
        stepcount, reasoning_steps = deconstruct_nested_descriptors(reasoning_steps, stepcount, desc, graph_specs)
    else:
        stepcount, reasoning_steps = deconstruct_nested_descriptors(reasoning_steps, stepcount, desc, graph_specs)
        reasoning_steps = reasoning_steps[:-1]
        stepcount-=1
        if "that controls the" in desc.text and not is_pedestrian:
            if len(other_tls)>1: reasoning_steps.append(f"\n\nStep {stepcount}: In the CENTER camera, there are {len(other_tls)} traffic lights visible that control the lane in question.")
            else: reasoning_steps.append(f"\n\nStep {stepcount}: In the CENTER camera, there is {len(other_tls)} traffic light visible that controls the lane in question.")
        if graph_specs.with_pointing_cot:
            views = []
            for otl in other_tls:
                views.append(extract_view_per_cam(graph_specs.G.nodes[otl], graph_specs.with_pointing_cot)[0])
            views = sort_traffic_lights_left_to_right(views)
            if len(other_tls)>1: reasoning_steps.append(f"They are located in {join_with_and(views)}.")    
            else: 
                if len(other_tls)==1: reasoning_steps.append(f"It is located in {views[0]}.")  
                
    tl_type = "pedestrian signal" if is_pedestrian else "signal for traffic on the main road"
    if is_pedestrian: 
        reasoning_steps.append(f"\n\nStep {stepcount}: The traffic light in question is a {tl_type}.")
        stepcount+=1
    else: 
        reasoning_steps.append(f"\n\nStep {stepcount}: The traffic light in question is a {tl_type}.")
        stepcount+=1
    
    
    reasoning_steps.append(f"\n\nStep {stepcount}: I am monitoring {'this signal' if len(other_tls)==1 or 'the traffic light marked with ' in desc.text else 'these signals'} across the captured video sequence.")
    stepcount+=1
    
    status = timeline["status"]
    reasoning_steps.append(f"Analyze the traffic light in Frame 0. The signal status is {TL_TO_PEDESTRIAN[status[0][1]] if is_pedestrian else status[0][1]}.\n")
    for idx, t in enumerate(timeline["status"][1:]):
        reasoning_steps.append(f"Analyze the traffic light in Frame {idx+1}. The signal status is {t[1]}.\n")
    
    if status[0][1] == t[1]: reasoning_steps.append(f"Hence, the traffic light in question stayed {t[1]} throughout the whole sequence.")
    if status[0][1] != t[1]: reasoning_steps.append(f"Hence, the traffic light in question changed from {status[0][1]} to {t[1]}.")
    if formulated_answer!= "None of the above": 
        reasoning_steps.append(f"\n\nConclusion: This is consistent with answer '{formulated_answer}'.")
    
    else: 
        reasoning_steps.append(f"\n\nConclusion: Given that this observation does not match any answer provided, the correct option is '{formulated_answer}'.")
    
    return " ".join(reasoning_steps)


def build_temporal_property_mcq(first_val, last_val, changed, only=None):
    template_vals = list(TL_TO_PEDESTRIAN.keys())[:-1]
    template_vals_pc = list(TL_TO_PEDESTRIAN.values())[:-1]
    if only=="pc": template_vals=[]
    if only=="ls": template_vals_pc=[]
    
    
    correct = None
    options = []

    first_val = str(first_val)
    last_val  = str(last_val)

    if changed:
        if first_val != last_val:
            correct = f"Yes, it was {first_val} first but switched to {last_val}."
        else:
            correct = "Yes, it changed"
    else:
        correct = f"No, it stayed {first_val}"
        
    if template_vals:
        for v1 in template_vals:
            idx = template_vals.index(v1)
            v2 = template_vals[(idx+1)%len(template_vals)]
            if v1 != v2:
                wrong = f"Yes, it was {v1} first but switched to {v2}."
                if wrong != correct:
                    options.append(wrong)
    if template_vals_pc:
        for v1 in template_vals_pc:
            idx = template_vals_pc.index(v1)
            v2 = template_vals_pc[(idx+1)%len(template_vals_pc)]
            if v1 != v2:
                wrong = f"Yes, it was {v1} first but switched to {v2}."
                if wrong != correct:
                    options.append(wrong)

    for v in template_vals:
        wrong = f"No, it stayed {v}"
        
        if wrong != correct:
            options.append(wrong)
    for v in template_vals_pc:
        wrong = f"No, it stayed {v}"
        
        if wrong != correct:
            options.append(wrong)

  
    options = list(dict.fromkeys(options))
    three_wrong_items = random.sample(options, min(3, len(options)))
    
    none_of_the_above = False
    if random.random() > 0.9: none_of_the_above = True
    
    if none_of_the_above == True: 
        correct = "None of the above"
    else: 
        if random.random() > 0.7: 
            three_wrong_items = three_wrong_items[:-1] + ["None of the above"]

    
    options = [correct] + three_wrong_items

    random.shuffle(options)

    return options, correct


def generate_temporal_property_change_questions(graph_specs):
    qa = []

    timelines = build_property_timelines(graph_specs.G_old)
    

    for node_label, props_timeline in timelines.items():
        if node_label not in graph_specs.G.nodes:
            continue
        if graph_specs.G.nodes[node_label]["type"]!="traffic_light": continue
        if len(props_timeline["status"])<4: continue
        controls_lanes = collect_matches(graph_specs.G, "traffic_light", "lane", lambda x: x == "controls")
        controls_peds = collect_matches(graph_specs.G, "traffic_light", "crossing", lambda x: x == "controls")
        this_tl_controls = [c[1] for c in controls_lanes if c[0] == node_label]
        this_pc_controls = [c[1] for c in controls_peds if c[0] == node_label]

        other_tls = list(set([c[0] for c in controls_lanes if c[1] in this_tl_controls]+[c[0] for c in controls_peds if c[1] in this_pc_controls]))
        
        descs, _ = build_descriptors_and_select(graph_specs, node_label, n_items=1, allow_positions=True, allow_vehicle_pointers=True)
        if not descs: continue
        
        traffic_light_type = graph_specs.G.nodes[node_label]["properties"].get("type", "vehicle")
        pedestrian_signal = traffic_light_type == "pedestrian"

        for desc in descs:
            for prop_key, seq in props_timeline.items(): 
                 
                if "unknown" in [s[1] for s in seq] or [s[1] for s in seq] == ["unknown", "unknown", "unknown", "unknown"]: 
                    continue
                
                if [s[1] for s in seq] == ["green", "green", "green", "green"] and random.random() > 0.25: continue
         
                first_val = seq[0][1] if not pedestrian_signal else TL_TO_PEDESTRIAN[seq[0][1]]
                last_val  = seq[-1][1] if not pedestrian_signal else TL_TO_PEDESTRIAN[seq[-1][1]]
                
                changed   = property_changed(seq)

     
                q = (
                    f"Did the {prop_key} of {desc.text} change over the "
                    f"last {graph_specs.window_size+1} frame(s)?"
                )
                
                only=None
                if "traffic light that controls the crossing" in desc.text:
                    only = "pc"
                if not "traffic light that controls the crossing" in desc.text and "traffic light that controls " in desc.text:
                    only = "ls"


                options, correct_answer = build_temporal_property_mcq(   
                    first_val=first_val,
                    last_val=last_val,
                    changed=changed,
                    only=only
                )
        
                cot_reasoning = format_cot_answer(
                  desc=desc,
                  other_tls=other_tls,
                  is_pedestrian=pedestrian_signal,
                  formulated_answer=correct_answer,
                  timeline=timelines[node_label],
                  graph_specs=graph_specs
                )

                qa.append({
                    "q": q,
                    "a": correct_answer,
                    "cot_reasoning": cot_reasoning, 
                    "options": options
                })
            
    return qa
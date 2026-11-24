
from qa.helpers.build_descriptors import build_descriptors_and_select
import random
from core.graph_builder import collect_matches
from core.temporal import build_property_timelines
from qa.helpers.definitions import TL_TO_PEDESTRIAN
from qa.helpers.definitions import join_with_and
from qa.helpers.localize_and_deconstruct import deconstruct_nested_descriptors, extract_node_descriptions, extract_view_per_cam, sort_traffic_lights_left_to_right


def format_cot_answer(desc, other_tls, correct_value, is_pedestrian, formulated_answer, timeline, graph_specs):
    """
    Rationalizes the visual state of a traffic light.
    """
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
    if len(other_tls)==1 or "the traffic light marked with " in desc.text:
        descriptors = extract_node_descriptions(desc, graph_specs, original_property=["status", desc.property], original_relation=desc.relation)
        for description in descriptors:
            reasoning_steps.append(description["text"])         
    stepcount+=1        
    tl_type = "pedestrian signal" if is_pedestrian else "signal for traffic on the main road"
    if is_pedestrian: 
        reasoning_steps.append(f"\n\nStep {stepcount}: The traffic light in question is a {tl_type}.")
        stepcount+=1
    else: 
        reasoning_steps.append(f"\n\nStep {stepcount}: The traffic light in question is a {tl_type}.")
        stepcount+=1
    


    reasoning_steps.append(f"\n\nStep {stepcount}: I am identifying the current state of the traffic light in the LAST frame.")
    
    if correct_value!="unknown":
        if is_pedestrian:
            reasoning_steps.append(f"Observing the pedestrian interface, the active icon or text indicates a '{TL_TO_PEDESTRIAN[correct_value]}' command.")
        else:
            reasoning_steps.append(f"The lamp currently illuminated on the signal head corresponds to the color {correct_value}.")
    else: 
        reasoning_steps.append("From the ego's perspective it is impossible to tell which lamp is currently illuminated.")
    stepcount+=1
    if len(timeline["status"])>1:reasoning_steps.append(f"\n\nStep {stepcount}: To confirm, I am cross verifying with earlier frames:")

    for idx, t in enumerate(reversed(timeline["status"])):
        if idx==0: continue
        new_value = t[1]
        if new_value!="unknown":
            if new_value==correct_value:
                reasoning_steps.append(f"In Frame {3-idx} (CENTER), the same traffic light is also {TL_TO_PEDESTRIAN[new_value] if is_pedestrian else new_value}.")
            else:
                reasoning_steps.append(f"In Frame {3-idx} (CENTER), the same traffic light is not {TL_TO_PEDESTRIAN[correct_value] if is_pedestrian else correct_value} but {TL_TO_PEDESTRIAN[new_value] if is_pedestrian else new_value}.")
                reasoning_steps.append("However, the question specifically refers to the status of the traffic light in the last frame, which is Frame 3.")
                break
                
        else: 
            reasoning_steps.append(f"In Frame {3-idx} (CENTER) it is impossible to tell which lamp is currently illuminated. Hence, I answer based on the later frames.")
            break
    reasoning_steps.append(f"\n\nConclusion: Therefore, the correct answer is: {formulated_answer}.")
    
    return " ".join(reasoning_steps)

def generate_traffic_light_status_questions(graph_specs):
    qa = []
    try: 
        timelines = build_property_timelines(graph_specs.G_old)
    except Exception as e: 
        print("Error in traffic_light.py: ", e, graph_specs.current_index) 
        return qa
    
    controlled_lanes = []
    for node_label, attrs in graph_specs.G.nodes(data=True):
        node_type = attrs["type"]
        if node_type not in ["traffic_light"]: continue
        
        props = attrs["properties"]
        is_occluded = props["is_occluded"]
        if is_occluded: continue
  
        controls_lanes = collect_matches(graph_specs.G, "traffic_light", "lane", lambda x: x == "controls")
        controls_peds = collect_matches(graph_specs.G, "traffic_light", "crossing", lambda x: x == "controls")
        this_tl_controls = [c[1] for c in controls_lanes if c[0] == node_label]
        this_pc_controls = [c[1] for c in controls_peds if c[0] == node_label]

        other_tls = list(set([c[0] for c in controls_lanes if c[1] in this_tl_controls]+[c[0] for c in controls_peds if c[1] in this_pc_controls]))
        this_set = set(this_tl_controls)

        if any(this_set == set(existing) for existing in controlled_lanes):
            continue
        
        descs, _ = build_descriptors_and_select(graph_specs, node_label, n_items=1, allow_positions=True, allow_vehicle_pointers=True)
        if not descs: continue
        
        
        for desc in descs:
            correct_value = props.get("status", None)
            is_pedestrian = props.get("type", None) == "pedestrian"
            if not is_pedestrian:
                controls_crossing = collect_matches(graph_specs.G, "traffic_light", "crossing", lambda x: x == "controls")
                if node_label in [c[0] for c in controls_crossing]: is_pedestrian=True
            if correct_value == None:
                continue
            if (correct_value == "green" and random.random() < 0.75): continue
            
            if "traffic light that controls the crossing" in desc.text:
                all_options=list(TL_TO_PEDESTRIAN.values())
            elif not "traffic light that controls the crossing" in desc.text and "traffic light that controls " in desc.text:
                all_options=list(TL_TO_PEDESTRIAN.keys())
            else:
                all_options = list(set(list(TL_TO_PEDESTRIAN.keys()) + list(TL_TO_PEDESTRIAN.values())))
            
            if is_pedestrian != False:
                correct_value = TL_TO_PEDESTRIAN[correct_value]
                
            none_of_the_above = False
            if random.random() > 0.9:
                none_of_the_above = True
            ops = [a for a in all_options if a != correct_value and (none_of_the_above==False or a != "None of the above")]
 
            options = random.sample(ops, 3)

            q = f"What is the status of {desc.text}?"
            
            a = correct_value if not none_of_the_above else "None of the above"
            options.append(a)
            random.shuffle(options)
        
    
            cot_reasoning = format_cot_answer(
                desc=desc,
                other_tls=other_tls,
                correct_value=props.get("status", None),
                is_pedestrian=is_pedestrian,
                formulated_answer=a, 
                timeline=timelines[node_label],
                graph_specs=graph_specs
            )
            if cot_reasoning==None: continue
            qa.append({
                "q": q,
                "a": a,
                "options": options, 
                "cot_reasoning": cot_reasoning
            })
          
            controlled_lanes.append(this_tl_controls)
            
    return qa
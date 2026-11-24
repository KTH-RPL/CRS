from qa.helpers.build_descriptors import build_descriptors_and_select
import random
from qa.helpers.localize_and_deconstruct import deconstruct_nested_descriptors, extract_node_descriptions, extract_views
from qa.helpers.definitions import PC_TYPE_VERBOSE

def format_cot_answer(desc, correct_style, formulated_answer, graph_specs):

    reasoning_steps = []
    stepcount = 1
    
    stepcount, reasoning_steps = deconstruct_nested_descriptors(reasoning_steps, stepcount, desc, graph_specs)
    
    if not "crossing marked with" in desc.text:
        views = extract_views(desc.node_label, graph_specs)
        if views:
            reasoning_steps[-1] = reasoning_steps[-1] + f" and is visible in the {views}."
        
        
    descriptors = extract_node_descriptions(desc, graph_specs, original_property=["marking_style", desc.property], original_relation=desc.relation)
   
    reasoning_steps.append(f"\n\nStep {stepcount}: ")
    stepcount += 1
    for descriptor in descriptors:
        reasoning_steps.append(descriptor["text"])
        
   
    if correct_style == "unmarked":
        reasoning_steps.append(f"\n\nStep {stepcount}: The area lacks painted transverse or longitudinal lines, indicating an unmarked crossing.")
    else:
        reasoning_steps.append(f"\n\nStep {stepcount}: The crossing is marked as a {correct_style} crossing.")
        
    
    if formulated_answer == "None of the above": reasoning_steps.append(f"\n\nConclusion: Since the correct pattern ({correct_style}) is not part of the available choices, the correct answer is {formulated_answer}.")
    else:reasoning_steps.append(f"\n\nConclusion: The correct answer is: {formulated_answer}.")
    
    return " ".join(reasoning_steps)

def generate_pc_type_questions(graph_specs):
    qa = []


    intersection_nodes = [
        (n, attrs) for n, attrs in graph_specs.G.nodes(data=True)
        if (attrs.get("type") or "").lower() == "intersection"
    ]
    
    if intersection_nodes:
        if len(intersection_nodes)!=1: return qa
        dist_to_ego = graph_specs.G.nodes[intersection_nodes[0][0]]["properties"]["distance_to_ego"]
        if dist_to_ego > 10 or dist_to_ego < 2:
            return qa
    if not intersection_nodes: return qa
        
    for node_label, attrs in graph_specs.G.nodes(data=True):
        node_type = attrs["type"]
        if node_type not in ["crossing"]: continue
        props = attrs["properties"]
        is_occluded = props["is_occluded"]
        if is_occluded: continue
  
        descs, _ = build_descriptors_and_select(graph_specs, node_label, n_items=1, allow_positions=True)

        if not descs:
            continue

        prop_key = "marking_style"
        
        for desc in descs:
            correct_value = props.get(prop_key, None)
            if correct_value == None: continue
            
            none_of_the_above = False
            if random.random() > 0.9: none_of_the_above = True
           
            
            verbose_lanes = {
                "None of the above": "None of the above",
                "zebra": "It is a zebra crossing",
                "ladder": "The crossing is marked in ladder style",
                "unmarked": "The crossing is unmarked",
                "white outlined rectangle": "The crossing consists of a white outlined rectangle"
            }
            
            ops = [verbose_lanes[a] for a in PC_TYPE_VERBOSE.keys() if a != correct_value and (none_of_the_above==False or a != "None of the above")]

            options = random.sample(ops, 3)

            questions = [
                f"What is the style of {desc.text}?", 
                f"How is {desc.text} marked?",
                f"What is the marking of {desc.text}?"]
            
            q = random.sample(questions, 1)[0]
            a = correct_value if not none_of_the_above else "None of the above"
            if a == '': continue
            options.append(verbose_lanes[a])
            random.shuffle(options)
            
            correct_value = props.get(prop_key, None)
            if correct_value == None: continue
            
            
            cot_reasoning = format_cot_answer(
                desc=desc,
                correct_style=correct_value,
                formulated_answer=verbose_lanes[a], 
                graph_specs=graph_specs
            )
            qa.append({
                "q": q,
                "a": verbose_lanes[a],
                "options": options, 
                "cot_reasoning": cot_reasoning
            })
         

    return qa
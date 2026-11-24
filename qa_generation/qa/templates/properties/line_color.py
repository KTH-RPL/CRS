from qa.helpers.build_descriptors import build_descriptors_and_select
import random
from core.graph_builder import collect_matches
from qa.helpers.definitions import LINE_COLORS, LINE_TYPES, VERBOSE_MARKS
from qa.helpers.localize_and_deconstruct import deconstruct_nested_descriptors, extract_node_descriptions, extract_views
from core.graph_builder import lane_split_in_frame


def format_cot_answer(desc, relation, formulated_answer, correct_value, line_label, graph_specs):
    reasoning_steps = []
    stepcount=1
    
    stepcount, reasoning_steps = deconstruct_nested_descriptors(reasoning_steps, stepcount, desc, graph_specs)
    
    view_string = extract_views(desc.node_label, graph_specs)
    if view_string:
        reasoning_steps[-1] = reasoning_steps[-1] + f" and is visible in the {view_string}."
    descriptors = extract_node_descriptions(desc, graph_specs, original_relation=[relation, desc.relation], original_property=desc.property)
   
    reasoning_steps.append(f"\n\nStep {stepcount}: ")
    stepcount += 1
    for descriptor in descriptors:
        reasoning_steps.append(descriptor["text"])
        
    view_string_marking = extract_views(line_label, graph_specs)    
    if not view_string_marking: 
        return "", False
    reasoning_steps.append(f"\n\nStep {stepcount}: Finally, the lane marking in question is located in the {view_string_marking}. It is {correct_value}.")    
        
    reasoning_steps.append(f"\n\nConclusion: the correct answer is '{formulated_answer}'.")
    
    return " ".join(reasoning_steps), True

def generate_line_marking_style_questions(graph_specs, variant):
    qa = []
    if lane_split_in_frame(graph_specs.G): return qa
   
    relations = ["is left marking of", "is right marking of"]
    matches = []
    for relation in relations:
        matches += collect_matches(graph_specs.G,"lane_line", "lane", lambda x: x == relation)
        
    all_match = [(m[1], m[2]) for m in matches]
    if len(all_match) != len(list(set(all_match))): return qa

    allowed_nodes = [n[1] for n in matches]

    variants = {
        "type":  {"target": "lane line type"},
        "color": {"target": "lane line color"},
        "all":   {"target": "lane line marking"}
    }
    for idx, node_label in enumerate(allowed_nodes):
        attrs = graph_specs.G.nodes[node_label]
        line_label = matches[idx][0]
        line = graph_specs.G.nodes[line_label]
        props_line = line["properties"]
        props_lane = attrs["properties"]

        mark_type = props_line.get("mark_type", None)
        is_occluded = props_lane["is_occluded"]
        if mark_type == None or is_occluded: continue
        
        descs, _ = build_descriptors_and_select(graph_specs, node_label, n_items=1, allow_positions=False, allow_vehicle_pointers=True)
        
        for desc in descs:
            side = "left" if "left" in matches[idx][2] else "right"
            q = f"What is the {side} {variants[variant]['target']} of {desc.text}?"
            correct_value = mark_type
            none_of_the_above = False
            if random.random() > 0.9: none_of_the_above = True
            if variant == "all":   
                options = list(set([v for k,v in VERBOSE_MARKS.items() if (not k == correct_value) and (none_of_the_above==False or k != "None of the above")]))
                a = VERBOSE_MARKS[correct_value] if not none_of_the_above else "None of the above"
            if variant == "color": 
                options_all = list(set(LINE_COLORS.values()))
                options = [v for v in options_all if  (v != LINE_COLORS[correct_value] )]
                a = LINE_COLORS[correct_value]
            if variant == "type":
                options_all = ["solid", "dashed", "double solid", "double dashed", "There is no lane line visible", "None of the above"]
                options = [v for v in options_all if  (v != LINE_TYPES[correct_value] and (none_of_the_above==False or v != "None of the above"))]
                a = LINE_TYPES[correct_value] if not none_of_the_above else "None of the above"
            random.shuffle(options)
            options = [o for o in options if o != a]
            options = options[:3]
            
            options.append(a)
            random.shuffle(options)
     
            cot_reasoning, valid = format_cot_answer(
                desc=desc,
                relation=(f"is marked to the {side} with",line_label),
                formulated_answer=a, 
                correct_value=correct_value,
                graph_specs=graph_specs, 
                line_label=line_label
            )
            if not valid: 
                continue
            qa.append({
                "q": q,
                "a": a,
                "options": options,
                "cot_reasoning": cot_reasoning
            })
            
            
            
    

    
    return qa

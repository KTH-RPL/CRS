
from collections import Counter
import random
from core.graph_builder import collect_matches
from core.graph_builder import lane_split_in_frame
from qa.helpers.definitions import verbose_direction, idx_to_letter
import numpy as np
from qa.helpers.localize_and_deconstruct import extract_node_descriptions, extract_views
from qa.helpers.helpers_counting import get_intro_sentence, retreive_all_lanes

def construct_question(relation):
    if relation == "same":
        return "How many lanes are there in ego direction?"
    if relation == "opposite":
        return "How many lanes are there in direction opposite to the ego?"

def _present_counts_from_matches(G, matches):
    cntr = Counter()
    nodes = []
    for match, _ in matches:
        props = G.nodes[match].get("properties") or {}
        t = props.get("type")
        cntr[t] += 1
        nodes.append(match)
    return cntr, nodes

def format_sentence(number, direction):
    location = verbose_direction(direction)
    if number == 0:
        return random.choice(
            [
                f"There are no lanes {location}",
                f"This is a one-way street, so there are no lanes {location}",
                f"There are zero lanes {location}",
            ] )
    if number == 1:
        return random.choice(
            [
                f"There is just one lane {location}",
                f"There is exactly one lane {location}",
                f"There is one lane {location}",
            ] )    
    if number > 1:
        return random.choice(
            [
                f"There are {number} lanes {location}",
                f"{location.capitalize()} there are {number} lanes",
            ] )    
        


def format_cot_answer(nodes, formulated_answer, options, graph_specs):
    reasoning_steps = []
    stepcount = 1
    random.shuffle(nodes)

    descs, start_from_ego = retreive_all_lanes(graph_specs, nodes)
    reasoning_steps.append(f"Step {stepcount}: To determine the number of lanes, I start by examining the most recent frame (Frame 3).")
    stepcount+=1
    old_node_labels = []
    for idx, entry in enumerate(descs):
        desc = entry["desc"]
        node_label = desc[0].node_label
        is_ego = True if idx == 0 and start_from_ego else False
        intro_sentence = get_intro_sentence(node_label, idx, graph_specs.G, old_node_labels, is_ego)  
        orig_desc = desc
        if is_ego: desc = [d for d in desc if d.text != "the ego lane"]
        potential_descriptors = [d for d in desc if not "marked with" in d.text and not True in ["lane"==D["type"] for D in d.dependants]]
        not_unique = False
        if entry["is_anchor"]==True and len(potential_descriptors)>0: 
            lane_desc = random.choice(potential_descriptors)
        elif len(potential_descriptors)>0: 
            not_unique = True
            lane_desc = random.choice([d for d in desc])
        else: 
            not_unique = True
            lane_desc = orig_desc[0]
        view_string = extract_views(node_label, graph_specs)
        reasoning_steps.append(f"\n\nStep {stepcount}: {intro_sentence}{f'{lane_desc.text}, ' if not_unique==False else ''}which I call 'Lane {idx+1}'. Considering the images, the lane is visible in the {view_string}.")
        stepcount+=1
        original_property = ["direction"]
        original_relation = []
        if not_unique==False: 
            original_property.append(lane_desc.property)
            original_relation = [lane_desc.relation]
        if is_ego: original_relation.append(("contains", "Ego"))
        descriptors = extract_node_descriptions(lane_desc, graph_specs, original_property=original_property, original_relation=original_relation)
        for descriptor in descriptors:
            reasoning_steps.append(descriptor["text"])
        same = True if graph_specs.G.nodes[node_label]["properties"]["direction"]=="same" else False
        reasoning_steps.append(f"Traffic in this lane moves {'away from ' if same else 'towards '}the camera.")
        old_node_labels.append(node_label)
    
    
 

    idx = options.index(formulated_answer)
    reasoning_steps.append(f"\n\nConclusion: I found {len(nodes)} relevant lane(s). Therefore, the correct answer is option {idx_to_letter[idx]}:'{formulated_answer['text']}'")

    return " ".join(reasoning_steps)


def generate_counting_questions_off_intx(graph_specs):
    """
    Lane/intersection counting questions focused on lane types.
    Returns items where 'a' is a verbose correct sentence and 'options' are decoys.
    """
    qa = []
    
    if "lane" not in graph_specs.complete_types:
        return []
    
    if lane_split_in_frame(graph_specs.G): return qa
    
    intersection_nodes = [
        (n, attrs) for n, attrs in graph_specs.G.nodes(data=True)
        if (attrs.get("type") or "").lower() == "intersection"
    ]
    if intersection_nodes:
        if len(intersection_nodes) != 1:
            return qa
        distance_to_intersection = intersection_nodes[0][1]["properties"]["distance_to_ego"]
        if distance_to_intersection < 5:
            return qa
        

    if intersection_nodes:
        matches_leads_up_to = collect_matches(graph_specs.G, "lane", "intersection", lambda x: x == "leads up to")
        matches_leaves = collect_matches(graph_specs.G, "lane", "intersection", lambda x: x == "leaves")
        allowed_lanes = [m[0] for m in matches_leaves] + [m[0] for m in matches_leads_up_to]        
    
    directions = ["same", "opposite"]
    for direction in directions:
        matches = collect_matches(graph_specs.G, source="lane", property=("direction", direction))
        matches_opposite = collect_matches(graph_specs.G, source="lane", property=("direction", "opposite" if direction=="same" else "same"))
        if intersection_nodes: 
            matches = [m for m in matches if m[0] in allowed_lanes]
            matches_opposite = [m for m in matches_opposite if m[0] in allowed_lanes]
        question = construct_question(direction)
        true_counts, nodes = _present_counts_from_matches(graph_specs.G, matches)
        true_counts_opp, _ = _present_counts_from_matches(graph_specs.G, matches_opposite)
        
        true_number = int(np.sum(list(true_counts.values())))
        true_number_opp = int(np.sum(list(true_counts_opp.values())))
      
        formulated_answer = {"text":format_sentence(true_number, direction), "counts": true_counts}

        if true_number+true_number_opp==0: continue
        decoys_range = range(0,np.max((6,true_number)))
        decoys = [d for d in decoys_range if (d >= 0 and int(d) != int(true_number))]
        if direction == "same": 
            if 0 in decoys: decoys.remove(0)
        random.shuffle(decoys)
        
        options = [{"text": format_sentence(d, direction), "counts": d} for d in decoys]
        
        none_of_the_above = False
        if random.random() > 0.9: none_of_the_above = True
        
        if none_of_the_above == True: 
            formulated_answer = {"text":"None of the above"}
        else: 
            if random.random() > 0.7: 
                options = options[:-1] + [{"text":"None of the above"}]
           
        if len(options)<3: continue
        options = random.sample(options,3) + [formulated_answer]        
        random.shuffle(options)
        cot_reasoning = format_cot_answer(
            nodes=nodes,
            formulated_answer=formulated_answer,
            options=options, 
            graph_specs=graph_specs
        )
        
        qa.append({
            "q": question,
            "a": formulated_answer["text"],
            "options": [o["text"] for o in options],
            "cot_reasoning": cot_reasoning
        })

        
     
        
    return qa
        
      
    
    
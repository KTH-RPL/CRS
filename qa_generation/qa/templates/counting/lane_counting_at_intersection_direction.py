
from collections import Counter
import random
from core.graph_builder import lane_split_in_frame
from core.graph_builder import collect_matches
from qa.helpers.helpers_lane import format_type_answer_sentence
from qa.helpers.localize_and_deconstruct import extract_node_descriptions, extract_views
from qa.helpers.definitions import OTHER_DIRECTION_LANE, direction_phrase_from_relation, normalize_lane_direction, idx_to_letter, verbose_direction
from qa.helpers.helpers_counting import get_intro_sentence, retreive_all_lanes

def present_direction_counts_from_matches(matches):
    dir_counts = Counter()
    nodes = []
    for match, _, relation in matches:
        nodes.append(match)
        key = relation
        dir_counts[key] += 1
    return dir_counts, nodes

def format_cot_answer(relation, matches, true_counts, formulated_answer, options, graph_specs):
    reasoning_steps = []
    stepcount = 1
    nodes = [m[0] for m in matches]
    descs, start_from_ego = retreive_all_lanes(graph_specs, nodes)
    reasoning_steps.append(f"Step {stepcount}: To determine the number of lanes {direction_phrase_from_relation(relation)}, I start by examining the most recent frame (Frame 3).")
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
        
        old_node_labels.append(node_label)

        reasoning_steps.append(f"Traffic in this lane moves {verbose_direction(graph_specs.G.nodes[node_label]['properties']['direction'])}.")
  

    reasoning_steps.append(f"\n\nStep {stepcount}: Based on these observations, I count exactly {len(old_node_labels)} lanes. Out if these, {true_counts[relation[0]]} travel away from the camera and {true_counts[relation[1]]} travel towards the camera.")   
    
    idx = options.index(formulated_answer)
    reasoning_steps.append(f"\n\nConclusion: Therefore, the correct answer is option {idx_to_letter[idx]}:'{formulated_answer['text']}'")

    return " ".join(reasoning_steps)



def generate_counting_questions_direction(graph_specs):
    """
    Lane/intersection counting questions focused on lane types.
    Returns items where 'a' is a verbose correct sentence and 'options' are decoys.
    """
    qa = []
    
    if "lane" not in graph_specs.complete_types:
        return qa
    
    if lane_split_in_frame(graph_specs.G): return qa
    
    intersection_nodes = [
        (n, attrs) for n, attrs in graph_specs.G.nodes(data=True)
        if (attrs.get("type") or "").lower() == "intersection"
    ]
    if len(intersection_nodes) != 1:
        return qa
    
    dist_to_ego = intersection_nodes[0][1]["properties"]["distance_to_ego"]
     
    seen = set()
    relations = [
        (k, v)
        for k, v in OTHER_DIRECTION_LANE.items()
        if not (tuple(sorted((k, v))) in seen or seen.add(tuple(sorted((k, v)))))
    ]

    
    
    for relation in relations:
        matches = collect_matches(graph_specs.G, "lane", "intersection", lambda x: x == relation[0] or x == relation[1])
        true_counts, _ = present_direction_counts_from_matches(matches)

        if relation[0] in ["leaves to the left of", "leaves to the right of", "approaches to the left of", "approaches to the right of"]:
            if dist_to_ego > 2 or dist_to_ego == 0: continue
        elif relation[0] in ["leaves behind of", "approaches behind of"]:
            if dist_to_ego > 10: continue
        elif relation[0] in ["leads up to", "leaves"]:
            if dist_to_ego < 2: continue
        
        phrase="in total"
        if relation[0] in ["leaves behind of", "approaches behind of","leads up to", "leaves"]:  
            phrase = "main_road"
           
        question = f"How many lanes are there {direction_phrase_from_relation(relation)}?"
        if sum(true_counts.values()) == 0: continue
        formulated_answer = {"text":format_type_answer_sentence(sum(true_counts.values()), phrase, true_counts, normalize_lane_direction), "counts": true_counts}


        rel_0 = true_counts[relation[0]]
        rel_1 = true_counts[relation[1]]
        low_0 = 1 if relation[0] == "leads up to" else 0
        low_1 = 1 if relation[1] == "leads up to" else 0
        def make_option(r0, r1):
            if r0 == r1 == 0:
                return None
            if r0 == rel_0 and r1 == rel_1:
                return None
            if r0 == 0:
                counter = Counter({
                    relation[1]: r1,
                })
            elif r1 == 0:
                counter = Counter({
                    relation[0]: r0
                })
            else:
                counter = Counter({
                    relation[0]: r0,
                    relation[1]: r1,
                })
            return {
                "counts": counter,
                "text": format_type_answer_sentence(
                    sum(counter.values()),
                    phrase,
                    counter,
                    normalize_lane_direction,
                ),
            }
        local_options = []
        for r0 in range(max(low_0, rel_0 - 2), max(3, rel_0 + 3)):
            for r1 in range(max(low_1, rel_1 - 2), max(3, rel_1 + 3)):
                opt = make_option(r0, r1)
                if opt is not None:
                    local_options.append(opt)  
        max_count = 4
        global_options = []
        for r0 in range(low_0, max_count + 1):
            for r1 in range(low_1, max_count + 1):
                opt = make_option(r0, r1)
                if opt is not None:
                    global_options.append(opt)    
        random.shuffle(local_options)              
        random.shuffle(global_options) 
        options = local_options[:2]+global_options[:1]             
        
        
        none_of_the_above = False
        if random.random() > 0.9: none_of_the_above = True
        if none_of_the_above == True: formulated_answer = {"text":"None of the above"}
        else: 
            if random.random() > 0.7: 
                options = options[:-1] + [{"text":"None of the above"}]
        options = random.sample(options + [formulated_answer], len(options + [formulated_answer]))
     
        cot_reasoning = format_cot_answer(
            relation=relation,
            matches=matches,
            true_counts=true_counts,
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
        
      
    
    
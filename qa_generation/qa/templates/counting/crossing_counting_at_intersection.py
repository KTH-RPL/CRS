
from collections import Counter
import random
from qa.helpers.helpers_crossing import format_type_answer_sentence, make_decoy_sentences_crossing
from qa.helpers.definitions import join_with_and
from qa.helpers.localize_and_deconstruct import extract_node_descriptions, extract_views
from qa.helpers.definitions import idx_to_cardinal, idx_to_letter


def format_cot_answer(true_counts, nodes, formulated_answer, options, graph_specs):
    class Desc:
        def __init__(self, node_label):
            self.node_label = node_label
            
    reasoning_steps = []
    stepcount=1
    
    reasoning_steps.append(f"Step {stepcount}: To determine the number of crossings present, I start by examining the most recent frame (Frame 3).")
    stepcount+=1

    for idx, node_label in enumerate(nodes):
        
        view_string = extract_views(node_label, graph_specs)
        desc_ = Desc(node_label=node_label)
        descriptors = extract_node_descriptions(desc_, graph_specs)
        
        reasoning_steps.append(f"\n\nStep {stepcount}:  I detect a {idx_to_cardinal[idx]} crossing, which I call 'Crossing {idx+1}' in the {view_string}.")
        for descriptor in descriptors:
            reasoning_steps.append(descriptor["text"])
        stepcount+=1
       
      
    true_total = sum(true_counts.values())
    reasoning_steps.append(f"\n\nStep {stepcount}: In total, I have identified {true_total} pedestrian crossing(s).")

    reasoning_steps.append("Now, let's evaluate the options:")
    
    ans_text = formulated_answer["text"] if isinstance(formulated_answer, dict) else formulated_answer

    for idx, opt in enumerate(options):
        opt_text = opt["text"] if isinstance(opt, dict) else opt
        
        if opt_text == ans_text:
            continue

        if opt_text == "None of the above":
            reasoning_steps.append(
                f"Option {idx_to_letter[idx]} is incorrect because the observed crossings match one of the descriptive options provided."
            )
            continue

        opt_counts = opt.get("counts", Counter()) if isinstance(opt, dict) else Counter()
        opt_total = sum(opt_counts.values())

        if opt_total != true_total:
            reasoning_steps.append(
                f"Option {idx_to_letter[idx]} is incorrect because it suggests there are {opt_total} crossings"
            )
       
        else:
            mismatches = []
            for loc, count in opt_counts.items():
                if true_counts[loc] < count:
                    mismatches.append(f"incorrectly claims there is a {loc}")
                elif true_counts[loc] > count:
                    mismatches.append(f"omits the {loc}")
            
            if not mismatches:
                reasoning_steps.append(
                    f"Option {idx_to_letter[idx]} is incorrect because it misidentifies the specific layout of the crossings."
                )
            else:
                reasoning_steps.append(
                    f"Option {idx_to_letter[idx]} is incorrect because it {join_with_and(mismatches)}."
                )

    correct_idx = -1
    for i, o in enumerate(options):
        t = o["text"] if isinstance(o, dict) else o
        if t == ans_text:
            correct_idx = i
            break
            
    reasoning_steps.append(f"\n\nConclusion: Therefore, the correct answer is option {idx_to_letter[correct_idx]}: '{ans_text}'.")

    return " ".join(reasoning_steps)

def present_direction_counts_from_matches(G, matches):
    dir_counts = Counter()
    nodes = []
    for match in matches:
        nodes.append(match)
        key = G.nodes[match]["properties"]["description"]
        dir_counts[key] += 1
    return dir_counts, nodes

def present_general_counts_from_matches(matches):
    dir_counts = Counter()
    nodes = []
    for match in matches:
        nodes.append(match)
        dir_counts["general"] += 1
    return dir_counts, nodes

def generate_counting_questions_crossing(graph_specs):
    """
    Lane/intersection counting questions focused on lane types.
    Returns items where 'a' is a verbose correct sentence and 'options' are decoys.
    """
    qa = []
    
    if "crossing" not in graph_specs.complete_types:
        return []

    matches = [n for n in graph_specs.G.nodes() if graph_specs.G.nodes[n]["type"]=="crossing" ]
    occluded = [graph_specs.G.nodes[n]["properties"]["is_occluded"] for n in matches]
    described = [graph_specs.G.nodes[n]["properties"].get("description", "") != "" for n in matches]
    
    if True in occluded: return qa
    
    intersection_nodes = [
        (n, attrs) for n, attrs in graph_specs.G.nodes(data=True)
        if (attrs.get("type") or "").lower() == "intersection"
    ]
    
    if intersection_nodes:
        dist_to_ego = graph_specs.G.nodes[intersection_nodes[0][0]]["properties"]["distance_to_ego"]
        if dist_to_ego > 10:
            return qa
        if dist_to_ego < 2:
            return qa
        
    question = "How many pedestrian crossings are there?"
    
    if not False in described: 
        true_counts, nodes = present_direction_counts_from_matches(graph_specs.G, matches)
    else: 
        true_counts, nodes = present_general_counts_from_matches(matches)
    
    if sum(true_counts.values())==0: return qa
    formulated_answer = {"text": format_type_answer_sentence(sum(true_counts.values()))}
    
    if False in described:
        option_numbers = [0,1,2,3,4]
        option_numbers = [o for o in option_numbers if o != sum(true_counts.values())]
        options = []
        for count in option_numbers: 
            options.append({"text":format_type_answer_sentence(count), "counts": Counter({"general":count})})
        random.shuffle(options)
        options = options[:3]
        
    else:
        global_types = ["crossing to the left", "crossing to the right", "crossing straight ahead", "crossing at the far side"]
        options = make_decoy_sentences_crossing(
            true_counts=true_counts,
            nodes=nodes,
            G=graph_specs.G,
            global_types=global_types,
            key="description",
            k=3,
            p_delete=0.7,
            p_add=0.1,
            p_change=0.6,
            p_mixed=0.0,
            rng=random.Random(random.getrandbits(64))
        )
        
    none_of_the_above = False
    if random.random() > 0.9: none_of_the_above = True
    
    if none_of_the_above == True: formulated_answer = {"text":"None of the above"}
    else: 
        if random.random() > 0.7: 
            options = options[:-1] + [ {"text":"None of the above"}]  
                 
    options = random.sample(options + [formulated_answer], len(options + [formulated_answer]))        
    cot_reasoning = format_cot_answer(
        true_counts=true_counts,
        nodes=nodes,
        formulated_answer=formulated_answer,
        options=options, 
        graph_specs=graph_specs
        )
    
    qa.append({
        "q": question,
        "a": formulated_answer["text"],
        "cot_reasoning": cot_reasoning,
        "options": [o["text"] for o in options],
    })
    

    return qa
        
      
    
    
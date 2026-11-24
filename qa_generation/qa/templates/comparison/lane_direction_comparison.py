from qa.helpers.build_descriptors import build_descriptors_and_select
import random
import re
from core.graph_builder import collect_matches
from qa.helpers.localize_and_deconstruct import deconstruct_nested_descriptors, extract_node_descriptions, extract_views
from core.graph_builder import lane_split_in_frame
from qa.helpers.definitions import idx_to_cardinal

def format_cot_answer(desc1, desc2, property, formulated_answer, graph_specs):
    reasoning_steps = []
    stepcount = 1
    
    for idx, desc in enumerate([desc1, desc2]):
        reasoning_steps.append(f"Step {stepcount}: I look at the {idx_to_cardinal[idx]} lane in question.")
        stepcount, reasoning_steps_new = deconstruct_nested_descriptors([], stepcount, desc, graph_specs)
        for idx_ in range(len(reasoning_steps_new)):
            reasoning_steps_new[idx_] = re.sub(r'\n?\n?Step \d+: ', '', reasoning_steps_new[idx_])
        reasoning_steps+=reasoning_steps_new
        view_string = extract_views(desc.node_label, graph_specs)
        if view_string:
            reasoning_steps[-1] = reasoning_steps[-1] + f". Looking at the images, the lane is visible in the {view_string}."
        
        descriptors = extract_node_descriptions(desc, graph_specs, original_property=[property, desc.property], original_relation=desc.relation)
        stepcount += 1
        for descriptor in descriptors:
            reasoning_steps.append(descriptor["text"])
        same = True if graph_specs.G.nodes[desc.node_label]["properties"]["direction"]=="same" else False
        reasoning_steps.append(f"Traffic in this lane moves {'away from ' if same else 'towards '}the camera.")    
        reasoning_steps[-1]=reasoning_steps[-1]+"\n\n"    
        
    reasoning_steps.append(f"Conclusion: Hence, the correct answer is {formulated_answer}")
    
    return " ".join(reasoning_steps), True



forbidden_descriptor_pairs = ("the lane that is right of the lane that contains the ego", "the lane that contains the ego", "the ego lane")
    
forbidden_parts = [
    "the lane that approaches to the left of the intersection",
    "the lane that approaches to the right of the intersection",
    "the lane that leads up to the intersection",
    "the lane that approaches behind of the intersection",
    "the lane that leaves the intersection",
    "the lane that is right of the ego lane",
    "the lane that leaves behind of the intersection",
    "the lane that leaves to the right of the intersection",
    "the lane that leaves to the left of the intersection", 
    "of the double solid median", 
    "leftmost lane", "right curb lane",
    "rightmost lane", "left curb lane", "the lane marked with"
]
def discard_descs(desc):
    discard = False
    for fp in forbidden_parts:
        if fp in desc.text: discard = True
    if discard == True: return True
    return False  
        
def generate_pairwise_direction_comparison_questions(graph_specs):
    """
    Generate pairwise comparison questions using recursive node descriptors.
    """

    qa = []
    
    if lane_split_in_frame(graph_specs.G): return qa
    nodes_by_type = {}
    relations = [("leaves to the left of", "approaches to the left of"), ("leaves to the right of", "approaches to the right of")]
    matches = []
    for relation in relations:
        matches += collect_matches(graph_specs.G, "lane", "intersection", lambda x: x == relation[0] or x == relation[1])
    lanes_to_discard = [m[0] for m in matches]
    
    
    for node_label, attrs in graph_specs.G.nodes(data=True):
        if attrs["type"] != "lane":
            continue
        if node_label in lanes_to_discard:
            continue
        t = attrs.get("type")
        nodes_by_type.setdefault(t, []).append(node_label)

    for t, nodes in nodes_by_type.items():
        if len(nodes) < 2:
            continue
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                n1, n2 = nodes[i], nodes[j]
                
                props1 = graph_specs.G.nodes[n1]["properties"]
                props2 = graph_specs.G.nodes[n2]["properties"]
                is_occluded_1 = props1["is_occluded"]
                is_occluded_2 = props2["is_occluded"]
                if is_occluded_1 or is_occluded_2: continue

                descs1, _ = build_descriptors_and_select(graph_specs, n1, n_items=1, allow_positions=True, allow_vehicle_pointers=True, special_selector=discard_descs)
                descs2, _ = build_descriptors_and_select(graph_specs, n2, n_items=1, allow_positions=True, allow_vehicle_pointers=True, special_selector=discard_descs)

                if not descs1 or not descs2:
                    continue

                for d1 in descs1:
                    for d2 in descs2:
                        if d1 == forbidden_descriptor_pairs[0] and d2 == forbidden_descriptor_pairs[1]: continue
                        if d1 == forbidden_descriptor_pairs[1] and d2 == forbidden_descriptor_pairs[0]: continue
                        prop = "direction"

                        v1 = props1[prop]
                        v2 = props2[prop]

                        q = f"Do {d1.text} and {d2.text} share the same {prop}?"

                        if d1.text in ["the lane that contains the ego", "the ego lane",  "the lane that is right of the lane that contains the ego", "the lane that is right of the ego lane"]:
                            options = [
                                "Yes, both are in ego direction.",
                                "No, the first lane is in ego direction and the second lane in direction opposite to the ego.",
                            ]
                            if v1 == v2:
                                correct = "Yes, both are in ego direction."     
                            else:
                                correct = "No, the first lane is in ego direction and the second lane in direction opposite to the ego."
                            cot_reasoning, _ = format_cot_answer(
                                desc1=d1, 
                                desc2=d2, 
                                property="direction",
                                formulated_answer=correct,
                                graph_specs=graph_specs
                            )
                            qa.append({
                            "q": q,
                            "a": correct,
                            "options": options,
                            "cot_reasoning": cot_reasoning
                            })  
                            continue  
                        if d2.text in ["the lane that contains the ego", "the ego lane", "the lane that is right of the lane that contains the ego", "the lane that is right of the ego lane"]:
                            options = [
                                "Yes, both are in ego direction.",
                                "No, the first lane is in direction opposite to the ego and the second lane in ego direction.",
                            ]
                            if v1 == v2:
                                correct = "Yes, both are in ego direction."     
                            else:
                                correct = "No, the first lane is in direction opposite to the ego and the second lane in ego direction."
                            cot_reasoning, _ = format_cot_answer(
                                desc1=d1, 
                                desc2=d2, 
                                property="direction",
                                formulated_answer=correct,
                                graph_specs=graph_specs
                            )
                            qa.append({
                                "q": q,
                                "a": correct,
                                "options": options, 
                                "cot_reasoning": cot_reasoning
                            })
                            continue
                        options = [
                            "Yes, both are in ego direction.",
                            "Yes, both are in direction opposite to the ego.",
                            "No, the first lane is in ego direction and the second lane in direction opposite to the ego.",
                            "No, the first lane is in direction opposite to the ego and the second lane in ego direction.",
                        ]
                        if v1 == v2:
                            if v1 == "same":
                                correct = "Yes, both are in ego direction."
                            else:
                                correct = "Yes, both are in direction opposite to the ego."
                            
                        else:
                            if v1 == "same":
                                correct = "No, the first lane is in ego direction and the second lane in direction opposite to the ego."
                            else:
                                correct = "No, the first lane is in direction opposite to the ego and the second lane in ego direction."
                            
                        options = [o for o in options if o != correct]     
                        random.shuffle(options)   
                        none_of_the_above = False
                        if random.random() > 0.9: none_of_the_above = True
                        
                        if none_of_the_above == True: 
                            correct = "None of the above"
                        else: 
                            if random.random() > 0.7: 
                                options = options[:-1] + ["None of the above"]
        
                        options = options + [correct]
                        random.shuffle(options)
                        
                        cot_reasoning, _ = format_cot_answer(
                            desc1=d1, 
                            desc2=d2, 
                            property="direction",
                            formulated_answer=correct,
                            graph_specs=graph_specs
                        )
                        qa.append({
                            "q": q,
                            "a": correct,
                            "options": options,
                            "cot_reasoning": cot_reasoning
                        })

                        

    return qa
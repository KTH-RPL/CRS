
import random
from qa.helpers.localize_and_deconstruct import extract_views


verbose_pcs = {
            "zebra": "Yes, marked as a zebra crossing",
            "ladder": "Yes, marked in ladder style",
            "unmarked": "Yes, but it is unmarked",
            "white outlined rectangle": "Yes, marked as a white outlined rectangle",
        }


def format_cot_answer(requested_location, matches, formulated_answer, graph_specs):
    reasoning_steps = []
    stepcount=1
    reasoning_steps.append(f"Step {stepcount}: I am tasked to identify if there is a {requested_location} {'of' if not 'straight ahead' in requested_location else 'on'} the intersection, and determine its potential marking style.")
    stepcount += 1
    requested_location_to_cam = {
        "crossing to the left": "to the left of",
        "crossing to the right": "to the right of",
        "crossing at the far side": "at the far side of",
        "crossing straight ahead": "straight ahead on"
    }
    
    hits = {}
    for m in matches:
        attrs = graph_specs.G.nodes[m]["properties"]
        desc = attrs.get("description", "crossing")
        style = attrs.get("marking_style", None)
        hits[desc]={}
        view_string = extract_views(m, graph_specs)
        hits[desc]["views"] = view_string
        hits[desc]["style"] = style
        
     
    target_match = hits.get(requested_location, None)    
    if not target_match:
        reasoning_steps.append(f"\n\nStep {stepcount}: Analyzing the sequence of frames and their camera views. There is no crossing {requested_location_to_cam[requested_location]} the intersection.")
        stepcount+=1
        reasoning_steps.append(f"\n\nStep {stepcount}: Examining the other sides of the intersection.")
       
        for key, hit in hits.items():
            reasoning_steps.append(f"I identify a {key} located in {hit['views']}.")
            if hit["style"] != None:   reasoning_steps.append(f"It's marking style is {hit['style']}.")
    
    else:
        location = target_match["views"]
        reasoning_steps.append(f"\n\nStep {stepcount}: Analyzing the sequence of frames and their camera views. I detect a {requested_location} of the intersection, visible in {location}.")
        stepcount+=1
        if target_match["style"] != None: reasoning_steps.append(f"\n\nStep {stepcount}: Determining the marking style. This crosswalk is a {target_match['style']} crossing.")
         
    reasoning_steps.append(f"\n\nConclusion: Therefore, the correct answer is option '{formulated_answer}'.")
    return " ".join(reasoning_steps)

def generate_existence_questions_crossing(graph_specs):
    """
    Lane/intersection counting questions focused on lane types.
    Returns items where 'a' is a verbose correct sentence and 'options' are decoys.
    """
    qa = []
    
    if "crossing" not in graph_specs.complete_types:
        return []

    intersection_nodes = [
        (n, attrs) for n, attrs in graph_specs.G.nodes(data=True)
        if (attrs.get("type") or "").lower() == "intersection"
    ]
    
    if not intersection_nodes: return qa
    if intersection_nodes:
        dist_to_ego = graph_specs.G.nodes[intersection_nodes[0][0]]["properties"]["distance_to_ego"]
        if dist_to_ego > 9:
            return qa
        if dist_to_ego < 1:
            return qa
        
    matches = [n for n in graph_specs.G.nodes() if graph_specs.G.nodes[n]["type"]=="crossing" ]
    described = [graph_specs.G.nodes[n]["properties"].get("description", "") for n in matches if graph_specs.G.nodes[n]["properties"].get("description", "")!=""]
    if len(matches)!=len(described): 
        return qa
    
    for location in ['crossing to the right', 'crossing to the left', 'crossing straight ahead', 'crossing at the far side']:
        exists = False
        occluded_ = False
        for match in matches: 
            descs = graph_specs.G.nodes[match]["properties"]["description"] 
            if descs == location: 
                exists = True      
                occluded = graph_specs.G.nodes[match]["properties"]["is_occluded"] 
                if occluded: occluded_ = True
                marking = graph_specs.G.nodes[match]["properties"].get("marking_style", None)
                break
        if occluded_: continue

        q = f"Is there a {location} {'of' if location !=  'crossing straight ahead' else 'on'} the intersection?"        
        
        no_options_dict = {
            "crossing to the left": "No, but there is one to the left",
            "crossing to the right": "No, but there is one to the right",
            "crossing straight ahead": "No, but there is one straight ahead",
            "crossing at the far side": "No, but there is one at the far side",
        }
        if exists: 
            if marking: 
                formulated_answer = {
                    "text": verbose_pcs[marking],
                    "metadata": {"exists": True, "marking": marking}
                }
                options = [{
                    "text": v,
                    "metadata": {"exists": True, "marking": k}
                } for k,v in verbose_pcs.items() if k != marking]
                no_options = [{
                    "text": v,
                    "metadata": {"exists": False, "marking": None}
                } for k,v in no_options_dict.items() if k != location]
                
         
                options = options + no_options
            else: 
                formulated_answer = {
                    "text": f"Yes, there is a {location}.",
                    "metadata": {"exists": True, "marking": None}
                }    
                options = [
                    {
                    "text": f"No, there is no {location}.",
                    "metadata": {"exists": False, "marking": None}
                } ]
                no_options = [{
                    "text": v,
                    "metadata": {"exists": False, "marking": None}
                } for k,v in no_options_dict.items() if k != location]
                options = options + no_options
        else: 
            no_options_true = []
            for match in matches: 
                descs = graph_specs.G.nodes[match]["properties"]["description"] 
                no_options_true.append(no_options_dict[descs])
            no_options_false = [{
                    "text": v,
                    "metadata": {"exists": False, "marking": None}
                } for k,v in no_options_dict.items() if v not in no_options_true and k != location]                           
            
            formulated_answers = [f"No, there is no {location}."] + no_options_true
            formulated_answer = random.choice(formulated_answers)
            formulated_answer = {
                    "text": formulated_answer,
                    "metadata": {"exists": False, "marking": None}
                }  
            options = [{
                    "text": v,
                    "metadata": {"exists": True, "marking": None}
                } for k,v in verbose_pcs.items()] + no_options_false
        
        random.shuffle(options)        
        options = options[:3]
        none_of_the_above = False
        if random.random() > 0.9: none_of_the_above = True
        
        if none_of_the_above == True: formulated_answer = {"text":"None of the above"}
        else: 
            if random.random() > 0.7: 
                options = options[:-1] + [ {"text":"None of the above"}]       

    
    
        options = options + [formulated_answer]
        random.shuffle(options)
        cot_reasoning = format_cot_answer(
            requested_location=location,
            matches=matches,
            formulated_answer=formulated_answer["text"],
            graph_specs=graph_specs
        )   
        
        
        qa.append({
            "q": q,
            "a": formulated_answer["text"],
            "cot_reasoning": cot_reasoning,
            "options": [o["text"] for o in options],
        })
      

    return qa
            

      
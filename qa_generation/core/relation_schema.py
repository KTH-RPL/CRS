
RELATIONS = {
    "is left of":                   {"bidirectional": True, "inverse": "is right of"},
    "is left marking of":           {"bidirectional": False, "inverse": "is marked to the left with"},
    "is right marking of":          {"bidirectional": False, "inverse": "is marked to the right with"},   
    "is in":                        {"bidirectional": True, "inverse": "contains"},
    "is on":                        {"bidirectional": True, "inverse": "contains"},
    "controls":                     {"bidirectional": False, "inverse": "is controlled by"},
    "is holding":                   {"bidirectional": False, "inverse": "is held by"},
    "is impacting":                 {"bidirectional": False, "inverse": "is impacted by"},
    "leads up to":                  {"bidirectional": True, "inverse": "is approached by"},
    "leaves":                       {"bidirectional": True, "inverse": "is left by"},
    "leaves behind of":             {"bidirectional": True, "inverse": "is left at the far side by"},
    "splits into":                  {"bidirectional": False, "inverse": "continues out of"},
    "is merging into":              {"bidirectional": True, "inverse": "is entered by"},
    "is changing into":             {"bidirectional": True, "inverse": "is entered by"},
    "is approaching":               {"bidirectional": True, "inverse": "is approached by"},
    "is riding on":                 {"bidirectional": True, "inverse": "contains"},
    "approaches to the right of":   {"bidirectional": True, "inverse": "is approached at the right side by"},
    "approaches to the left of":    {"bidirectional": True, "inverse": "is approached at the left side by"},
    "leaves to the right of":       {"bidirectional": True, "inverse": "is left at the right side by"},
    "leaves to the left of":        {"bidirectional": True, "inverse": "is left at the left side by"},
    "is crossing at":               {"bidirectional": True, "inverse": "is crossed by"},
    "is on the right side of":      {"bidirectional": True, "inverse": "is on the left side of"},
    "approaches behind of":         {"bidirectional": True, "inverse": "is approached at the far side by"},
    "is turning into":              {"bidirectional": True, "inverse": "is the target of"},
    "is the same lane as":          {"bidirectional": True, "inverse": "is the same lane as"},
    "are in":                       {"bidirectional": True, "inverse": "contains"}, 
    "cuts into":                    {"bidirectional": True, "inverse": "is agressively entered by"},
    "is waiting at":                {"bidirectional": True, "inverse": "is being approached by"},
    "is parked outside of":         {"bidirectional": False, "inverse": None},
    "turns right into":             {"bidirectional": False, "inverse": None},
    "turns left into":              {"bidirectional": False, "inverse": None},
    "continues ahead into":         {"bidirectional": False, "inverse": None},
    "leads to":                     {"bidirectional": False, "inverse": "is approached by"},
    "continues straight into":      {"bidirectional": False, "inverse": None},
    "is in the back right corner of":{"bidirectional": False, "inverse": None},
    "parked outside of":            {"bidirectional": False, "inverse": "is to the immediate side of"},
    "is crossing on":               {"bidirectional": False, "inverse": "is crossed by"},
}

def generate_full_schema(base_relations):
    full_schema = base_relations.copy()
    
    for key, value in base_relations.items():
        inverse_key = value["inverse"]
        
        if inverse_key != None and inverse_key not in full_schema:
            full_schema[inverse_key] = {
                "bidirectional": value["bidirectional"],
                "inverse": key
            }      
    return full_schema

RELATION_SCHEMA = generate_full_schema(RELATIONS)
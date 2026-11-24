import random 

ACTOR_TYPES   = ["regular_vehicle", "large_vehicle", "bicyclist","bus", "truck", "truck_cab", "box_truck", "cyclist", "motorcyclist", "motorcycle", "pedestrian", "vehicular_trailer", "articulated_bus", "official_signaler"]

VERBOSE_LANES = {
                "VEHICLE": "standard travel lane",
                "BUS": "lane reserved for bus",
                "BIKE": "bike lane",
                "BUS and BIKE": "lane reserved for bus and bikes",
                "VEHICLE share the road with BIKES": "standard travel lane shared with bikes",
                "VEHICLE share the road with BIKES and street parking": "standard travel lane with street parking shared with bikes",
                "VEHICLE with street parking": "standard travel lane with street parking", 
                "VEHICLE blocked due to construction work": "standard travel lane blocked due to construction work",
                "None of the above": "None of the above"
                }


VERBOSE_MARKS = {
                "DASH_SOLID_WHITE": "A dashed solid white lane line",
                "DASHED_WHITE": "A dashed white lane line",
                "DASHED_YELLOW": "A dashed yellow lane line",
                "DOUBLE_SOLID_YELLOW": "A double solid yellow median",
                "DOUBLE_SOLID_WHITE": "A double solid white median",
                "DOUBLE_DASH_YELLOW": "A double dashed yellow divider",
                "DOUBLE_DASH_WHITE": "A double dashed yellow divider",
                "SOLID_YELLOW": "A solid yellow divider",
                "SOLID_WHITE": "A solid white lane line",
                "SOLID_DASH_WHITE": "A solid dashed white lane line",
                "SOLID_DASH_YELLOW": "A solid dashed yellow lane line",
                "SOLID_BLUE": "A solid blue lane line",
                "NONE": "There is no lane line visible",
                "UNKNOWN": "There is no lane line visible", 
                "None of the above": "None of the above"
            }

LINE_COLORS  = {
                "DASH_SOLID_WHITE": "white",
                "DASHED_WHITE": "white",
                "DASHED_YELLOW": "yellow",
                "DOUBLE_SOLID_YELLOW": "yellow",
                "DOUBLE_SOLID_WHITE": "white",
                "DOUBLE_DASH_YELLOW": "yellow",
                "DOUBLE_DASH_WHITE": "white",
                "SOLID_YELLOW": "yellow",
                "SOLID_WHITE": "white",
                "SOLID_DASH_WHITE": "white",
                "SOLID_DASH_YELLOW": "yellow",
                "NONE": "none, since the lane line is implicit",
                "UNKNOWN": "none, since the lane line is implicit",
                "None of the above": "None of the above"
            }

LINE_TYPES  = {
            "DASH_SOLID_WHITE": "dashed solid",
            "DASHED_WHITE": "dashed",
            "DASHED_YELLOW": "dashed",
            "DOUBLE_SOLID_YELLOW": "double solid",
            "DOUBLE_SOLID_WHITE": "double solid",
            "DOUBLE_DASH_YELLOW": "double dashed",
            "DOUBLE_DASH_WHITE": "double dashed",
            "SOLID_YELLOW": "solid",
            "SOLID_WHITE": "solid",
            "SOLID_DASH_WHITE": "solid dashed",
            "SOLID_DASH_YELLOW": "solid dashed",
            "SOLID_BLUE": "solid",
            "NONE": "none, since the lane line is implicit",
            "UNKNOWN": "none, since the lane line is implicit",
            "None of the above": "None of the above"
        }


PC_TYPE_VERBOSE = {
            "zebra": "marked with thick, longitudinal white stripes painted parallel to the flow of traffic",
            "ladder": "marked with thick, longitudinal white stripes painted parallel to the flow of traffic (like a zebra crossing) but adds two solid white lines running perpendicular to the traffic",
            "unmarked": "not marked on the road, but the surrounding infrastructure (e.g., signs, markings, traffic lights) clearly imply its presence",
            "white outlined rectangle": "marked with white lines forming a rectangular grid",
            "None of the above": "None of the above"
        }

TL_TO_PEDESTRIAN = {
                    "red": "Don't Walk",
                    "green": "Walk",
                    "yellow": "Countdown Timer",
                    "unknown": "unknown"
                }


def direction_phrase_from_relation(d: str) -> str:
    if d == "leaves to the right of":
        return "leaving to the right of the intersection"
    if d == "approaches to the right of":
        return "approaching to the right of the intersection"
    if d == "leaves to the left of":
        return "leaving to the left of the intersection"
    if d == "approaches to the left of":
        return "approaching to the left of the intersection"
    if d == "approaches behind of":
        return "approaching at the far side of the intersection"
    if d == "leaves behind of":
        return "leaving at the far side of the intersection"
    if d == "leads up to":
        return "leading straight up to the intersection"
    if d == "leaves":
        return "leaving the intersection towards the ego"
    if d == ("leaves to the left of", "approaches to the left of") or d == ("approaches to the left of", "leaves to the left of"):
        return "approaching or leaving the intersection at the left side"
    if d == ("leaves to the right of", "approaches to the right of") or d == ("approaches to the right of", "leaves to the right of"):
        return "approaching or leaving the intersection at the right side"
    if d == ("leads up to", "leaves") or d == ("leaves", "leads up to"):
        return "approaching or leaving the intersection ahead from the road the ego is on"
    if d == ('leaves behind of', 'approaches behind of') or d == ('approaches behind of', 'leaves behind of'):
        return "approaching or leaving the intersection from behind"
    return f"with relation '{d}'"

idx_to_cardinal = {
    0: "first",
    1: "second",
    2: "third",
    3: "forth",
    4: "fifth",
    5: "sixth",
    6: "seventh",
    7: "eighth",
}   
    
idx_to_letter = {0: "A", 1: "B", 2: "C", 3: "D"}

def normalize_lane_direction(t: str) -> str:
    if t in ["same", "leads up to_main_road", "leaves behind of_main_road"] : return random.choice(["lane leading away from the camera", "lane in ego direction"])
    if t in ["opposite", "approaches behind of_main_road",  "leaves_main_road"]: return random.choice(["lane travelling towards the camera", "lane in direction opposite to the ego"])
    if t in ["approaches to the left of", "approaches to the right of"] : return "lane approaching"
    if t in ["leaves to the left of", "leaves to the right of"]: return "lane leaving"

  
OTHER_DIRECTION_LANE = {
    "leaves behind of": "approaches behind of", 
    "leaves to the right of": "approaches to the right of",
    "leads up to": "leaves", 
    "leaves to the left of":  "approaches to the left of",
    "approaches behind of":  "leaves behind of",
    "approaches to the left of": "leaves to the left of",
    "approaches to the right of": "leaves to the right of",
    "leaves": "leads up to",
}  

def verbose_direction(direction):
    if direction == "opposite": options = ["in opposite direction", "travelling towards the camera"]
    if direction == "same": options = ["in ego direction", "travelling away from the camera", "in forward direction"]
    return random.choice(options)


def join_with_and(items):
    """Join items as natural language: "a", "a and b", "a, b and c"."""
    items = [str(x) for x in items]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"

    return f"{', '.join(items[:-1])} and {items[-1]}"

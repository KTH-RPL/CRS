"""
Description hierarchy.
"""

DESCRIPTION_HIERARCHY = {
    "bicycle": {
        "properties": {
            "status": 0,
        },
        "edges": {
            ('is in', 'lane'): 0,
        },
    },
    "vehicular_trailer": {
        "properties": {
            "status": 0,
            "description":0,
        },
        "edges": {
            ('is in', 'lane'): 0,
        },
    },
    "bicyclist": {
        "properties": {
            "description": 0,
        },
        "edges": {
            ('is in', 'intersection'): 0,
            ('is in', 'lane'): 0,
        },
    },
    "articulated_bus": {
        "properties": {
            "description": 0,
        },
        "edges": {
            ('is in', 'intersection'): 0,
            ('is in', 'lane'): 0,
        },
    },
    "motorcyclist": {
        "properties": {
        },
        "edges": {
            ('is in', 'intersection'): 0,
            ('is in', 'lane'): 0,
        },
    },
    "box_truck": {
        "properties": {
            "hazard": 0,
            "description": 0,
            "status": 0,
        },
        "edges": {
            ('is in', 'intersection'): 0,
            ('is in', 'lane'): 0,
        },
    },
    "bus": {
        "properties": {
            "description": 0,
            "status": 0,
        },
        "edges": {
            ('is in', 'intersection'): 0,
            ('is in', 'lane'): 0,
        },
    },
    "construction_area": {
        "properties": {
            "description": 0,
            "hazard": 0,
        },
        "edges": {
            ('is in the back right corner of', 'intersection'): 0,
            ('is on', 'sidewalk'): 0,
        },
    },
    "construction_cone": {
        "properties": {
            "hazard": 0,
        },
        "edges": {
            ('is in', 'lane'): 0,
        },
    },
    "construction_barrel": {
        "properties": {
            "hazard": 0,
        },
        "edges": {
            ('is in', 'lane'): 0,
        },
    },
    "crossing": {
        "properties": {
            "description": 0,
            "marking_quality": 0,
            "marking_style": 0,
            "signalized": 0,
        },
        "edges": {
            ('is impacting', 'lane'): 0,
            ('is crossed by', 'pedestrian'):0, 
            ('is being approached by', 'pedestrian'): 0,
            ('is on', 'intersection'): 1,
            ('is in', 'intersection'): 1,
            ('is controlled by', 'traffic_light'): 0,
        },
    },
    "intersection": {
        "properties": {
            "control_type": 0,
            "description": 0,
            "number_of_arms": 0,
            "type": 0,
        },
        "edges": {
        },
    },
    "lane": {
        "properties": {
            "direction": 1,
            "traffic_pattern": 0,
            "turn_direction": 2,
            "description": 0,
            "type": 1,
            "variant": 0,
        },
        "edges": {
            ('approaches behind of', 'intersection'): 1,
            ('approaches to the left of', 'intersection'): 1,
            ('approaches to the right of', 'intersection'): 1,
            ('continues ahead into', 'lane'): 2,
            ('continues straight into', 'lane'): 2,
            ('is controlled by', 'sign'): 0,
            ('is left of', 'lane'): 2,
            ('is left of', 'regular_vehicle'): 0, 
            ('is left of', 'sign'): 0,
            ('is entered by', 'bus'): 0,
            ('is right of', 'lane'): 2,
            ('is the same lane as', 'lane'): 1,
            ('leads up to', 'split'): 0,
            ('is left of', 'road_marking'): 0,
            ('is right of', 'road_marking'): 0,
            ('contains', 'articulated_bus'): 0,
            ('contains', 'construction_barrel'): 0,
            ('contains', 'official_signaler'):0,
            ('is impacted by', 'crossing'): 0,
            ('is controlled by', 'stop_sign'): 0,
            ('is to the immediate side of', 'regular_vehicle'): 0,
            ('is marked to the left with', 'lane_line'): 2,
            ('is marked to the right with', 'lane_line'): 2,
            ('continues out of', 'split'): 0,
            ('leads to', 'split'): 0,
            ('leads up to', 'intersection'): 1,
            ('leaves behind of', 'intersection'): 1,
            ('leaves to the left of', 'intersection'): 1,
            ('leaves to the right of', 'intersection'): 1,
            ('leaves', 'intersection'): 1,
            ('contains', 'regular_vehicle'): 0,
            ('contains', 'school_bus'): 0,
            ('contains', 'motorcyclist'): 0,
            ('contains', 'motorcycle'): 0,
            ('contains', 'pedestrian'): 0,
            ('contains', 'large_vehicle'): 0,
            ('contains', 'truck_cab'): 0,
            ('contains', 'railroad_tracks'): 0,
            ('contains', 'stop_sign'):0, 
            ('contains', 'ego'): 1,
            ('contains', 'truck'): 0,
            ('contains', 'construction_cone'): 0,
            ('contains', 'box_truck'): 0,
            ('contains', 'bus'): 0,
            ('contains', 'bicyclist'): 0,
            ('contains', 'vehicular_trailer'): 0,
            ('turns left into', 'lane'): 2,
            ('turns right into', 'lane'): 2,
            ('is controlled by', 'traffic_light'): 1,
            ('is controlled by', 'road_marking'): 0,
            ('contains', 'road_marking'): 0,
            ('is agressively entered by', 'regular_vehicle'): 0,
        },
    },
    "lane_line": {
        "properties": {
            "mark_type": 1,
            "quality": 0,
        },
        "edges": {
            ('is left marking of', 'lane'): 1,
            ('is right marking of', 'lane'): 1,
        },
    },
    "large_vehicle": {
        "properties": {
            "description": 0,
            "status": 0,
        },
        "edges": {
            ('is in', 'intersection'): 0,
            ('is in', 'lane'): 0,
        },
    },
    "official_signaler": {
        "properties": {
            "description": 0,
            "status": 0,
        },
        "edges": {
            ('is in', 'intersection'): 0,
            ('is in', 'lane'): 0,
        },
    },
    "pedestrian": {
        "properties": {
            "description": 0,
            "hazard": 0,
            "status": 0,
            "illegal_behaviour": 0,
        },
        "edges": {
            ('is crossing at', 'crossing'): 0,
            ('is in', 'intersection'): 0,
            ('is in', 'lane'): 0,
        },
    },
    "railroad_tracks": {
        "properties": {
        },
        "edges": {
            ('are in', 'lane'): 0,
        },
    },
    "regular_vehicle": {
        "properties": {
            "description": 0,
            "hazard": 0,
            "illegal_behaviour": 0,
            "status": 0,
        },
        "edges": {
            ('cuts into', 'lane'): 0,
            ('is in', 'intersection'): 0,
            ('is in', 'lane'): 0,
            ('is parked outside of', 'lane'): 0,
            ('is right of', 'lane'): 0,
            ('parked outside of', 'lane'): 0,
        },
    },
    "road_marking": {
        "properties": {
            "hazard": 0,
            "meaning": 0,
            "type": 0,
        },
        "edges": {
            ('controls', 'lane'): 0,
            ('is in', 'lane'): 0,
            ('is left of', 'lane'): 0,
            ('is right of', 'lane'): 0,
        },
    },
    "school_bus": {
        "properties": {
        },
        "edges": {
            ('is in', 'lane'): 0,
        },
    },
    "motorcycle": {
        "properties": {
        },
        "edges": {
            ('is in', 'lane'): 0,
        },
    },
    "sidewalk": {
        "properties": {
            "description": 0,
        },
        "edges": {
        },
    },
    "sign": {
        "properties": {
            "category": 0,
            "description": 0,
            "location": 0,
            "meaning": 0,
            "type": 0,
        },
        "edges": {
            ('controls', 'lane'): 0,
            ('is in', 'intersection'): 0,
            ('is in', 'lane'): 0,
            ('is right of', 'lane'): 0,
        },
    },
    "split": {
        "properties": {
        },
        "edges": {
            ('splits into', 'lane'): 0,
        },
    },
    "stop_sign": {
        "properties": {
            "meaning": 0,
        },
        "edges": {
            ('controls', 'lane'): 0,
        },
    },
    "traffic_light": {
        "properties": {
            "status": 1,
            "type": 0,
            "mount": 0
        },
        "edges": {
            ('controls', 'crossing'): 0,
            ('controls', 'lane'): 0,
        },
    },
    "truck": {
        "properties": {
            "description": 0,
            "hazard": 0,
            "status": 0,
        },
        "edges": {
            ('is in', 'intersection'): 0,
            ('is in', 'lane'): 0,
        },
    },
    "truck_cab": {
        "properties": {
            "description": 0,
        },
        "edges": {
            ('is in', 'intersection'): 0,
            ('is in', 'lane'): 0,
        },
    },
}

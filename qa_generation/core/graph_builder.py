import networkx as nx
import json
import numpy as np
import os
import random 
from qa.helpers.definitions import idx_to_cardinal
from core.process_geometry import IMG_SIZE_BY_CAM



def collect_matches(G, source, target=None, edge_condition=None, property=""):
    """
    Find nodes of type `source` in G.
    - With `edge_condition`: edges source -> target whose relation text satisfies the condition,
      returned as (u, v, relation).
    - With `property` = (key, value): source nodes whose property `key` equals `value`,
      returned as (node, (key, value)).
    """
    matches = []
    if edge_condition != None:
        for u, v, eattrs in G.edges(data=True):
            u_type = (G.nodes[u].get("type") or "").lower()
            v_type = (G.nodes[v].get("type") or "").lower()
            if u_type == source and v_type == target:
                relation_text = eattrs.get("relation", "") or ""
                if not edge_condition(relation_text): continue
                matches.append((u,v,relation_text))
    if property != "":
        for n, attrs in G.nodes(data=True):
            n_type = (G.nodes[n].get("type") or "").lower()
            if n_type == source:
                val = attrs["properties"].get(property[0], "none")

                if val == property[1]:
                    matches.append((n, (property[0], val)))
    return matches


def lane_split_in_frame(G):
    """True if the scene graph contains a lane split node."""
    lane_split_nodes = [
            (n, attrs) for n, attrs in G.nodes(data=True)
            if (attrs.get("type") or "").lower() == "split"
        ]
    if lane_split_nodes: return True
    return False


class GraphBuilder:
    def __init__(self, relation_schema, openlane_root="data/Openlane_reprocessed_FINAL"):
        self.relation_schema = relation_schema
        self.openlane_root = openlane_root
        self._openlane_cache = {}

    def validate_relation_schema(self, data):
        """
        Ensure every temporalLabel (edge label) appearing in the JSON
        has a corresponding inverse in RELATION_SCHEMA.
        Returns a list of inconsistent labels.
        """ 

        found_labels = set()

        for edge in data["edges"]:
            labels = edge.get("temporalLabels", None)

            if isinstance(labels, str):
                found_labels.add(labels)
            elif isinstance(labels, dict):
                for v in labels.values():
                    found_labels.add(v)

        missing_inverse = []
        for label in found_labels:
            schema_entry = self.relation_schema.get(label)
            if schema_entry is None:
                missing_inverse.append(label)

        return missing_inverse

    def _load_openlane_file(self, logid):
        """
        Load OpenLane reprocessed file for this log id.
        Cache results so we do not reload per node.
        """
        if logid in self._openlane_cache:
            return self._openlane_cache[logid]

        path = os.path.join(self.openlane_root, f"{logid}.json")
        if not os.path.exists(path):
            print(f"[WARNING] OpenLane file not found: {path}")
            self._openlane_cache[logid] = None
            return None

        with open(path, "r") as f:
            data = json.load(f)

        self._openlane_cache[logid] = data
        return data
     
    def _point_to_segment_distance_2d(self, p, a, b):
        """
        p, a, b: np.array([x,y])
        Returns Euclidean distance from point p to segment a-b in 2D.
        """
        ab = b - a
        denom = float(np.dot(ab, ab))
        if denom <= 1e-12:
            return float(np.linalg.norm(p - a))

        t = float(np.dot(p - a, ab) / denom)
        t = max(0.0, min(1.0, t))
        proj = a + t * ab
        return float(np.linalg.norm(p - proj))

    def _distance_point_to_polygon_2d(self, p_xy, poly_xyz):
        """
        p_xy: [x,y] in CITY coords
        poly_xyz: [[x,y,z], ...] polygon/polyline in CITY coords

        Computes distance from point to the *boundary* (closest point on any edge).
        Falls back to vertex distance if < 2 points.
        """
        if not poly_xyz:
            return None

        pts = np.asarray(poly_xyz, dtype=float)
        if pts.ndim != 2 or pts.shape[0] == 0:
            return None

        p = np.asarray(p_xy, dtype=float).reshape(2,)

        if pts.shape[0] == 1:
            return float(np.linalg.norm(p - pts[0, :2]))

        pts2 = pts[:, :2]
        n = pts2.shape[0]

        min_d = float("inf")
        for i in range(n):
            a = pts2[i]
            b = pts2[(i + 1) % n]
            d = self._point_to_segment_distance_2d(p, a, b)
            if d < min_d:
                min_d = d

        return float(min_d)

    def _lookup_traffic_element_bbox(self, openlane_data, uuid, t):
        """
        Find traffic_element by uuid (=node.helpers.uuid)
        and return its polygon/bbox from points[str(t)].
        """
        if not openlane_data:
            return None

        elements = openlane_data.get("traffic_elements", [])
        for elem in elements:
            if elem.get("id") == uuid:
                
                pts = elem.get("points", {})
                frame_pts = pts.get(str(t))
                return frame_pts

        return None

    def _extract_uniqueness(self, data, t):
        """
        Extract unique nodes, unique properties, and unique edges
        based on helpers.uniqueKey[t].

        Returns:
            unique_nodes: {node_label: True}
            unique_props: {node_label: set(prop_names)}
            unique_edges: {edge_label: True}
        """

        edge_index = {e["label"]: e for e in data["edges"]}

        unique_nodes = {}
        unique_props = {}
        unique_edges = {}

        for node in data["nodes"]:
            uniq_list = node.get("helpers", {}).get("uniqueKey", {}).get(str(t), [])
            props = node.get("properties", {})
            
            for entry in uniq_list:
                
                if entry == "is unique":
                    unique_nodes[node["label"]] = True
                    continue

                if entry in props:
                    unique_props.setdefault(node["label"], set()).add(entry)
                    continue

                
                if entry in edge_index:
                    unique_edges[entry] = {"unique": True, "unique_node": node["label"]}
                    continue
        
        for node in data["nodes"]:
            props = node.get("properties", None)
            if not props: continue
            
            visibleAt = node.get("visibleAt", {}).get(str(t), None)
            if not visibleAt: continue
            if "description" in props.keys():
                unique_props.setdefault(node["label"], set()).add("description")
                
       
        return unique_nodes, unique_props, unique_edges

    def _resolve_properties(self, properties, t, temporal_only=False):
        """
        Given a dict of properties (possibly time-changing), return
        the correct property map at time t.
        """
        resolved = {}
        
        for key, val in properties.items():

            if not isinstance(val, dict):
                if not temporal_only:
                    resolved[key] = val
                    continue
                else:
                    continue

            candidates = [int(ts) for ts in val.keys() if int(ts) <= t]
            if not candidates:
                continue

            latest = max(candidates)
            resolved[key] = val[str(latest)]

        return resolved

    def _is_visible(self, node, t):
        vis = node.get("visibleAt", {})
        if not str(t) in vis.keys():
            return None
        return vis.get(str(t), False)

    def _resolve_edge_label(self, edge, t, temporal_only):
        labels = edge.get("temporalLabels")

        if isinstance(labels, str):
            if not temporal_only:
                return labels
            else:
                return None

        
        return labels[str(t)] if str(t) in labels.keys() else None

    def extract_complete_types(self, data, t):
        type_to_completeness = {}

        for node in data["nodes"]:
            vis = node.get("visibleAt", {})
            if vis and not vis.get(str(t), False):
                continue

            node_type = node.get("type")
            helpers = node.get("helpers", {})
   
            try: 
                is_complete = helpers.get("is_complete", {})[str(t)]
            except: is_complete = False    

            if node_type not in type_to_completeness:
                type_to_completeness[node_type] = []
            type_to_completeness[node_type].append(is_complete)

        complete_types = {
            tname
            for tname, completelist in type_to_completeness.items()
            if all(completelist)
        }
        return complete_types

    def _frame_index_for_t(self, openlane_data, t, camera="ring_front_center"):
        """
        Map frame id `t` to OpenLane frame index.
        Supports:
          - t already being an index (0..N-1)
          - t being an image timestamp that exists in sensor[camera]
        """
        imgs = openlane_data.get("sensor", {}).get(camera, [])
        if not imgs:
            return None

        if isinstance(t, int) and 0 <= t < len(imgs):
            return t

        ts = str(t)
        if ts in imgs:
            return imgs.index(ts)

        return None
    
    def _densify_polyline_city(self, pts_xyz, max_seg_len=1.0):
        """
        Densify a polyline/polygon in CITY coordinates.

        pts_xyz: [[x,y,z], ...]
        max_seg_len: max segment length in meters

        Returns: densified [[x,y,z], ...]
        """
        if not pts_xyz or len(pts_xyz) < 2:
            return pts_xyz

        out = []

        for i in range(len(pts_xyz)):
            p1 = np.array(pts_xyz[i], dtype=float)
            p2 = np.array(pts_xyz[(i + 1) % len(pts_xyz)], dtype=float)

            out.append(p1.tolist())

            seg = p2 - p1
            dist = np.linalg.norm(seg)

            if dist > max_seg_len:
                steps = int(np.ceil(dist / max_seg_len))
                for s in range(1, steps):
                    out.append((p1 + seg * (s / steps)).tolist())

        return out

    def _get_cam_calib(self, openlane_data, camera="ring_front_center"):
        calib = openlane_data.get("calibration", {}).get(camera)
        if not calib:
            return None

        fx, fy = calib["fx"], calib["fy"]
        cx, cy = calib["cx"], calib["cy"]
        K = np.array([[fx, 0,  cx],
                      [0,  fy, cy],
                      [0,  0,  1]], dtype=float)

        R = np.array(calib["R"], dtype=float)
        t = np.array(calib["t"], dtype=float).reshape(3,)

        return K, R, t

    def _get_pose_city_T_ego(self, openlane_data, frame_idx):
        """
        OpenLane file has pose.translations and pose.rotations aligned with sensor frames.
        rotations[i] is 3x3, translations[i] is 3.
        We assume this is city_T_ego.
        """
        pose = openlane_data.get("pose", {})
        Rs = np.array(pose.get("rotations", []), dtype=float)
        ts = np.array(pose.get("translations", []), dtype=float)

        if frame_idx is None or frame_idx >= len(ts) or frame_idx >= len(Rs):
            return None

        R_city_ego = Rs[frame_idx]
        t_city_ego = ts[frame_idx]
        return R_city_ego, t_city_ego
    
    def _bbox_to_polygon(self, geom, point_radius=5.0):
        """
        Normalize geometry into a polygon.

        Handles:
        - single point [x, y] or (x, y)
        - 2-point bbox [[x1,y1],[x2,y2]]
        - polygon [[x,y], [x,y], ...]

        Args:
        point_radius: half-size of square for single-point expansion (pixels)

        Returns:
        polygon as list of [x,y] points
        """
        if (
            isinstance(geom, (list, tuple))
            and len(geom) == 2
            and all(isinstance(v, (int, float)) for v in geom)
        ):
            x, y = geom
            r = float(point_radius)
            return [
                [x - r, y - r],
                [x + r, y - r],
                [x + r, y + r],
                [x - r, y + r],
            ]

        if (
            isinstance(geom, (list, tuple))
            and len(geom) == 2
            and all(isinstance(p, (list, tuple)) and len(p) == 2 for p in geom)
        ):
            (x1, y1), (x2, y2) = geom
            xmin, xmax = min(x1, x2), max(x1, x2)
            ymin, ymax = min(y1, y2), max(y1, y2)
            return [
                [xmin, ymin],
                [xmax, ymin],
                [xmax, ymax],
                [xmin, ymax],
            ]

        if (
            isinstance(geom, (list, tuple))
            and len(geom) >= 3
            and all(isinstance(p, (list, tuple)) and len(p) == 2 for p in geom)
        ):
            return list(geom)
        if (
            isinstance(geom, (list, tuple))
            and len(geom) == 4
            and all(isinstance(p, (float)) for p in geom)
        ):
            return [[geom[0], geom[1]],[geom[2], geom[3]],]

        return None
    
    def _clip_polyline_to_ego_window(self, pts_ego_xyz, x_min=0.0, x_max=20.0, y_min=-10.0, y_max=10.0):
        """
        Keep only the portion of a polyline/polygon that lies inside a rectangular
        ego-frame window.

        pts_ego_xyz: np.array of shape (N,3) in ego coordinates
        window defaults to a 20m x 20m region in front of ego:
        x in [0, 20], y in [-10, 10]

        Returns:
            np.array of shape (M,3)
        """
        if pts_ego_xyz is None or len(pts_ego_xyz) == 0:
            return np.empty((0, 3), dtype=float)

        pts = np.asarray(pts_ego_xyz, dtype=float)
        if pts.ndim != 2 or pts.shape[1] != 3:
            return np.empty((0, 3), dtype=float)

        def inside(p):
            return x_min <= p[0] <= x_max and y_min <= p[1] <= y_max

        clipped = []

        for i in range(len(pts) - 1):
            p1 = pts[i]
            p2 = pts[i + 1]

            p1_in = inside(p1)
            p2_in = inside(p2)

            if p1_in:
                clipped.append(p1.tolist())

            intersections = []

            rect_edges = [
                ("x", x_min),
                ("x", x_max),
                ("y", y_min),
                ("y", y_max),
            ]

            d = p2 - p1
            for axis, val in rect_edges:
                if axis == "x":
                    if abs(d[0]) < 1e-9:
                        continue
                    t = (val - p1[0]) / d[0]
                    if 0.0 <= t <= 1.0:
                        p = p1 + t * d
                        if y_min <= p[1] <= y_max:
                            intersections.append((t, p))
                else:
                    if abs(d[1]) < 1e-9:
                        continue
                    t = (val - p1[1]) / d[1]
                    if 0.0 <= t <= 1.0:
                        p = p1 + t * d
                        if x_min <= p[0] <= x_max:
                            intersections.append((t, p))

            intersections.sort(key=lambda z: z[0])

            for _, p in intersections:
                clipped.append(p.tolist())

            if i == len(pts) - 2 and p2_in:
                clipped.append(p2.tolist())

        if not clipped:
            return np.empty((0, 3), dtype=float)

        deduped = [clipped[0]]
        for p in clipped[1:]:
            if np.linalg.norm(np.asarray(p) - np.asarray(deduped[-1])) > 1e-6:
                deduped.append(p)

        return np.asarray(deduped, dtype=float)
   
    def _project_map_geometry_all_cameras(self, openlane_data, pts_city, t, idx):
        """
        Project CITY-space geometry into all front cameras.
        Returns dict:
        camera -> { "bbox": [...], "polygon": [...] }
        """
        out = {}

        pts_city_dense = self._densify_polyline_city(
            pts_city,
            max_seg_len=2.5
        )

        for cam in ["ring_front_center", "ring_front_left", "ring_front_right"]:
            bbox2d, poly2d = self._project_city_points_to_image(
                openlane_data,
                pts_city_dense,
                t,
                camera=cam,
                image_wh=IMG_SIZE_BY_CAM[cam],
                assume_sensor_T_ego=True,
            )

            if bbox2d or poly2d:
                out[cam] = {
                    "polygon": [[float(x), float(y)] for x, y in poly2d] if poly2d else None
                }
            out["name"] = f"position_{idx}"    

        return out or None

    def _project_city_points_to_image(
        self,
        openlane_data,
        points_city_xyz,
        t,
        camera="ring_front_center",
        image_wh=(1920, 1200),
        assume_sensor_T_ego=True,
    ):
        """
        Returns (bbox, poly_pixels) where
          bbox = [[xmin,ymin],[xmax,ymax]] in image coords
          poly_pixels = [(u,v), ...] filtered to finite points
        If projection fails → (None, []).
        """
        frame_idx = self._frame_index_for_t(openlane_data, t, camera=camera)
        if frame_idx is None:
            return None, []

        calib = self._get_cam_calib(openlane_data, camera=camera)
        pose = self._get_pose_city_T_ego(openlane_data, frame_idx)
        if calib is None or pose is None:
            return None, []

        K, R_s, t_s = calib
        R_city_ego, t_city_ego = pose

        pts = np.asarray(points_city_xyz, dtype=float)
        if pts.ndim != 2 or pts.shape[1] != 3:
            return None, []

        p_ego = (R_city_ego.T @ (pts - t_city_ego).T).T

        p_ego = self._clip_polyline_to_ego_window(
            p_ego,
            x_min=0.0,
            x_max=50.0,
            y_min=-25.0,
            y_max=25.0,
        )

        if p_ego.shape[0] == 0:
            return None, []

        if assume_sensor_T_ego:
            p_cam = (R_s @ p_ego.T).T + t_s
        else:
            p_cam = (R_s.T @ (p_ego - t_s).T).T

        z = p_cam[:, 2]
        valid = z > 2
        p_cam = p_cam[valid]
        if p_cam.shape[0] == 0:
            return None, []
        W, H = image_wh
        uvw = (K @ p_cam.T).T
        u = uvw[:, 0] / uvw[:, 2]
        v = uvw[:, 1] / uvw[:, 2]
        on_screen = (u >= 0) & (u < W) & (v >= 0) & (v < H)

        if not np.any(on_screen):
            return None, []

        poly = list(zip(u.tolist(), v.tolist()))

        xmin, xmax = float(np.min(u)), float(np.max(u))
        ymin, ymax = float(np.min(v)), float(np.max(v))

        W, H = image_wh
        xmin = max(0.0, min(xmin, W - 1.0))
        xmax = max(0.0, min(xmax, W - 1.0))
        ymin = max(0.0, min(ymin, H - 1.0))
        ymax = max(0.0, min(ymax, H - 1.0))

        bbox = [[xmin, ymin], [xmax, ymax]]
        return bbox, poly

    def _lookup_bbox_object(self, openlane_data, uuid, t):
        if not openlane_data or not uuid:
            
            return None
        for obj in openlane_data.get("objects", []):
            if obj.get("uuid") == uuid:
                pos_c = obj.get("positions").get("ring_front_center", {}).get(str(t))
                pos_l = obj.get("positions").get("ring_front_left", {}).get(str(t))
                pos_r = obj.get("positions").get("ring_front_right", {}).get(str(t))
                return pos_c, pos_l, pos_r
                       
    def _lookup_map_geometry_city(self, openlane_data, uuid):
        """
        Find a geometry by id/uuid across OpenLane map structures.
        Return a list of [x,y,z] points in CITY coords (for projection).
        """
        if not openlane_data or not uuid:
            return None
      
        for lane in openlane_data.get("lane_segments", []):
            if str(lane.get("id")) == str(uuid):
                if lane.get("left_lane_boundary") and lane.get("right_lane_boundary"):
                    pts = lane["left_lane_boundary"] + lane["right_lane_boundary"][::-1]
                    return [[p["x"], p["y"], p["z"]] for p in pts]
                if lane.get("centerline"):
                    pts = lane["centerline"]
                    return [[p["x"], p["y"], p["z"]] for p in pts]
                if lane.get("polygon"):
                    pts = lane["polygon"]
                    return [[p["x"], p["y"], p["z"]] for p in pts]
            
        for inter in openlane_data.get("intersections", []):
            if str(inter.get("id")) == str(uuid):
                pts = inter.get("boundary", [])
                return [[p["x"], p["y"], p["z"]] for p in pts]
            
        for line_label, line in openlane_data.get("lane_lines").items():
            if str(line_label) == str(uuid):
                pts = line.get("geometry", [])
                return [p for p in pts]
      
        for cw in openlane_data.get("pedestrian_crossings", []):
            
            
            if str(cw.get("id")) == str(uuid):
                
            
                pts = (cw.get("edge1", []) or []) + (cw.get("edge2", [])[::-1] or [])
                return [[p["x"], p["y"], p["z"]] for p in pts]

        for key in ["merges", "splits"]:
            for obj in openlane_data.get(key, []) if isinstance(openlane_data.get(key, []), list) else []:
                if str(obj.get("id")) == str(uuid):
                    for geom_key in ["polygon", "boundary", "centerline", "points"]:
                        if geom_key in obj and obj[geom_key]:
                            pts = obj[geom_key]
                            if isinstance(pts[0], dict):
                                return [[p["x"], p["y"], p["z"]] for p in pts]
                            if isinstance(pts[0], (list, tuple)) and len(pts[0]) >= 3:
                                return [p[:3] for p in pts]

        return None
    
    def _extract_click_position(self, node, t):
        helpers = node.get("helpers", {})
        cp = helpers.get("ClickPosition", None)

        if not cp:
            return []

        frame_entry = cp.get(str(t))
        if not frame_entry:
            return []
        
        cameras = {"center": "ring_front_center",
                   "left": "ring_front_left", 
                   "right": "ring_front_right"
                   }
        
        return {cameras[camera]: {"polygon": self._bbox_to_polygon(coords)} for camera, coords in frame_entry.items()}

    def _point_in_polygon_2d(self, p_xy, poly_xyz):
        """
        Ray-casting point-in-polygon test in 2D.

        p_xy: [x,y]
        poly_xyz: [[x,y,z], ...]

        Returns True if inside (or on boundary).
        """
        if not poly_xyz or len(poly_xyz) < 3:
            return False

        x, y = p_xy
        inside = False

        pts = poly_xyz
        n = len(pts)

        for i in range(n):
            x1, y1 = pts[i][0], pts[i][1]
            x2, y2 = pts[(i + 1) % n][0], pts[(i + 1) % n][1]

            dx, dy = x2 - x1, y2 - y1
            dxp, dyp = x - x1, y - y1
            cross = dx * dyp - dy * dxp
            if abs(cross) < 1e-6:
                dot = dxp * (x - x2) + dyp * (y - y2)
                if dot <= 1e-6:
                    return True

            intersects = ((y1 > y) != (y2 > y)) and \
                        (x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1)
            if intersects:
                inside = not inside

        return inside


    def collect_reachable_lanes(self, G, start_lane, relation):
        """
        Follow lane-to-lane edges of one relation recursively.
        relation: 'is left of' or 'is right of'
        Returns a set of reachable lane node ids.
        """
        visited = set()
        stack = [start_lane]

        while stack:
            lane = stack.pop()
            for _, nbr, d in G.out_edges(lane, data=True):
                if d.get("relation") == relation and nbr not in visited:
                    visited.add(nbr)
                    stack.append(nbr)

        visited.discard(start_lane)
        
        return visited
    
    def assign_lane_position_descriptions(self, G, lane_ids):
        """
        lane_ids: list of lane node ids belonging to the same road segment/group
        """
        n_lanes = len(lane_ids)
        if n_lanes < 2:
            return G

        for lane_id in lane_ids:
            props = G.nodes[lane_id].setdefault("properties", {})
            unique_props = props.setdefault("unique_properties", [])

            left_set = self.collect_reachable_lanes(G, lane_id, "is left of")
            right_set = self.collect_reachable_lanes(G, lane_id, "is right of")
            if len(lane_ids)!= len(left_set)+len(right_set)+1: return G
            num_left = len(left_set)
            num_right = len(right_set)

            description = None

            if num_right == 0:
                description = random.choice(["leftmost lane", "left curb lane"])
            elif num_right == 1:
                description = "2nd lane from the left"
            elif num_right >= 2:
                description = f"{idx_to_cardinal[num_right]} lane from the left"

            if num_left == 0:
                left_description = random.choice(["rightmost lane", "right curb lane"])
            elif num_left == 1:
                left_description = "2nd lane from the right"
            elif num_left >= 2:
                left_description = f"{idx_to_cardinal[num_left]} lane from the right"
            else:
                left_description = None

            if description in ["rightmost lane", "right curb lane", "leftmost lane", "left curb lane"]:
                final_desc = description
            else:
                if num_left <= num_right:
                    final_desc = left_description
                else:
                    final_desc = description

            if final_desc:
                if props.get("description", None) != None:
                    final_desc = random.choice([props.get("description", None), final_desc])
                if "description" not in unique_props:
                    unique_props.append("description")
                props["description"] = final_desc
        return G        
    
    def build_frame(self, data, t, temporal_only=False):
        """
        Build the directed scene graph for timestamp t.
        """

        
        unique_nodes, unique_props, unique_edges = self._extract_uniqueness(data, t)
        
        G = nx.DiGraph()

        ego_node = {"label": "Ego", "type": "ego", "properties": {"is_occluded": False, "is_unique": True}}
        G.add_node(
            "Ego",
            label="Ego",
            type="ego",
            properties=ego_node["properties"]
        )
        

        for idx, node in enumerate(data["nodes"]):
            is_visible = self._is_visible(node, t)
            if is_visible is None:
                continue

            props = self._resolve_properties(node.get("properties", {}), t, temporal_only=temporal_only)
        
            props["is_occluded"] = not is_visible


            props["unique_properties"] = list(unique_props.get(node["label"], []))
            props["is_unique"] = unique_nodes.get(node["label"], False)
            

            click_pos = self._extract_click_position(node, t)

            node_type = node.get("type")
            uuid = node.get("helpers", {}).get("uuid")
            logid = data.get("logid")
            openlane_data = self._load_openlane_file(logid)
            if click_pos:
                props["click_position"] = click_pos
                for cam in ["ring_front_center", "ring_front_right", "ring_front_left"]:
                    if cam in props["click_position"].keys():
                        props["click_position"][cam]["polygon"] = self._bbox_to_polygon(props["click_position"][cam]["polygon"])
                props["click_position"]["name"] = f"position_{idx}"
              

            elif node_type in {"traffic_light", "sign", "road_marking"} and uuid and logid:

                openlane_data = self._load_openlane_file(logid)

                bbox = self._lookup_traffic_element_bbox(openlane_data, uuid, t)
                
                if bbox:
                    props["click_position"] = {
                        "ring_front_center": {
                            "polygon": self._bbox_to_polygon(bbox)
                        },
                        "name": f"position_{idx}"
                    }
                

            elif node_type in {"lane", "intersection", "crossing", "merge", "split", "lane_line"} and uuid and logid:
                openlane_data = self._load_openlane_file(logid)
                if node_type == "lane": props["uuid"] = node["helpers"]["uuid"]
                pts_city = self._lookup_map_geometry_city(openlane_data, uuid)
                
                if pts_city:
                    if pts_city:
                        cam_geoms = self._project_map_geometry_all_cameras(
                            openlane_data, pts_city, t, idx
                        )
                        if cam_geoms:
                            props["click_position"] = cam_geoms 
                      
                if node_type in ["intersection", "crossing"] and uuid and logid:
                    openlane_data = self._load_openlane_file(logid)

                    inter_poly_city = self._lookup_map_geometry_city(openlane_data, uuid)

                    frame_idx = self._frame_index_for_t(openlane_data, t, camera="ring_front_center")
                    pose = self._get_pose_city_T_ego(openlane_data, frame_idx)

                    if inter_poly_city and pose is not None:
                        _, t_city_ego = pose
                        ego_xy = [float(t_city_ego[0]), float(t_city_ego[1])]

                        if self._point_in_polygon_2d(ego_xy, inter_poly_city):
                            props["distance_to_ego"] = 0.0
                        else:
                            dist = self._distance_point_to_polygon_2d(ego_xy, inter_poly_city)
                            if dist is not None:
                                props["distance_to_ego"] = float(dist) 
                        
            elif "line" not in uuid:
                
                try:
                    pts_c, pts_l, pts_r = self._lookup_bbox_object(openlane_data, uuid, t)
                    props["click_position"] = {}
                    if pts_c: 
                        props["click_position"]["ring_front_center"] = {"polygon":  self._bbox_to_polygon([[pts_c[0],pts_c[1]],[pts_c[2], pts_c[3]]])}
                    if pts_l: 
                        props["click_position"]["ring_front_left"] = {"polygon": self._bbox_to_polygon([[pts_l[0],pts_l[1]],[pts_l[2], pts_l[3]]])}
                    if pts_r: 
                        props["click_position"]["ring_front_right"] = {"polygon": self._bbox_to_polygon([[pts_r[0],pts_r[1]],[pts_r[2], pts_r[3]]])}
                    props["click_position"]["name"] = f"position_{idx}"    
                except: pass
                

            G.add_node(
                node["label"],
                label=node["label"],
                type=node.get("type"),
                used=False,
                properties=props
            )
        
        

       


            
        


        visible = set(G.nodes)
        unique_edge_labels = [k for k,v in unique_edges.items()]
        matches_leads_up_to = collect_matches(G, "lane", "intersection", lambda x: x == "leads up to")
        matches_leaves = collect_matches(G, "lane", "intersection", lambda x: x == "leaves")
        for edge in data["edges"]:
            
            src, tgt = edge["source"], edge["target"]
            if src not in visible or tgt not in visible:
                continue
            

            label = self._resolve_edge_label(edge, t, temporal_only)
            if label is None:
                continue

            json_category = edge.get("category", "unknown")

            
            is_unique_edge = edge["label"] in unique_edge_labels

            if label  in ["continues ahead into", "continues straight into", "turns left into", "turns right into"]: 
                is_unique_edge = False
            
 
            if "TrafficLight" in src: is_unique_edge = True
            
            if src == "Ego" and label == "is in":
                is_unique_edge = True
            if "LaneLine" in src and label == "is left marking of" and "Lane" in tgt:
                is_unique_edge = True
            if "LaneLine" in src and label == "is right marking of" and "Lane" in tgt:
                is_unique_edge = True
            if "Lane-" in src and label == "is right of" and "Lane-" in tgt:
                is_unique_edge = True
            if "Lane-" in src and label == "is left of" and "Lane-" in tgt:
                is_unique_edge = True
            if "Marking-" in src and label == "controls" and "Lane" in tgt:
                is_unique_edge = True
            if "Marking-" in src and label == "is in" and "Lane" in tgt:
                is_unique_edge = True
                
            
            if "LaneLine" in src and label == "is left marking of" and "Lane" in tgt:
                intersection_nodes = [
                    (n, attrs) for n, attrs in G.nodes(data=True)
                    if (attrs.get("type") or "").lower() == "intersection"
                ]
                allow=False
                if not intersection_nodes: allow=True
                if len(intersection_nodes)==1:
                    if intersection_nodes[0][1]["properties"]["distance_to_ego"]>7:
                        allowed_lanes = [m[0] for m in matches_leaves] + [m[0] for m in matches_leads_up_to]
                        if tgt in allowed_lanes: allow=True
                        
                if allow==True:
                    mark_type = G.nodes[src]["properties"]["mark_type"]
                    direction = G.nodes[tgt]["properties"]["direction"]
                    if mark_type == "DOUBLE_SOLID_YELLOW" and direction == "same":
                        G.nodes[tgt]["properties"]["unique_properties"].append("description")
                        G.nodes[tgt]["properties"]['description'] = "lane right of the double solid median"
                        
                    if mark_type == "DOUBLE_SOLID_YELLOW" and direction == "opposite":
                        G.nodes[tgt]["properties"]["unique_properties"].append("description")
                        G.nodes[tgt]["properties"]['description'] = "lane left of the double solid median"
            
            if src != "Ego" and edge["label"] in unique_edges.keys():
                if unique_edges[edge["label"]]["unique_node"]==tgt and not is_unique_edge == False:
                    inv_label = self.relation_schema.get(label, {})["inverse"]
                    if inv_label == None: assert False, f"Missing inverse label for '{label}'"
                    else: 
                        label = inv_label
                        src, tgt = tgt, src
            
            G.add_edge(
                src,
                tgt,
                relation=label,
                category=json_category,
                is_unique=is_unique_edge
            )

            schema = self.relation_schema.get(label, {})
            bidirectional = schema.get("bidirectional")
            inverse = schema.get("inverse")
            if inverse == None: continue
            if not bidirectional: is_unique_edge=False
            if "Marking-" in src  and "Lane" in tgt: is_unique_edge=True
            G.add_edge(
                tgt,
                src,
                relation=inverse,
                category=json_category,
                is_unique=is_unique_edge
            )

        complete_types = self.extract_complete_types(data, t)
        intersection_nodes = [
                (n, attrs) for n, attrs in G.nodes(data=True)
                if (attrs.get("type") or "").lower() == "intersection"
            ]
        if len(intersection_nodes)==1: 
            complete_types = set(list(complete_types)+["intersection"])
        if "lane" in complete_types:
            lane_nodes = [
                n for n, attrs in G.nodes(data=True)
                if (attrs.get("type") or "").lower() == "lane"
            ]
            intersection_nodes = [
                (n, attrs) for n, attrs in G.nodes(data=True)
                if (attrs.get("type") or "").lower() == "intersection"
            ]
   
            assign_descriptions=False
            if len(intersection_nodes)==1:
                if intersection_nodes[0][1]["properties"]["distance_to_ego"]>5:
                    assign_descriptions=True
                    relation = ("leads up to", "leaves")
                    lane_nodes = collect_matches(G, "lane", "intersection", lambda x: x == relation[0] or x == relation[1])
                    lane_nodes = [m[0] for m in lane_nodes]   
            
            else: 
                assign_descriptions = True   
            if not lane_split_in_frame(G) and assign_descriptions==True:
                G = self.assign_lane_position_descriptions(G, lane_nodes)
                
   
        return G, complete_types
from shapely.geometry import box, MultiPoint, LineString
import math


IMG_SIZE_BY_CAM = {
    "ring_front_center": (1550, 2048),
    "ring_front_left":   (2048, 1550),
    "ring_front_right":  (2048, 1550),
}
VISIBLE_FRACTION=0.08

use_centroid_types = ["lane", "merge", "split", "lane_line", "crossing"]

def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def to_qwen_1000(x_px, y_px, w, h):
    x = int(round((x_px / w) * 1000.0))
    y = int(round((y_px / h) * 1000.0))
    return clamp(x, 0, 1000), clamp(y, 0, 1000)


def bbox_to_qwen_1000(x1, y1, x2=None, y2=None, w=None, h=None):
    X1, Y1 = to_qwen_1000(x1, y1, w, h)
    if x2 != None and y2 != None: 
        X2, Y2 = to_qwen_1000(x2, y2, w, h)
        return min(X1, X2), min(Y1, Y2), max(X1, X2), max(Y1, Y2)
    else: return X1, Y1


def point_as_point_qwen(cx, cy, w, h):
    return bbox_to_qwen_1000(cx, cy, w=w, h=h)


def euclidean(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def order_points_greedy(points):
    """
    Order unordered points along a path by:
    1) finding the two farthest points as approximate endpoints
    2) greedily walking to the nearest unvisited point
    """
    if len(points) <= 2:
        return points[:]

    pts = [tuple(p) for p in points]

    max_d = -1
    start = pts[0]
    end = pts[0]
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            d = euclidean(pts[i], pts[j])
            if d > max_d:
                max_d = d
                start, end = pts[i], pts[j]

    ordered = [start]
    remaining = set(pts)
    remaining.remove(start)

    current = start
    while remaining:
        nxt = min(remaining, key=lambda p: euclidean(current, p))
        ordered.append(nxt)
        remaining.remove(nxt)
        current = nxt

    if euclidean(ordered[-1], end) > euclidean(ordered[0], end):
        ordered.reverse()

    return ordered
    
def poly_to_grounding_box(poly_coords, w, h, type):
    """
    A robust version using Shapely for clipping and area calculations.
    """
    if not poly_coords or len(poly_coords) < 3:
        return None, 0

    view_rect = box(0, 0, w, h)
    if type == "lane_line":
        ordered_coords = order_points_greedy(poly_coords)
        line = LineString(ordered_coords)
       

        if line.is_empty or line.length == 0:
            return None, 0.0

        visible_line = line.intersection(view_rect)

        if visible_line.is_empty:
            return None, 0.0

        total_length = line.length
        visible_length = visible_line.length if hasattr(visible_line, "length") else 0.0
        visible_fraction = min(visible_length / total_length, 1.0) if total_length > 0 else 0.0

        if visible_fraction < VISIBLE_FRACTION:
            return None, visible_fraction

        if visible_line.geom_type == "MultiLineString":
            
            return None, visible_fraction
        coords = list(visible_line.coords)
        if len(coords) < 2:
            return None, visible_fraction

        start_from_bottom = coords[0][1] >= coords[-1][1]
        if not start_from_bottom:
            coords = coords[::-1]

        ordered_line = LineString(coords)

        dist = ordered_line.length / 2.0
        target = ordered_line.interpolate(dist)
       
        return point_as_point_qwen(target.x, target.y, w, h), visible_fraction

    view_rect = box(0, 0, w, h)

    envelope_poly = MultiPoint(poly_coords).convex_hull
    
    if envelope_poly.area <= 0:
        return None, 0

    
    visible_part = envelope_poly.intersection(view_rect)

    if visible_part.is_empty:
        return None, 0

    visible_fraction = min(visible_part.area / envelope_poly.area, 1.0)

    if visible_fraction<VISIBLE_FRACTION: return None, visible_fraction
    if visible_part.is_empty:
        return None, visible_fraction

    if type in use_centroid_types:
        target = visible_part.centroid
        return point_as_point_qwen(target.x, target.y, w, h), visible_fraction

    minx, miny, maxx, maxy = visible_part.bounds
    return bbox_to_qwen_1000(minx, miny, maxx, maxy, w, h), visible_fraction

    



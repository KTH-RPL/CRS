"""Frame/time helpers: the frames a log covers, and how node properties change over a window of frames."""
import json


def extract_all_timestamps(data):
    """Sorted list of all frame indices that occur in an annotated log."""
    timestamps = set()

    for node in data["nodes"]:
        for t in node.get("visibleAt", []):
            timestamps.add(int(t))

        for val in node.get("properties", {}).values():
            if isinstance(val, dict):
                for t in val.keys():
                    timestamps.add(int(t))

    for edge in data["edges"]:
        temps = edge.get("temporalLabels", {})
        if isinstance(temps, str):
            timestamps.add(0)
        else:
            for t in temps.keys():
                timestamps.add(int(t))

    return sorted(timestamps)


def build_property_timelines(G_old):
    """
    Timelines of node properties over a window of frames.

    G_old: list of scene graphs, one per frame (oldest first).
    Returns timelines[node_id][prop] = [(frame position in G_old, value), ...]; only the
    "status" property is tracked, and the ego node is skipped.
    """
    timelines = {}
    for t, G in enumerate(G_old):
        for node_id, attrs in G.nodes(data=True):
            node_tl = timelines.setdefault(node_id, {})
            if node_id == "Ego":
                continue

            props = attrs.get("properties", {})

            for key, val in props.items():
                if key != "status":
                    continue

                seq = node_tl.setdefault(key, [])
                seq.append((t, val))

    return timelines


def normalize_value(v):
    """
    Convert any property value into a hashable representation.
    - scalars remain identical
    - lists/dicts get JSON-serialized
    """
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    try:
        return json.dumps(v, sort_keys=True)
    except Exception:
        return str(v)


def property_changed(seq):
    """
    seq = [(timestamp, value), ...]
    Return True if any normalized value differs across the timeline.
    """
    values = [normalize_value(v) for (_, v) in seq]
    return len(set(values)) > 1

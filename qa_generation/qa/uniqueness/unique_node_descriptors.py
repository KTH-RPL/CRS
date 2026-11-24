

class DescriptorResult:
    def __init__(self, text, node_label, is_unique, n_hops, dependants=None, property=None, relation=(None,None)):
        self.text = text
        self.node_label = node_label
        self.is_unique = is_unique
        self.n_hops = n_hops
        self.dependants = dependants or []
        self.relation = relation
        self.property = property

            


def _extract_unique_edge_anchors(G):
    anchors = {}
    for u, v, attrs in G.edges(data=True):
        
        if attrs.get("is_unique", False):
            rel = attrs.get("relation", "")
            anchors.setdefault(u, []).append((v, rel, "outgoing"))
    
    return anchors


def build_node_descriptor(graph_specs, node_label, edge_anchors, max_hops=2, visited=None):
    """
    Returns list[DescriptorResult] giving ALL unique ways of describing node_label.
    Priority:
      1. unique node
      2. unique properties
      3. unique edges (recursive)
      4. click-position fallback
      5. fallback (non-unique)
    """


    if visited is None:
        visited = set()
    if node_label in visited:
        return []

    visited = visited | {node_label}
    all_label_options = []
    node = graph_specs.G.nodes[node_label]
    props = node["properties"]
    noun = node["type"].replace("_", " ")
  
    is_unique = props.get("is_unique", False)
    unique_props = props.get("unique_properties", [])
    click_pos = props.get("click_position", None)
    edge_refs = edge_anchors.get(node_label, [])

    if is_unique:
        all_label_options.append(
            DescriptorResult(
                text=f"the {noun}",
                node_label=node_label,
                is_unique=True,
                n_hops=0,
                dependants=[]
            )
        )

    prop_results = []
    for u_key in unique_props:
        u_value = props.get(u_key)
        if not u_value:
            continue

        if u_key == "description":
            prop_results.append(
                DescriptorResult(
                    text=f"the {u_value}",
                    node_label=node_label,
                    is_unique=True,
                    property=u_key,
                    n_hops=0,
                    dependants=[]
                )
            )
        else:
            prop_results.append(
                DescriptorResult(
                    text=f"the {noun} whose {u_key} is '{u_value}'",
                    node_label=node_label,
                    property=u_key,
                    is_unique=True,
                    n_hops=0,
                    dependants=[]
                )
            )

    if prop_results:
        all_label_options += prop_results

    edge_results = []
    if edge_refs and max_hops > 0:

        if props.get("is_occluded", False):
            edge_refs = []

        for (other, rel, direction) in edge_refs:
            other_props = graph_specs.G.nodes[other]["properties"]
            other_type = graph_specs.G.nodes[other]["type"]
            if other_props.get("is_occluded", False):
                continue
       
            other_descs = build_node_descriptor(
                graph_specs,
                other,
                edge_anchors,
                max_hops=max_hops - 1,
                visited=visited,
            )

            for od in other_descs:
                wrapped = od.text
                if direction == "incoming":
                    text = f"the {noun} that {wrapped} {rel}"
                else:
                    if noun == "lane" and wrapped == "the ego":
                        text = "the ego lane"
                    elif (
                        noun == "traffic light"
                        and rel == "controls"
                        and "the lane that contains" in wrapped
                        and od.n_hops == 1
                    ):
                        wrapped = wrapped.replace("the lane that contains ", "")
                        text = f"the traffic light that controls {wrapped}"
                    else:
                        text = f"the {noun} that {rel} {wrapped}"

                    if text == "the lane that is right of the lane left of the double solid median":
                        text = "the lane right of the double solid median"
                    if text == "the lane that is left of the lane right of the double solid median":
                        text = "the lane left of the double solid median"

                dependants = list(od.dependants)
                if dependants:
                    dependants_nodes = [n['node'] for n in dependants]
                else: dependants_nodes = []
                if other not in dependants_nodes:
                    dependants.append({
                        "node": other, 
                        "text": wrapped, 
                        "relation": (rel, od.node_label), 
                        "target": node_label, 
                        "n_hops": od.n_hops, 
                        "type": other_type,
                        "other_descs": [od for od in other_descs if od.text != wrapped]})
                if text in ["the lane right of the double solid median", "the lane left of the double solid median"]:
                    edge_results.append(
                        DescriptorResult(
                            text=text,
                            relation=("is marked to the left with", "Median"),
                            node_label=node_label,
                            is_unique=od.is_unique,
                            n_hops=od.n_hops,
                            dependants=[],
                            property="description"
                        )
                    )
                else: edge_results.append(
                    DescriptorResult(
                        text=text,
                        relation=(rel, od.node_label),
                        node_label=node_label,
                        is_unique=od.is_unique,
                        n_hops=od.n_hops + 1,
                        dependants=dependants,
                    )
                )

    if edge_results:
        all_label_options += edge_results

    if click_pos:
        all_label_options.append(
            DescriptorResult(
                text=f"the {noun} marked with point_<{click_pos['name']}>",
                node_label=node_label,
                is_unique=True,
                n_hops=0,
                dependants=[]
            )
        )

    if len(all_label_options) == 0:
        return [
            DescriptorResult(
                text=node_label,
                node_label=node_label,
                is_unique=False,
                n_hops=0,
                dependants=[]
            )
        ]

    return all_label_options
   

   
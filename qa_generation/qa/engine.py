from types import SimpleNamespace

from qa.templates.comparison.lane_direction_comparison import generate_pairwise_direction_comparison_questions
from qa.templates.comparison.vehicle_location_comparison import generate_pairwise_vehicle_comparison_questions
from qa.templates.counting.crossing_counting_at_intersection import generate_counting_questions_crossing
from qa.templates.counting.crossing_existence_at_intersection import generate_existence_questions_crossing
from qa.templates.counting.lane_counting_at_intersection_direction import generate_counting_questions_direction
from qa.templates.counting.lane_counting_no_intersection import generate_counting_questions_off_intx
from qa.templates.counting.lane_counting_no_intersection_direction import generate_counting_questions_direction_off_intx
from qa.templates.pointing.pointing_questions import generate_pointing_questions
from qa.templates.properties.lane_direction import generate_lane_direction_questions
from qa.templates.properties.lane_type import generate_lane_type_questions
from qa.templates.properties.line_color import generate_line_marking_style_questions
from qa.templates.properties.pedestrian_crossing_type import generate_pc_type_questions
from qa.templates.properties.traffic_light import generate_traffic_light_status_questions
from qa.templates.relations.sign_control import generate_controlled_lane_mcq_sign
from qa.templates.relations.tlight_control import generate_controlled_lane_mcq
from qa.templates.relations.vehicle_is_in import generate_vehicle_position_questions
from qa.templates.temporal.traffic_light_status import generate_temporal_property_change_questions


def tag(type_name, qa_list):
    return [{"type": type_name, **qa} for qa in qa_list]


class QAEngine:
    """Generates all question/answer pairs for one frame of a scene graph."""

    def generate(self, G, gb, complete_types, current_index, window_size, data):
        G_old = []
        for t in range(current_index - 3, current_index + 1):
            subgraph, _ = gb.build_frame(data, t)
            assert subgraph is not None
            G_old.append(subgraph)

        graph_specs = SimpleNamespace(
            G=G,
            G_old=G_old,
            with_pointing_qa=True,
            with_pointing_cot=True,
            current_index=current_index,
            temporal=False,
            window_size=window_size,
            complete_types=complete_types,
            pointing_style="all",
        )

        qa = []
        qa += tag("lane_direction",
                  generate_lane_direction_questions(graph_specs))[::2]
        qa += tag("line_marking",
                  generate_line_marking_style_questions(graph_specs, variant="all"))[::5]
        qa += tag("line_type",
                  generate_line_marking_style_questions(graph_specs, variant="type"))[::5]
        qa += tag("line_color",
                  generate_line_marking_style_questions(graph_specs, variant="color"))[::5]
        qa += tag("existence_crossings",
                  generate_existence_questions_crossing(graph_specs))
        qa += tag("lane_type",
                  generate_lane_type_questions(graph_specs))
        qa += tag("pc_type",
                  generate_pc_type_questions(graph_specs))
        qa += tag("traffic_lights",
                  generate_traffic_light_status_questions(graph_specs))
        qa += tag("traffic_light_change",
                  generate_temporal_property_change_questions(graph_specs))
        qa += tag("counting_at_intersection_direction",
                  generate_counting_questions_direction(graph_specs))
        qa += tag("counting_off_intersection_direction",
                  generate_counting_questions_direction_off_intx(graph_specs))
        qa += tag("counting_off_intersection_generic",
                  generate_counting_questions_off_intx(graph_specs))
        qa += tag("pointing",
                  generate_pointing_questions(graph_specs))
        qa += tag("counting_off_crossing",
                  generate_counting_questions_crossing(graph_specs))
        qa += tag("vehicle_position",
                  generate_vehicle_position_questions(graph_specs))
        qa += tag("sign_lane_controls",
                  generate_controlled_lane_mcq_sign(graph_specs))
        qa += tag("tl_lane_controls",
                  generate_controlled_lane_mcq(graph_specs))
        qa += tag("pairwise_vehicle_location",
                  generate_pairwise_vehicle_comparison_questions(graph_specs))
        qa += tag("pairwise_lane_comparison_direction",
                  generate_pairwise_direction_comparison_questions(graph_specs))[::10]
        return qa

from battlescope_api.graph.state import GraphState


def planner_node(state: GraphState) -> GraphState:
    """Select up to 3 targets and set research_status."""
    return {"stage": "planner"}

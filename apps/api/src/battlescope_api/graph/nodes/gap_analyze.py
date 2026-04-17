from battlescope_api.graph.state import GraphState


def gap_analyze_node(state: GraphState) -> GraphState:
    """Infer gaps; set needs_more_research via coverage gates + LLM."""
    return {"stage": "gap_analyze"}

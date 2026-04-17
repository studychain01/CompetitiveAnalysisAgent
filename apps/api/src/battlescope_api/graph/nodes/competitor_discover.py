from battlescope_api.graph.state import GraphState


def competitor_discover_node(state: GraphState) -> GraphState:
    """Discover >=3 competitors with provenance (Tavily-led)."""
    return {"stage": "competitor_discover"}

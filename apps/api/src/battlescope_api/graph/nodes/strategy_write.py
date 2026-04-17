from battlescope_api.graph.state import GraphState


def strategy_write_node(state: GraphState) -> GraphState:
    """Emit UI-ready strategy_report JSON."""
    return {"stage": "strategy_write"}

from battlescope_api.graph.state import GraphState


def evidence_reduce_node(state: GraphState) -> GraphState:
    """Dedupe facts, normalize sources, compute evidence_coverage."""
    return {"stage": "evidence_reduce"}

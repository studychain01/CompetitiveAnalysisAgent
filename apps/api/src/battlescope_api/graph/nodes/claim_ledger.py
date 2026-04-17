from battlescope_api.graph.state import GraphState


def claim_ledger_node(state: GraphState) -> GraphState:
    """Link gaps to fact_ids before StrategyWriter prose."""
    return {"stage": "claim_ledger"}

from langgraph.graph import END, START, StateGraph

from battlescope_api.graph.nodes.intake import intake_node
from battlescope_api.graph.nodes.sec_risk import sec_risk_node
from battlescope_api.graph.state import GraphState


def build_graph():
    """
    LangGraph entry point. ``intake`` and ``sec_risk`` are async — use ``await graph.ainvoke(...)``.

    Next: add discover → plan → workers.
    """
    workflow = StateGraph(GraphState)
    workflow.add_node("intake", intake_node)
    workflow.add_node("sec_risk", sec_risk_node)
    workflow.add_edge(START, "intake")
    workflow.add_edge("intake", "sec_risk")
    workflow.add_edge("sec_risk", END)
    return workflow.compile()

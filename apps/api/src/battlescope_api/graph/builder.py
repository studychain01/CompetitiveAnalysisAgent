from langgraph.graph import END, START, StateGraph

from battlescope_api.graph.nodes.competitive_strategy import competitive_strategy_node
from battlescope_api.graph.nodes.competitor_discover import competitor_discover_node
from battlescope_api.graph.nodes.intake import intake_node
from battlescope_api.graph.nodes.peer_research_parallel import peer_research_parallel_node
from battlescope_api.graph.nodes.sec_risk import sec_risk_node
from battlescope_api.graph.state import GraphState


def build_graph():
    """
    LangGraph entry point. Nodes are async — use ``await graph.ainvoke(...)``.
    """
    workflow = StateGraph(GraphState)
    workflow.add_node("intake", intake_node)
    workflow.add_node("sec_risk", sec_risk_node)
    workflow.add_node("competitor_discover", competitor_discover_node)
    workflow.add_node("peer_research_parallel", peer_research_parallel_node)
    workflow.add_node("competitive_strategy", competitive_strategy_node)

    workflow.add_edge(START, "intake")
    workflow.add_edge("intake", "sec_risk")
    workflow.add_edge("sec_risk", "competitor_discover")
    workflow.add_edge("competitor_discover", "peer_research_parallel")
    workflow.add_edge("peer_research_parallel", "competitive_strategy")
    workflow.add_edge("competitive_strategy", END)

    return workflow.compile()

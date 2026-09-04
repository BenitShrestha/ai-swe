from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langgraph.constants import END
from langgraph.graph import StateGraph

from agent.prompts import *
from agent.states import *

_ = load_dotenv()

llm = ChatGroq(model="openai/gpt-oss-120b") # LLM Call

def planner_agent(state: dict) -> dict:
    """Function converts user prompt into a structured plan"""
    users_prompt = state["user_prompt"]

    # Provide schema when using structured output
    resp = resp = llm.with_structured_output(Plan).invoke(
                planner_prompt(user_prompt)
    ) # Invoke Planner Node
    if resp is None:
        raise ValueError("Planner didn't return a valid response.")
    return {"plan": resp}

def architect_agent(state: dict) -> dict:
    """Function creates a task plan from structured plan"""
    plan: Plan = state["plan"]
    resp = llm.with_structured_output(TaskPlan).invoke(
        architect_prompt(plan)
    )
    if resp is None:
        raise ValueError("Architect didn't return a valid response.")

    resp.plan = plan # Added Plan response into context, `ConfigDict` use
    return {"task_plan": resp}

graph = StateGraph(dict)

graph.add_node("planner", planner_agent)
graph.add_node("architect", architect_agent)

graph.add_edge("planner", "architect")
graph.set_entry_point("planner")

agent = graph.compile()

if __name__ == "__main__":
    user_prompt = "Create a simple calculator web application"

    result = agent.invoke({"user_prompt": user_prompt})

    print(result)
    print(agent.get_graph().draw_ascii())
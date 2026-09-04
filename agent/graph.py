from dotenv import load_dotenv
load_dotenv()

from pydantic import BaseModel

from langchain_groq import ChatGroq
from langgraph.constants import END
from langgraph.graph import StateGraph

from prompts import *
from states import *

llm = ChatGroq(model="openai/gpt-oss-120b") # LLM Call

user_prompt = "Create a simple calculator web application"

def planner_agent(state: dict) -> dict:
    users_prompt = state["user_prompt"]

    # Provide schema when using structured output
    resp = resp = llm.with_structured_output(Plan).invoke(
                planner_prompt(user_prompt)
    ) # Invoke Planner Node

    return {"plan": resp}

state = {
    "user_prompt": user_prompt,
    "planner_prompt": planner_prompt,
}

graph = StateGraph(dict)
graph.add_node("planner", planner_agent)
graph.set_entry_point("planner")

agent = graph.compile()

result = agent.invoke({"user_prompt": user_prompt})

print(result)

print(agent.get_graph().draw_ascii())
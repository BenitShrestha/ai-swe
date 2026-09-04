from dotenv import load_dotenv

import time
from groq import RateLimitError

from langchain_groq import ChatGroq
from langgraph.constants import END
from langgraph.graph import StateGraph
from langchain.agents import create_agent

from agent.prompts import *
from agent.states import *
from agent.tools import *

_ = load_dotenv()

llm = ChatGroq(model="openai/gpt-oss-120b") # LLM Call

def planner_agent(state: dict) -> dict: # State Object passed across nodes
    """Function converts user prompt into a structured plan"""
    user_prompt = state["user_prompt"]

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

def coder_agent(state: dict) -> dict:
    """Function for LangGraph tool-using Coder Agent"""
    coder_state = state.get("coder_state")
    if coder_state is None:
        coder_state = CoderState(task_plan=state["task_plan"], current_step_idx=0)

    steps = coder_state.task_plan.implementation_steps
    if coder_state.current_step_idx >= len(steps):
        return {"coder_state": coder_state, "status": "DONE"}

    current_task = steps[coder_state.current_step_idx]
    existing_content = read_file.run(current_task.filepath)

    system_prompt = coder_system_prompt()
    user_prompt = (
        f"Task: {current_task.task_description}\n"
        f"File: {current_task.filepath}\n"
        f"Existing content:\n{existing_content}\n"
        "Use write_file(path, content) to save your changes."
    )

    coder_tools = [read_file, write_file, list_files, get_current_directory]
    react_agent = create_agent(
        model=llm,
        tools=coder_tools
    )

    retry_delay = 5

    while True:
        try:
            react_agent.invoke({
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            })
            break

        except RateLimitError:
            print(f"Groq rate limit reached. Waiting {retry_delay} seconds...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)

    coder_state.current_step_idx += 1

    return {"coder_state": coder_state}

graph = StateGraph(dict)

graph.add_node("planner", planner_agent)
graph.add_node("architect", architect_agent)
graph.add_node("coder", coder_agent)

graph.add_edge("planner", "architect")
graph.add_edge("architect", "coder")
graph.add_conditional_edges(
    "coder",
    lambda s: "END" if s.get("status") == "DONE" else "coder",
    {"END": END, "coder": "coder"}
)

graph.set_entry_point("planner")

agent = graph.compile()

if __name__ == "__main__":
    user_prompt = " Create a simple calculator web application."

    result = agent.invoke({"user_prompt": user_prompt})

    print(result)
    print(agent.get_graph().draw_ascii())
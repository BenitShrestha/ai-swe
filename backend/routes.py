import uuid
import shutil
import pathlib
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent.graph import agent
from agent.tools import set_project_root, init_project_root
from backend.limiter import limiter

router = APIRouter()

JOBS_DIR = pathlib.Path(__file__).resolve().parent.parent / "jobs"
JOBS_DIR.mkdir(exist_ok=True)

jobs: dict[str, dict] = {}  # job_id -> {"status": ..., "error": ..., "zip_path": ...}
executor = ThreadPoolExecutor(max_workers=1)  # serialize agent runs (shared PROJECT_ROOT)


class GenerateRequest(BaseModel):
    prompt: str


def _describe_chunk(node_name: str, node_output: dict) -> str | None:
    """Turn one LangGraph stream chunk into a human-readable progress line."""
    if node_name == "planner":
        return "Planning the project..."

    if node_name == "architect":
        return "Breaking the plan into engineering tasks..."

    if node_name == "coder":
        coder_state = node_output.get("coder_state")
        if coder_state:
            total = len(coder_state.task_plan.implementation_steps)
            idx = min(coder_state.current_step_idx, total)
            return f"Coding: step {idx}/{total} complete"

    # inner ReAct loop (create_agent) — node names are typically "agent" / "tools"
    if node_name == "agent":
        messages = node_output.get("messages", [])
        if messages:
            last = messages[-1]
            tool_calls = getattr(last, "tool_calls", None)
            if tool_calls:
                call = tool_calls[0]
                path = call.get("args", {}).get("path", "")
                return f"  → calling {call['name']}({path})"

    if node_name == "tools":
        messages = node_output.get("messages", [])
        if messages:
            content = str(messages[-1].content)[:80]
            return f"  ← tool result: {content}"

    return None


def _run_job(job_id: str, prompt: str):
    try:
        project_root = JOBS_DIR / job_id / "generated_project"
        set_project_root(project_root)
        init_project_root()

        jobs[job_id]["log"] = []

        for namespace, chunk in agent.stream(
            {"user_prompt": prompt},
            {"recursion_limit": 200},
            subgraphs=True,
        ):
            for node_name, node_output in chunk.items():
                line = _describe_chunk(node_name, node_output)
                if line:
                    jobs[job_id]["log"].append(line)

        zip_base = JOBS_DIR / job_id / "output"
        zip_path = shutil.make_archive(str(zip_base), "zip", root_dir=project_root)

        jobs[job_id]["status"] = "done"
        jobs[job_id]["zip_path"] = zip_path
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)


@router.post("/generate")
@limiter.limit("5/hour")
def generate(req: GenerateRequest, request: Request):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "running"}
    executor.submit(_run_job, job_id, req.prompt)
    return {"job_id": job_id}


@router.get("/status/{job_id}")
def status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {
        "status": job["status"],
        "error": job.get("error"),
        "log": job.get("log", []),
    }


@router.get("/download/{job_id}")
@limiter.limit("5/hour")
def download(job_id: str, request: Request):
    job = jobs.get(job_id)
    if not job or job["status"] != "done":
        raise HTTPException(404, "Not ready or not found")
    return FileResponse(job["zip_path"], filename=f"{job_id}.zip")
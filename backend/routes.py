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


def _run_job(job_id: str, prompt: str):
    try:
        project_root = JOBS_DIR / job_id / "generated_project"
        set_project_root(project_root)
        init_project_root()

        agent.invoke({"user_prompt": prompt}, {"recursion_limit": 200})

        zip_base = JOBS_DIR / job_id / "output"
        zip_path = shutil.make_archive(str(zip_base), "zip", root_dir=project_root)

        jobs[job_id] = {"status": "done", "zip_path": zip_path}
    except Exception as e:
        jobs[job_id] = {"status": "error", "error": str(e)}


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
    return {"status": job["status"], "error": job.get("error")}


@router.get("/download/{job_id}")
@limiter.limit("5/hour")
def download(job_id: str, request: Request):
    job = jobs.get(job_id)
    if not job or job["status"] != "done":
        raise HTTPException(404, "Not ready or not found")
    return FileResponse(job["zip_path"], filename=f"{job_id}.zip")
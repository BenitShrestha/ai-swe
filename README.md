# AI-SWE

AI-SWE is an AI software engineering agent that turns a natural-language project request into an implementation plan and then generates the project files. It uses a LangGraph workflow with three stages:

1. **Planner**: Converts the user request into a structured project plan.
2. **Architect**: Converts the plan into ordered, file-level implementation tasks.
3. **Coder**: Executes those tasks using file-system tools and writes the generated project.

The LLM backend is **Groq** using `openai/gpt-oss-120b`.

## Live Demo

A hosted version is available at: **https://web-production-c56d49.up.railway.app/**

No login or API key is required. Requests are rate-limited (5 generations/hour per IP) to protect the shared Groq quota.

## Architecture

```text
User Prompt
    │
    ▼
┌──────────┐
│ Planner  │  → Plan
└────┬─────┘
     ▼
┌──────────┐
│ Architect│  → TaskPlan
└────┬─────┘
     ▼
┌──────────┐
│  Coder   │  → generated_project/
└────┬─────┘
     │
     └── repeats until all implementation steps are complete
```

The workflow is implemented as a LangGraph `StateGraph`. The coder is a tool-using agent with access to:

- `read_file`: Read a generated-project file
- `write_file`: Create or overwrite a generated-project file
- `list_files`: Inspect generated-project contents
- `get_current_directory`: Return the generated project root

File operations are restricted to the generated project's root directory.

This agent can be run two ways:

- **CLI**: `main.py`, unchanged, writes to a single local `generated_project/` folder.
- **Web app**: `backend/` (FastAPI) + `frontend/` (static HTML/JS), where each request runs in its own isolated `jobs/<job_id>/generated_project/` folder and produces a downloadable zip.

## Project Structure

```text
ai-swe/
├── agent/
│   ├── graph.py         # Planner, Architect, Coder agents and LangGraph workflow
│   ├── prompts.py       # Prompts used by the three agent stages
│   ├── states.py        # Pydantic models for plans, tasks and coder state
│   └── tools.py         # Sandboxed file-system tools
├── backend/
│   ├── main.py           # FastAPI app: mounts frontend, includes routes
│   ├── routes.py         # /generate, /status/{id}, /download/{id}
│   └── limiter.py        # Shared rate-limiter instance
├── frontend/
│   ├── index.html         # Prompt box, status, download link
│   └── app.js              # Calls backend, polls job status
├── src/
│   └── ai_swe/
│       └── __init__.py
├── main.py               # CLI entry point for running the agent locally
├── Procfile                # Railway start command
├── pyproject.toml          # Project metadata and dependencies
├── uv.lock                 # Locked dependency versions
├── .python-version         # Python version used by the project
├── .env                     # Local environment variables; not committed
├── generated_project/        # Created by the CLI run
└── jobs/                      # Created by the web app; per-request generated projects + zips
```

`generated_project/` and `jobs/` are intentionally ignored by Git because they contain generated output.

## Requirements

- Python **3.13+**
- [uv](https://docs.astral.sh/uv/)
- A **Groq API key**

The dependency set is defined in `pyproject.toml` and locked in `uv.lock`.

## Setup

Clone the repository and enter the project directory:

```bash
git clone <repository-url>
cd ai-swe
```

Create the environment and install the locked dependencies:

```bash
uv sync
```

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key
```

Do not commit `.env` or expose the API key.

## Run

### CLI

```bash
uv run python main.py
```

Enter a project request when prompted, for example:

```text
Create a simple calculator web application.
```

The agent will plan the project, create implementation tasks, and execute them into:

```text
generated_project/
```

### Web app (local)

```bash
uv run uvicorn backend.main:app --reload
```

Open `http://localhost:8000`, enter a prompt, and download the generated project as a zip once it's ready.

## Deployment (Railway)

The app is deployed on Railway using its default Nixpacks builder (no Dockerfile) plus a `Procfile`:

```text
web: uv run uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

Railway installs dependencies from `pyproject.toml`/`uv.lock` automatically and injects `$PORT`. Set `GROQ_API_KEY` in the Railway dashboard's environment variables.

## How the Workflow Works

### 1. Planner

`planner_agent()` sends the user's request to the LLM with a planning prompt and requests structured output conforming to the `Plan` Pydantic model.

A plan contains:

- application name
- description
- technology stack
- features
- files to create

### 2. Architect

`architect_agent()` receives the structured plan and produces a `TaskPlan`. Each implementation task identifies a file and describes what must be implemented, including relevant dependencies and integration details.

Tasks are ordered so that dependent work can be implemented after its prerequisites.

### 3. Coder

`coder_agent()` processes one implementation task at a time.

For each task it:

1. Reads the target file if it already exists.
2. Builds a task-specific prompt containing the task, file path and existing content.
3. Creates a tool-using LangChain agent.
4. Allows the agent to inspect and modify files.
5. Advances to the next implementation step.
6. Repeats until all tasks are complete.

If Groq returns a rate-limit error, the coder retries with an exponential backoff, up to a 60-second delay between attempts.

## Generated Project Safety

All generated-project file paths pass through `safe_path_for_project()` before reading or writing. Paths that resolve outside the current project root are rejected.

This limits the coder's file operations to the generated application directory. In the web app, each request gets its own isolated project root via `set_project_root()`, so concurrent requests don't collide.

```bash
uv run python main.py
```

### Rate-limit errors

**Groq rate limits:** The coder automatically retries with exponential backoff. If limits persist, wait and retry or use an account/API configuration with sufficient quota.

**App rate limit:** The web app caps requests at 5 generations/hour per IP. A `429` response means you'll need to wait before generating again.
# AI-SWE

AI-SWE is a command-line AI software engineering agent that turns a natural-language project request into an implementation plan and then generates the project files. It uses a LangGraph workflow with three stages:

1. **Planner** — converts the user request into a structured project plan.
2. **Architect** — converts the plan into ordered, file-level implementation tasks.
3. **Coder** — executes those tasks using file-system tools and writes the generated project.

The LLM backend is **Groq** using `openai/gpt-oss-120b`.

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

- `read_file` — read a generated-project file
- `write_file` — create or overwrite a generated-project file
- `list_files` — inspect generated-project contents
- `get_current_directory` — return the generated project root

File operations are restricted to the `generated_project/` directory.

## Project Structure

```text
ai-swe/
├── agent/
│   ├── graph.py       # Planner, Architect, Coder agents and LangGraph workflow
│   ├── prompts.py     # Prompts used by the three agent stages
│   ├── states.py      # Pydantic models for plans, tasks and coder state
│   └── tools.py       # Sandboxed file-system tools
├── src/
│   └── ai_swe/
│       └── __init__.py
├── main.py            # CLI entry point for running the agent
├── pyproject.toml     # Project metadata and dependencies
├── uv.lock            # Locked dependency versions
├── .python-version    # Python version used by the project
├── .env               # Local environment variables; not committed
└── generated_project/ # Created/generated application files
```

`generated_project/` is intentionally ignored by Git because it contains generated output.

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

Start the agent with:

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

### Recursion Limit

The default LangGraph recursion limit is `200`. It can be changed with:

```bash
uv run python main.py --recursion-limit 300
```

or:

```bash
uv run python main.py -r 300
```

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

All generated-project file paths pass through `safe_path_for_project()` before reading or writing. Paths that resolve outside `generated_project/` are rejected.

This limits the coder's file operations to the generated application directory.

## Development Notes

The main executable implementation is currently `main.py`, which imports the compiled graph from `agent.graph`.

The package entry declared in `pyproject.toml` (`ai-swe = "ai_swe:main"`) currently points to `src/ai_swe/__init__.py`, whose `main()` is only a placeholder. Therefore, use:

```bash
uv run python main.py
```

to run the actual AI-SWE agent.

## Troubleshooting

### `GROQ_API_KEY` errors

Check that `.env` exists in the repository root and contains a valid key:

```env
GROQ_API_KEY=your_groq_api_key
```

### Rate-limit errors

The coder automatically retries Groq rate-limit errors with exponential backoff. If limits persist, wait and retry the run or use an account/API configuration with sufficient quota.

### Generated files are missing

Check:

```text
generated_project/
```

The directory is created when the project-generation tools write files. It is ignored by Git and is therefore not included when another user clones the repository.
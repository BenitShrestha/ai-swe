// frontend/app.js
const btn = document.getElementById("generate");
const promptEl = document.getElementById("prompt");
const statusEl = document.getElementById("status");
const downloadEl = document.getElementById("download");
const logEl = document.getElementById("log");

let pollTimer = null;

btn.addEventListener("click", async () => {
  const prompt = promptEl.value.trim();
  if (!prompt) return;

  btn.disabled = true;
  downloadEl.style.display = "none";
  statusEl.textContent = "Starting...";

  try {
    const res = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });

    if (res.status === 429) {
      statusEl.textContent = "Rate limit reached. Try again later.";
      btn.disabled = false;
      return;
    }
    if (!res.ok) throw new Error(`Request failed: ${res.status}`);

    const { job_id } = await res.json();
    statusEl.textContent = "Generating... this can take a few minutes.";
    poll(job_id);
  } catch (err) {
    statusEl.textContent = `Error: ${err.message}`;
    btn.disabled = false;
  }
});

function poll(jobId) {
  pollTimer = setInterval(async () => {
    const res = await fetch(`/api/status/${jobId}`);
    const data = await res.json();

    logEl.style.display = "block";
    logEl.textContent = data.log.join("\n");
    logEl.scrollTop = logEl.scrollHeight;

    if (data.status === "done") {
      clearInterval(pollTimer);
      statusEl.textContent = "Done!";
      downloadEl.href = `/api/download/${jobId}`;
      downloadEl.style.display = "inline-block";
      btn.disabled = false;
    } else if (data.status === "error") {
      clearInterval(pollTimer);
      statusEl.textContent = `Error: ${data.error}`;
      btn.disabled = false;
    }
    // else still "running" — keep polling
  }, 2000); // tightened from 3000 since there's more to show now
}
const API_BASE = "http://127.0.0.1:8000";

const goalInput = document.getElementById("goalInput");
const runBtn = document.getElementById("runBtn");
const clearBtn = document.getElementById("clearBtn");
const terminalFeed = document.getElementById("terminalFeed");
const iterationBadge = document.getElementById("iterationBadge");
const engineStatus = document.getElementById("engineStatus");

const coderCard = document.getElementById("coderCard");
const sandboxCard = document.getElementById("sandboxCard");
const criticCard = document.getElementById("criticCard");

const finalResultCard = document.getElementById("finalResultCard");
const finalResultContent = document.getElementById("finalResultContent");

// Presets loader
document.querySelectorAll(".preset-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    goalInput.value = btn.getAttribute("data-preset");
  });
});

clearBtn.addEventListener("click", () => {
  goalInput.value = "";
  resetDashboard();
});

function resetDashboard() {
  terminalFeed.innerHTML = '<div class="terminal-placeholder">Ready for dispatch. Provide a goal and click <strong>Run Multi-Agent Loop</strong>.</div>';
  iterationBadge.textContent = "Iteration: 0";
  engineStatus.className = "status-pill status-ready";
  engineStatus.textContent = "Ready";
  setAgentActive(null);
  finalResultCard.classList.add("hidden");
  finalResultContent.innerHTML = "";
}

function setAgentActive(activeAgent) {
  [coderCard, sandboxCard, criticCard].forEach(card => card.classList.remove("agent-active"));
  const coderStatus = document.getElementById("coderStatus");
  const sandboxStatus = document.getElementById("sandboxStatus");
  const criticStatus = document.getElementById("criticStatus");

  coderStatus.textContent = "Idle";
  sandboxStatus.textContent = "Idle";
  criticStatus.textContent = "Idle";

  if (activeAgent === "coder") {
    coderCard.classList.add("agent-active");
    coderStatus.textContent = "Working";
  } else if (activeAgent === "sandbox") {
    sandboxCard.classList.add("agent-active");
    sandboxStatus.textContent = "Running";
  } else if (activeAgent === "critic") {
    criticCard.classList.add("agent-active");
    criticStatus.textContent = "Reviewing";
  }
}

function appendLog(category, title, content, isCode = false) {
  const placeholder = terminalFeed.querySelector(".terminal-placeholder");
  if (placeholder) placeholder.remove();

  const entry = document.createElement("div");
  entry.className = "log-entry";

  const header = document.createElement("div");
  header.className = `log-header ${category}`;
  header.textContent = title;
  entry.appendChild(header);

  if (isCode) {
    const pre = document.createElement("pre");
    pre.className = "code-block";
    pre.textContent = content;
    entry.appendChild(pre);
  } else if (content) {
    const text = document.createElement("div");
    text.className = "log-text";
    text.textContent = content;
    entry.appendChild(text);
  }

  terminalFeed.appendChild(entry);
  terminalFeed.scrollTop = terminalFeed.scrollHeight;
}

runBtn.addEventListener("click", async () => {
  const goal = goalInput.value.trim();
  if (!goal) return alert("Please specify an objective for the agent.");

  resetDashboard();
  runBtn.disabled = true;
  engineStatus.className = "status-pill status-running";
  engineStatus.textContent = "Executing...";

  const encodedGoal = encodeURIComponent(goal);
  const eventSource = new EventSource(`${API_BASE}/api/stream?goal=${encodedGoal}&max_iterations=4`);

  eventSource.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      handleAgentEvent(data, eventSource);
    } catch (err) {
      console.error("Malformed SSE payload", err);
    }
  };

  eventSource.onerror = (err) => {
    console.error("SSE connection error", err);
    appendLog("error", "⚡ Connection Terminated", "Event stream disconnected.");
    eventSource.close();
    finishRun();
  };
});

function handleAgentEvent(data, eventSource) {
  const step = data.step;

  if (step === "init") {
    appendLog("coder", "🚀 Initializing Task", data.message);
  } else if (step === "iteration_start") {
    iterationBadge.textContent = `Iteration: ${data.iteration}`;
  } else if (step === "coder_thinking") {
    setAgentActive("coder");
    appendLog("coder", "🧠 Coder Agent", data.message);
  } else if (step === "coder_output") {
    appendLog("coder", "💡 Coder Strategy", data.thought);
    appendLog("coder", "📝 Generated Code", data.code, true);
  } else if (step === "sandbox_executing") {
    setAgentActive("sandbox");
    appendLog("sandbox", "⚙️ Execution Sandbox", data.message);
  } else if (step === "sandbox_output") {
    const output = `Exit Code: ${data.exit_code}\nStdout: ${data.stdout || "[None]"}\nStderr: ${data.stderr || "[None]"}`;
    appendLog("sandbox", "📥 Sandbox Feedback", output, true);
  } else if (step === "critic_thinking") {
    setAgentActive("critic");
    appendLog("critic", "🔍 Critic Review", data.message);
  } else if (step === "critic_output") {
    if (data.approved) {
      appendLog("success", "✅ Critic Approved", "The executed code successfully satisfied the objective.");
    } else {
      appendLog("critic", "⚠️ Critique & Revision Needed", data.critique);
    }
  } else if (step === "completed") {
    eventSource.close();
    setAgentActive(null);
    finishRun();
    finalResultCard.classList.remove("hidden");
    finalResultContent.textContent = data.final_answer;
    appendLog("success", "🏁 Mission Complete", `Resolved cleanly in ${data.iterations} iteration(s).`);
  } else if (step === "failed" || step === "error") {
    eventSource.close();
    setAgentActive(null);
    finishRun();
    appendLog("error", "❌ Workflow Stopped", data.message);
  }
}

function finishRun() {
  runBtn.disabled = false;
  engineStatus.className = "status-pill status-ready";
  engineStatus.textContent = "Completed";
}

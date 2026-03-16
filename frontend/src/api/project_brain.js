const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  return response.json();
}

export function getProjectBrainStatus() {
  return request("/api/project-brain/status");
}

export function getProjectSnapshot() {
  return request("/api/project-brain/snapshot");
}

export function searchProjectIndex(query) {
  return request("/api/project-brain/index/search", {
    method: "POST",
    body: JSON.stringify({ query }),
  });
}

export function analyzeProjectGoal(goal) {
  return request("/api/project-brain/analyze", {
    method: "POST",
    body: JSON.stringify({ goal }),
  });
}

export function createRefactorPlan(goal) {
  return request("/api/project-brain/plan", {
    method: "POST",
    body: JSON.stringify({ goal }),
  });
}

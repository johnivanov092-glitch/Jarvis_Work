const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const res = await fetch(API_BASE + path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });

  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || "API error");
  }

  return res.json();
}

export const api = {
  projectSnapshot: () => request("/api/project-brain/snapshot"),
  runHistory: () => request("/api/run-history/runs?limit=20"),
  runGoal: (goal) =>
    request("/api/supervisor/run", {
      method: "POST",
      body: JSON.stringify({ goal, requested_by: "ide" })
    }),
  autoDev: (goal) =>
    request("/api/autodev/run", {
      method: "POST",
      body: JSON.stringify({
        goal,
        auto_apply: false,
        run_checks: false,
        commit_changes: false,
        requested_by: "ide"
      })
    })
};

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

export function getAutoDevStatus() {
  return request("/api/autodev/status");
}

export function runAutoDev(goal, options = {}) {
  return request("/api/autodev/run", {
    method: "POST",
    body: JSON.stringify({
      goal,
      auto_apply: !!options.auto_apply,
      run_checks: !!options.run_checks,
      commit_changes: !!options.commit_changes,
      requested_by: options.requested_by || "workspace",
    }),
  });
}

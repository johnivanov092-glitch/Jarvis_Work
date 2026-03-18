const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function parseResponse(res) {
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return await res.json();
  return await res.text();
}

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: options.method || "GET",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  const payload = await parseResponse(res);
  if (!res.ok) {
    const detail =
      typeof payload === "string"
        ? payload
        : payload?.detail || payload?.message || `Request failed: ${res.status}`;
    throw new Error(detail);
  }

  return payload;
}

export async function runAgentRuntime(userInput) {
  return request("/api/agent-runtime/run", {
    method: "POST",
    body: { user_input: userInput },
  });
}

export default {
  runAgentRuntime,
};

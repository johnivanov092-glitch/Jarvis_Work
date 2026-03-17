const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function buildUrl(path, query) {
  const url = new URL(API_BASE + path);

  if (query && typeof query === "object") {
    Object.entries(query).forEach(([key, value]) => {
      if (value === undefined || value === null || value === "") {
        return;
      }
      url.searchParams.set(key, String(value));
    });
  }

  return url.toString();
}

function normalizeErrorText(text) {
  if (!text) {
    return "API error";
  }

  try {
    const parsed = JSON.parse(text);
    if (parsed?.detail) {
      return typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail);
    }
  } catch {
    // noop
  }

  return text;
}

async function request(path, options = {}) {
  const { query, headers, ...rest } = options;

  const response = await fetch(buildUrl(path, query), {
    headers: {
      "Content-Type": "application/json",
      ...(headers || {}),
    },
    ...rest,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(normalizeErrorText(text));
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }

  return response.text();
}

export const api = {
  projectSnapshot: () => request("/api/project-brain/snapshot"),
  projectStatus: () => request("/api/project-brain/status"),
  readFile: (path) => request("/api/project-brain/file", { query: { path } }),

  ollamaStatus: () => request("/api/project-brain/agent/ollama/status"),
  ollamaPlan: ({ goal, selectedPath, selectedContent, model }) =>
    request("/api/project-brain/agent/ollama/plan", {
      method: "POST",
      body: JSON.stringify({
        goal,
        selected_path: selectedPath,
        selected_content: selectedContent,
        model,
      }),
    }),

  ollamaRun: ({ goal, selectedPath, selectedContent, model, projectFiles = [] }) =>
    request("/api/project-brain/agent/ollama/run", {
      method: "POST",
      body: JSON.stringify({
        goal,
        selected_path: selectedPath,
        selected_content: selectedContent,
        model,
        project_files: projectFiles,
        mode: "patch",
      }),
    }),

  previewPatch: (filePath, newContent) =>
    request("/api/phase11/patch/preview", {
      method: "POST",
      body: JSON.stringify({
        file_path: filePath,
        new_content: newContent,
      }),
    }),

  applyPatch: (filePath, newContent, expectedOldSha256 = null) =>
    request("/api/phase11/patch/apply", {
      method: "POST",
      body: JSON.stringify({
        file_path: filePath,
        new_content: newContent,
        expected_old_sha256: expectedOldSha256,
      }),
    }),

  rollbackPatch: (backupId) =>
    request("/api/phase11/patch/rollback", {
      method: "POST",
      body: JSON.stringify({
        backup_id: backupId,
      }),
    }),

  verifyPatch: (filePath) =>
    request("/api/phase11/patch/verify", {
      method: "POST",
      body: JSON.stringify({
        file_path: filePath,
      }),
    }),

  listBackups: (limit = 20) =>
    request("/api/phase11/patch/backups", {
      query: { limit },
    }),

  listExecutions: (limit = 20) =>
    request("/api/phase12/executions", {
      query: { limit },
    }),

  executionEvents: (executionId) =>
    request(`/api/phase12/executions/${encodeURIComponent(executionId)}/events`),

  startExecution: (goal, mode = "autonomous_dev", metadata = {}) =>
    request("/api/phase12/executions/start", {
      method: "POST",
      body: JSON.stringify({
        goal,
        mode,
        metadata,
      }),
    }),

  runGoal: (goal) =>
    request("/api/supervisor/run", {
      method: "POST",
      body: JSON.stringify({
        goal,
        requested_by: "ide",
      }),
    }),

  autoDev: (goal) =>
    request("/api/autodev/run", {
      method: "POST",
      body: JSON.stringify({
        goal,
        auto_apply: false,
        run_checks: false,
        commit_changes: false,
        requested_by: "ide",
      }),
    }),
};

const API = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function request(url, options = {}) {
  const res = await fetch(API + url, {
    method: options.method || "GET",
    headers: { "Content-Type": "application/json" },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  const contentType = res.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await res.json()
    : await res.text();

  if (!res.ok) {
    const message =
      typeof payload === "string"
        ? payload
        : payload?.detail || payload?.message || "API error";
    throw new Error(message);
  }

  return payload;
}

function asArray(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.items)) return payload.items;
  if (Array.isArray(payload?.results)) return payload.results;
  if (Array.isArray(payload?.data)) return payload.data;
  return [];
}

export const api = {
  health: () => request("/health"),

  getProjectSnapshot: () => request("/snapshot"),
  getProjectFile: (path) => request(`/file?path=${encodeURIComponent(path)}`),

  previewPatch: ({ path, instruction, content }) =>
    request("/agent/ollama/run", {
      method: "POST",
      body: {
        mode: "code",
        selected_path: path,
        selected_content: content,
        goal: instruction,
        project_files: [path],
      },
    }),

  diffPatch: ({ path, original, updated }) =>
    request("/api/jarvis/patch/diff", { method: "POST", body: { path, original, updated } }),
  applyPatch: ({ path, content }) =>
    request("/api/jarvis/patch/apply", { method: "POST", body: { path, content } }),
  applyPatchBatch: (items) =>
    request("/api/jarvis/patch/apply-batch", { method: "POST", body: { items } }),
  rollbackPatch: ({ path }) =>
    request("/api/jarvis/patch/rollback", { method: "POST", body: { path } }),
  verifyPatch: ({ path, content }) =>
    request("/api/jarvis/patch/verify", { method: "POST", body: { path, content } }),
  verifyPatchBatch: (items) =>
    request("/api/jarvis/patch/verify-batch", { method: "POST", body: { items } }),
  listPatchHistory: async (path = "") =>
    asArray(await request(`/api/jarvis/patch/history/list?path=${encodeURIComponent(path)}`)),
  getPatchHistoryItem: (id) =>
    request(`/api/jarvis/patch/history/get?id=${encodeURIComponent(id)}`),

  getProjectMap: () => request("/api/jarvis/project/map"),
  createFile: ({ path, content }) =>
    request("/api/jarvis/fs/create", { method: "POST", body: { path, content } }),
  deleteFile: ({ path }) =>
    request("/api/jarvis/fs/delete", { method: "POST", body: { path } }),
  renameFile: ({ old_path, new_path }) =>
    request("/api/jarvis/fs/rename", { method: "POST", body: { old_path, new_path } }),

  patchPlan: ({ goal, current_path, current_content, staged_paths }) =>
    request("/api/jarvis/patch/plan", {
      method: "POST",
      body: { goal, current_path, current_content, staged_paths },
    }),

  runTask: ({ goal, mode, current_path, staged_paths }) =>
    request("/api/jarvis/task/run", {
      method: "POST",
      body: { goal, mode, current_path, staged_paths },
    }),
  listTaskHistory: async () => asArray(await request("/api/jarvis/task/history/list")),
  getTaskHistoryItem: (id) => request(`/api/jarvis/task/history/get?id=${encodeURIComponent(id)}`),

  runSupervisor: ({ goal, mode, current_path, staged_paths, auto_apply }) =>
    request("/api/jarvis/supervisor/run", {
      method: "POST",
      body: { goal, mode, current_path, staged_paths, auto_apply },
    }),
  executeSupervisor: ({ goal, current_path, current_content, auto_apply }) =>
    request("/api/jarvis/supervisor/execute", {
      method: "POST",
      body: { goal, current_path, current_content, auto_apply },
    }),
  listSupervisorHistory: async () => asArray(await request("/api/jarvis/supervisor/history/list")),
  getSupervisorHistoryItem: (id) => request(`/api/jarvis/supervisor/history/get?id=${encodeURIComponent(id)}`),

  runPhase19: ({ goal, mode, selected_paths }) =>
    request("/api/jarvis/phase19/run", { method: "POST", body: { goal, mode, selected_paths } }),
  listPhase19History: async () => asArray(await request("/api/jarvis/phase19/history/list")),
  getPhase19HistoryItem: (id) => request(`/api/jarvis/phase19/history/get?id=${encodeURIComponent(id)}`),

  runPhase20: ({ goal, selected_paths }) =>
    request("/api/jarvis/phase20/run", { method: "POST", body: { goal, selected_paths } }),
  buildPhase20PreviewQueue: ({ goal, targets }) =>
    request("/api/jarvis/phase20/preview-queue", { method: "POST", body: { goal, targets } }),
  buildPhase20ExecutionState: ({ goal, queue_items, staged_paths }) =>
    request("/api/jarvis/phase20/execution-state", {
      method: "POST",
      body: { goal, queue_items, staged_paths },
    }),
  listPhase20History: async () => asArray(await request("/api/jarvis/phase20/history/list")),
  getPhase20HistoryItem: (id) => request(`/api/jarvis/phase20/history/get?id=${encodeURIComponent(id)}`),

  runPhase21: ({ goal, queue_items, execution_state }) =>
    request("/api/jarvis/phase21/run", {
      method: "POST",
      body: { goal, queue_items, execution_state },
    }),
  listPhase21History: async () => asArray(await request("/api/jarvis/phase21/history/list")),
  getPhase21HistoryItem: (id) => request(`/api/jarvis/phase21/history/get?id=${encodeURIComponent(id)}`),

  runStabilizationPreflight: ({ phase20_queue_items, phase20_execution_state, phase21_run, staged_paths }) =>
    request("/api/jarvis/stabilization/preflight", {
      method: "POST",
      body: { phase20_queue_items, phase20_execution_state, phase21_run, staged_paths },
    }),
};

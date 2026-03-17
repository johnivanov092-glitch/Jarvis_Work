const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function buildUrl(path, query) {
  const url = new URL(API_BASE + path);
  if (query && typeof query === "object") {
    Object.entries(query).forEach(([key, value]) => {
      if (value === undefined || value === null || value === "") return;
      url.searchParams.set(key, String(value));
    });
  }
  return url.toString();
}

function normalizeErrorText(text) {
  if (!text) return "API error";
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
  readFile: (path) => request("/api/project-brain/file", { query: { path } }),
  legacyAgents: () => request("/api/project-brain/agent/legacy/catalog"),
  ollamaStatus: () => request("/api/project-brain/agent/ollama/status"),

  uploadAttachment: async (file) => {
    const body = new FormData();
    body.append("file", file);
    body.append("source", "upload");
    return request("/api/project-brain/chat/attachment", { method: "POST", body });
  },

  attachProjectFile: async (path) => {
    const body = new FormData();
    body.append("path", path);
    return request("/api/project-brain/chat/project-file", { method: "POST", body });
  },

  sendChat: ({ message, model, mode = "auto", webEnabled = true, sessionId = null, attachmentIds = [], selectedProjectPaths = [] }) =>
    request("/api/project-brain/chat/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        model,
        mode,
        web_enabled: webEnabled,
        session_id: sessionId,
        attachment_ids: attachmentIds,
        selected_project_paths: selectedProjectPaths,
      }),
    }),

  previewPatch: (filePath, newContent) =>
    request("/api/phase11/patch/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_path: filePath, new_content: newContent }),
    }),

  applyPatch: (filePath, newContent, expectedOldSha256 = null) =>
    request("/api/phase11/patch/apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        file_path: filePath,
        new_content: newContent,
        expected_old_sha256: expectedOldSha256,
      }),
    }),

  rollbackPatch: (backupId) =>
    request("/api/phase11/patch/rollback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ backup_id: backupId }),
    }),

  verifyPatch: (filePath) =>
    request("/api/phase11/patch/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_path: filePath }),
    }),

  listBackups: (limit = 20) => request("/api/phase11/patch/backups", { query: { limit } }),
};

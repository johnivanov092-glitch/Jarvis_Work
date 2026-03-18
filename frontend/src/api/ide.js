const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function normalizeError(payload, status) {
  if (typeof payload === "string") return payload;
  if (Array.isArray(payload)) {
    return payload.map((item) => item?.msg || JSON.stringify(item)).join("; ");
  }
  if (Array.isArray(payload?.detail)) {
    return payload.detail.map((item) => item?.msg || JSON.stringify(item)).join("; ");
  }
  return payload?.detail || payload?.message || `Request failed: ${status}`;
}

async function parseResponse(res) {
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return await res.json();
  }
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
    throw new Error(normalizeError(payload, res.status));
  }

  return payload;
}

async function safeRequest(path, options = {}, fallback = null) {
  try {
    return await request(path, options);
  } catch (error) {
    if (fallback !== null) {
      return typeof fallback === "function" ? fallback(error) : fallback;
    }
    throw error;
  }
}

function normalizeArray(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.items)) return payload.items;
  if (Array.isArray(payload?.data)) return payload.data;
  if (Array.isArray(payload?.results)) return payload.results;
  if (Array.isArray(payload?.chats)) return payload.chats;
  if (Array.isArray(payload?.messages)) return payload.messages;
  if (Array.isArray(payload?.files)) return payload.files;
  return [];
}

function normalizeChat(item = {}) {
  return {
    id: item.id ?? item.chat_id ?? item.uuid ?? "",
    title: item.title ?? item.name ?? "Новый чат",
    pinned: Boolean(item.pinned),
    memory_saved: Boolean(item.memory_saved ?? item.saved_to_memory ?? item.saved),
    created_at: item.created_at ?? item.createdAt ?? "",
    updated_at: item.updated_at ?? item.updatedAt ?? "",
    ...item,
  };
}

function normalizeMessage(item = {}) {
  const content =
    item.content ??
    item.answer ??
    item.response ??
    item.message ??
    item.text ??
    "";

  return {
    id: item.id ?? item.message_id ?? item.uuid ?? `${item.role || "msg"}-${Date.now()}`,
    role: item.role ?? item.sender ?? "assistant",
    content: typeof content === "string" ? content : String(content ?? ""),
    created_at: item.created_at ?? item.createdAt ?? "",
    ...item,
    content: typeof content === "string" ? content : String(content ?? ""),
  };
}

function unwrapItem(payload) {
  if (!payload || typeof payload !== "object") return payload;
  if (payload.item && typeof payload.item === "object") return payload.item;
  if (payload.chat && typeof payload.chat === "object") return payload.chat;
  if (payload.message && typeof payload.message === "object") return payload.message;
  if (payload.data && typeof payload.data === "object" && !Array.isArray(payload.data)) return payload.data;
  return payload;
}

export async function listChats() {
  const payload = await safeRequest("/api/jarvis/chats", {}, []);
  return normalizeArray(payload).map(normalizeChat);
}

export async function createChat(body = {}) {
  const payload = await request("/api/jarvis/chats", { method: "POST", body });
  return normalizeChat(unwrapItem(payload));
}

export async function renameChat(arg1, arg2) {
  const params = typeof arg1 === "object" && arg1 !== null ? arg1 : { id: arg1, title: arg2 };
  const payload = await request(`/api/jarvis/chats/${encodeURIComponent(params.id)}`, {
    method: "PATCH",
    body: { title: params.title },
  });
  return normalizeChat(unwrapItem(payload));
}

export async function pinChat(arg1, arg2) {
  const params = typeof arg1 === "object" && arg1 !== null ? arg1 : { id: arg1, pinned: arg2 };
  const payload = await request(`/api/jarvis/chats/${encodeURIComponent(params.id)}/pin`, {
    method: "PATCH",
    body: { pinned: Boolean(params.pinned) },
  });
  return normalizeChat(unwrapItem(payload));
}

export async function saveChatToMemory(arg1, arg2) {
  const params = typeof arg1 === "object" && arg1 !== null ? arg1 : { id: arg1, saved: arg2 };
  const payload = await safeRequest(
    `/api/jarvis/chats/${encodeURIComponent(params.id)}/memory`,
    { method: "PATCH", body: { saved: Boolean(params.saved) } },
    () =>
      request(`/api/jarvis/chats/${encodeURIComponent(params.id)}`, {
        method: "PATCH",
        body: { memory_saved: Boolean(params.saved) },
      })
  );
  return normalizeChat(unwrapItem(payload));
}

export async function deleteChat(arg) {
  const id = typeof arg === "object" && arg !== null ? arg.id : arg;
  return request(`/api/jarvis/chats/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export async function getMessages(arg) {
  const chatId = typeof arg === "object" && arg !== null ? arg.chatId : arg;
  const payload = await safeRequest(`/api/jarvis/chats/${encodeURIComponent(chatId)}/messages`, {}, []);
  return normalizeArray(payload).map(normalizeMessage);
}

export async function addMessage(body = {}) {
  const payload = await request("/api/jarvis/messages", {
    method: "POST",
    body: {
      ...body,
      content:
        typeof body.content === "string"
          ? body.content
          : String(body.content ?? ""),
    },
  });
  return normalizeMessage(unwrapItem(payload));
}

export async function sendMessage(body = {}) {
  return addMessage(body);
}

export async function execute(body = {}) {
  const userInput = String(
    body.user_input ??
      body.message ??
      body.prompt ??
      body.text ??
      body.query ??
      ""
  ).trim();

  const response = await request("/api/chat/send", {
    method: "POST",
    body: {
      model_name: body.model_name ?? body.model ?? "qwen3:8b",
      profile_name: body.profile_name ?? body.profile ?? "default",
      user_input: userInput,
      history: Array.isArray(body.history) ? body.history : [],
      use_memory: body.use_memory ?? true,
      use_library: body.use_library ?? true,
    },
  });

  const content =
    response?.content ??
    response?.answer ??
    response?.response ??
    response?.message ??
    "";

  return {
    ...response,
    content: typeof content === "string" ? content : String(content ?? ""),
  };
}

export async function listOllamaModels() {
  const payload = await safeRequest("/api/jarvis/models", {}, []);
  if (Array.isArray(payload?.models)) return { models: payload.models };
  if (Array.isArray(payload?.items)) return { models: payload.items };
  if (Array.isArray(payload)) return { models: payload };
  return { models: [] };
}

export async function getSettings() {
  return safeRequest("/api/jarvis/settings", {}, {});
}

export async function updateSettings(body = {}) {
  return request("/api/jarvis/settings", { method: "PUT", body });
}

export async function searchJarvis(query = "") {
  const payload = await safeRequest(`/api/jarvis/search?q=${encodeURIComponent(query)}`, {}, []);
  return normalizeArray(payload);
}

export async function listProjects() {
  const payload = await safeRequest("/api/jarvis/projects", {}, []);
  return normalizeArray(payload);
}

export async function getProjectSnapshot() {
  const payload = await request("/api/project-brain/snapshot");
  return {
    ...payload,
    files: Array.isArray(payload?.files) ? payload.files : [],
  };
}

export async function getProjectFile(path) {
  return request(`/api/project-brain/file?path=${encodeURIComponent(path)}`);
}

export async function getProjectBrainStatus() {
  return safeRequest("/api/project-brain/status", {}, { status: "unknown" });
}

export async function listPatchHistory({ path = "", limit = 20 } = {}) {
  const query = new URLSearchParams();
  if (path) query.set("path", path);
  if (limit) query.set("limit", String(limit));
  const payload = await safeRequest(
    `/api/jarvis/patch/history/list${query.toString() ? `?${query.toString()}` : ""}`,
    {},
    { items: [] }
  );
  return { ...payload, items: normalizeArray(payload) };
}

export async function previewPatch(body = {}) {
  return request("/api/jarvis/patch/diff", { method: "POST", body });
}

export async function applyPatch(body = {}) {
  return request("/api/jarvis/patch/apply", { method: "POST", body });
}

export async function rollbackPatch(body = {}) {
  return request("/api/jarvis/patch/rollback", { method: "POST", body });
}

export async function verifyPatch(body = {}) {
  return request("/api/jarvis/patch/verify", { method: "POST", body });
}

export async function listRunHistory() {
  const payload = await safeRequest("/api/jarvis/run-history/list", {}, { items: [] });
  return { ...payload, items: normalizeArray(payload) };
}

export async function autocodeSuggest(body = {}) {
  return request("/api/jarvis/autocode/suggest", { method: "POST", body });
}

export async function autocodeLoop(body = {}) {
  return request("/api/jarvis/autocode/loop", { method: "POST", body });
}

export const api = {
  listChats,
  createChat,
  renameChat,
  pinChat,
  saveChatToMemory,
  deleteChat,
  getMessages,
  addMessage,
  sendMessage,
  execute,
  listOllamaModels,
  getSettings,
  updateSettings,
  searchJarvis,
  listProjects,
  getProjectSnapshot,
  getProjectFile,
  getProjectBrainStatus,
  listPatchHistory,
  previewPatch,
  applyPatch,
  rollbackPatch,
  verifyPatch,
  listRunHistory,
  autocodeSuggest,
  autocodeLoop,
};

export default api;

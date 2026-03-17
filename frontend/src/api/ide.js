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
  listChats: () => request("/api/jarvis/chats"),
  createChat: (title = "Новый чат") =>
    request("/api/jarvis/chats", { method: "POST", body: { title } }),
  renameChat: (id, title) =>
    request(`/api/jarvis/chats/${id}`, { method: "PATCH", body: { title } }),
  deleteChat: (id) =>
    request(`/api/jarvis/chats/${id}`, { method: "DELETE" }),
  pinChat: (id, pinned) =>
    request(`/api/jarvis/chats/${id}/pin`, {
      method: "PATCH",
      body: { pinned },
    }),
  getMessages: (id) => request(`/api/jarvis/chats/${id}/messages`),
  addMessage: (payload) =>
    request("/api/jarvis/messages", { method: "POST", body: payload }),
  search: (q) =>
    request(`/api/jarvis/search?q=${encodeURIComponent(q)}`),

  execute: (payload) =>
    request("/api/jarvis/execute", { method: "POST", body: payload }),

  listMemory: async (q = "") => {
    const payload = await request(`/api/jarvis/memory/list?q=${encodeURIComponent(q)}`);
    return asArray(payload);
  },
  saveMemory: (payload) =>
    request("/api/jarvis/memory/save", { method: "POST", body: payload }),
  deleteMemory: (id) =>
    request("/api/jarvis/memory/delete", { method: "POST", body: { id } }),
};

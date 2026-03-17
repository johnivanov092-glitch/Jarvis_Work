const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const { method = "GET", body } = options;
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    const message = typeof payload === "string" ? payload : payload?.detail || payload?.message || "Ошибка API";
    throw new Error(message);
  }
  return payload;
}

export const api = {
  getModels: () => request("/api/jarvis/models"),
  getSettings: () => request("/api/jarvis/settings"),
  saveSettings: (payload) => request("/api/jarvis/settings", { method: "PUT", body: payload }),
  listChats: () => request("/api/jarvis/chats"),
  createChat: (title = "Новый чат") => request("/api/jarvis/chats", { method: "POST", body: { title } }),
  renameChat: (chatId, title) => request(`/api/jarvis/chats/${chatId}`, { method: "PATCH", body: { title } }),
  deleteChat: (chatId) => request(`/api/jarvis/chats/${chatId}`, { method: "DELETE" }),
  getMessages: (chatId) => request(`/api/jarvis/chats/${chatId}/messages`),
  addMessage: (payload) => request("/api/jarvis/messages", { method: "POST", body: payload }),
};

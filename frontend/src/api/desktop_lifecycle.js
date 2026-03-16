let invokeFn = null;

async function getInvoke() {
  if (invokeFn) return invokeFn;
  try {
    const mod = await import("@tauri-apps/api/core");
    invokeFn = mod.invoke;
    return invokeFn;
  } catch (_err) {
    return null;
  }
}

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

export async function tauriStartBackend() {
  const invoke = await getInvoke();
  if (!invoke) {
    return { running: false, mode: "browser", message: "Tauri runtime not available" };
  }
  return invoke("start_backend");
}

export async function tauriStopBackend() {
  const invoke = await getInvoke();
  if (!invoke) {
    return { running: false, mode: "browser", message: "Tauri runtime not available" };
  }
  return invoke("stop_backend");
}

export async function tauriBackendStatus() {
  const invoke = await getInvoke();
  if (!invoke) {
    return { running: false, pid: null, mode: "browser" };
  }
  return invoke("backend_status");
}

export async function getDesktopLifecycleConfig() {
  return request("/api/desktop-lifecycle/config");
}

export async function getDesktopLifecycleEnv() {
  return request("/api/desktop-lifecycle/env");
}

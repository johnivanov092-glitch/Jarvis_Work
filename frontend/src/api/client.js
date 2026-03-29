export const API_BASE =
  import.meta.env.VITE_API_BASE_URL || `http://${window.location.hostname}:8000`;

export function buildApiUrl(path = "") {
  if (!path) return API_BASE;
  return path.startsWith("http://") || path.startsWith("https://")
    ? path
    : `${API_BASE}${path}`;
}

export function normalizeError(payload, status) {
  if (typeof payload === "string") return payload;
  if (Array.isArray(payload)) {
    return payload.map((item) => item?.msg || JSON.stringify(item)).join("; ");
  }
  if (Array.isArray(payload?.detail)) {
    return payload.detail.map((item) => item?.msg || JSON.stringify(item)).join("; ");
  }
  return payload?.detail || payload?.message || payload?.error || `Request failed: ${status}`;
}

export async function parseResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return response.json();
  if (contentType.startsWith("text/")) return response.text();
  return response.blob();
}

export async function request(path, options = {}) {
  const {
    method = "GET",
    headers = {},
    body,
    raw = false,
    responseType,
    ...rest
  } = options;

  const finalHeaders = new Headers(headers);
  let finalBody = body;

  if (body !== undefined && body !== null) {
    const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
    const isBlob = typeof Blob !== "undefined" && body instanceof Blob;
    const isParams = typeof URLSearchParams !== "undefined" && body instanceof URLSearchParams;

    if (!isFormData && !isBlob && !isParams && typeof body === "object") {
      if (!finalHeaders.has("Content-Type")) {
        finalHeaders.set("Content-Type", "application/json");
      }
      finalBody = JSON.stringify(body);
    }
  }

  const response = await fetch(buildApiUrl(path), {
    method,
    headers: finalHeaders,
    body: finalBody,
    ...rest,
  });

  if (raw) return response;

  let payload;
  if (responseType === "text") payload = await response.text();
  else if (responseType === "blob") payload = await response.blob();
  else payload = await parseResponse(response);

  if (!response.ok) {
    throw new Error(normalizeError(payload, response.status));
  }

  return payload;
}

export async function safeRequest(path, options = {}, fallback = null) {
  try {
    return await request(path, options);
  } catch (error) {
    if (fallback !== null) {
      return typeof fallback === "function" ? fallback(error) : fallback;
    }
    throw error;
  }
}

const SERVER_BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";
const BROWSER_BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

function backendUrl() {
  return typeof window === "undefined" ? SERVER_BACKEND_URL : BROWSER_BACKEND_URL;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  token: string,
  init?: RequestInit
): Promise<T> {
  const res = await fetch(`${backendUrl()}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      Authorization: `Bearer ${token}`,
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });

  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = body.detail ?? message;
    } catch {
      // response wasn't JSON — keep statusText
    }
    throw new ApiError(res.status, message);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string, token: string) => request<T>(path, token),
  post: <T>(path: string, token: string, body?: unknown) =>
    request<T>(path, token, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, token: string, body?: unknown) =>
    request<T>(path, token, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string, token: string) => request<T>(path, token, { method: "DELETE" }),
};

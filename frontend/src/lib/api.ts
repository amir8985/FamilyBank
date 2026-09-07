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

// Fire-and-forget: reports how long this call actually took as perceived
// in the browser (network + server, not just the server's own view of
// itself) to /internal/client-metrics, so slow-client vs. slow-server can
// be told apart — see backend/app/core/request_logging.py. Browser-only:
// a server-side (SSR) call to our own backend is already covered by the
// backend's own request log, so there's nothing new to learn by reporting
// it a second time from here.
function reportClientMetric(report: {
  path: string;
  method: string;
  durationMs: number;
  statusCode: number | null;
  token: string;
  detail?: string;
}) {
  if (typeof window === "undefined") return;
  try {
    fetch(`${backendUrl()}/internal/client-metrics`, {
      method: "POST",
      keepalive: true,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${report.token}`,
      },
      body: JSON.stringify({
        path: report.path,
        method: report.method,
        duration_ms: report.durationMs,
        status_code: report.statusCode ?? undefined,
        detail: report.detail,
      }),
    }).catch(() => {
      // Telemetry must never surface an error of its own.
    });
  } catch {
    // ditto — a beacon that throws synchronously is still not our problem.
  }
}

async function request<T>(
  path: string,
  token: string,
  init?: RequestInit
): Promise<T> {
  const start = performance.now();
  let statusCode: number | null = null;
  let detail: string | undefined;
  try {
    const res = await fetch(`${backendUrl()}${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${token}`,
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
    statusCode = res.status;

    if (!res.ok) {
      let message = res.statusText;
      try {
        const body = await res.json();
        message = body.detail ?? message;
      } catch {
        // response wasn't JSON — keep statusText
      }
      detail = message;
      throw new ApiError(res.status, message);
    }

    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  } catch (err) {
    if (!(err instanceof ApiError)) detail = (err as Error).message;
    throw err;
  } finally {
    reportClientMetric({
      path,
      method: init?.method ?? "GET",
      durationMs: performance.now() - start,
      statusCode,
      token,
      detail,
    });
  }
}

export const api = {
  get: <T>(path: string, token: string) => request<T>(path, token),
  post: <T>(path: string, token: string, body?: unknown) =>
    request<T>(path, token, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, token: string, body?: unknown) =>
    request<T>(path, token, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string, token: string) => request<T>(path, token, { method: "DELETE" }),
};

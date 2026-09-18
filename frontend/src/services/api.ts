// frontend/src/services/api.ts
// Vigil HTTP Client with typed error extraction and proxy support

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "";

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }

  get isConflict(): boolean {
    return this.status === 409;
  }

  get errorCode(): string {
    return this.data?.error || (this.status === 409 ? "CONFLICT" : "UNKNOWN_ERROR");
  }
}

interface RequestOptions extends RequestInit {
  params?: Record<string, any>;
}

export async function request<T = any>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { params, headers, ...customConfig } = options;

  let url = `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        searchParams.append(key, String(value));
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      url += `${url.includes("?") ? "&" : "?"}${queryString}`;
    }
  }

  // Inject auth token if present
  const token = localStorage.getItem("vigil_auth_token");
  const authHeaders: Record<string, string> = {};
  if (token) {
    authHeaders["Authorization"] = `Bearer ${token}`;
  }

  const config: RequestInit = {
    method: customConfig.method || "GET",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...headers,
    },
    ...customConfig,
  };

  const response = await fetch(url, config);

  if (!response.ok) {
    let errorData: any;
    try {
      errorData = await response.json();
    } catch {
      errorData = { message: response.statusText };
    }

    let message: string;
    if (typeof errorData?.detail === "string") {
      message = errorData.detail;
    } else if (typeof errorData?.detail?.message === "string") {
      message = errorData.detail.message;
    } else if (typeof errorData?.message === "string") {
      message = errorData.message;
    } else {
      message = `Request failed with status ${response.status}`;
    }

    throw new ApiError(response.status, message, errorData);
  }

  // Check if response has content
  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("application/json")) {
    return response.json();
  }
  return response.text() as unknown as T;
}

export const api = {
  get: <T = any>(endpoint: string, params?: Record<string, any>) =>
    request<T>(endpoint, { method: "GET", params }),

  post: <T = any>(endpoint: string, body?: any) =>
    request<T>(endpoint, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    }),

  patch: <T = any>(endpoint: string, body?: any) =>
    request<T>(endpoint, {
      method: "PATCH",
      body: body ? JSON.stringify(body) : undefined,
    }),

  delete: <T = any>(endpoint: string) =>
    request<T>(endpoint, { method: "DELETE" }),
};

// frontend/src/services/authService.ts
// Authentication and user session service for Vigil

import { api } from "./api";

export interface User {
  user_id: string;
  username: string;
  email: string;
  role: string;
  team: string;
  access: string;
  full_name: string;
  is_active: boolean;
  last_login_at?: string | null;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export const authService = {
  /**
   * Authenticate user with username/email and password
   */
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    return api.post<AuthResponse>("/api/auth/login", credentials);
  },

  /**
   * Fetch currently authenticated user profile using active JWT
   */
  async getMe(): Promise<User> {
    return api.get<User>("/api/auth/me");
  },

  /**
   * Notify server of session termination
   */
  async logout(): Promise<{ status: string; message: string }> {
    try {
      return await api.post("/api/auth/logout");
    } catch {
      return { status: "ok", message: "Logged out locally." };
    }
  },

  /**
   * List all system users (audit view)
   */
  async getUsers(): Promise<User[]> {
    return api.get<User[]>("/api/auth/users");
  },
};

import { create } from "zustand";
import type { UserProfile } from "../types/domain";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: UserProfile | null;
  setAuth: (accessToken: string, user: UserProfile, refreshToken?: string) => void;
  logout: () => void;
}

const storedToken = localStorage.getItem("nayami_access_token");
const storedRefreshToken = localStorage.getItem("nayami_refresh_token");
const storedUser = localStorage.getItem("nayami_user");

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: storedToken,
  refreshToken: storedRefreshToken,
  user: storedUser ? (JSON.parse(storedUser) as UserProfile) : null,
  setAuth: (accessToken, user, refreshToken) => {
    localStorage.setItem("nayami_access_token", accessToken);
    if (refreshToken) {
      localStorage.setItem("nayami_refresh_token", refreshToken);
    }
    localStorage.setItem("nayami_user", JSON.stringify(user));
    set({ accessToken, refreshToken: refreshToken || get().refreshToken, user });
  },
  logout: () => {
    localStorage.removeItem("nayami_access_token");
    localStorage.removeItem("nayami_user");
    localStorage.removeItem("nayami_refresh_token");
    set({ accessToken: null, refreshToken: null, user: null });
  }
}));

window.addEventListener("nayami-auth-expired", () => {
  useAuthStore.getState().logout();
});

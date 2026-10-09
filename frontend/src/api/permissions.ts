import { http, unwrapResponse } from "./http";
import type { BackendRole } from "../types/domain";

export function listRolesApi() {
  return unwrapResponse<BackendRole[]>(http.get("/system/roles"));
}

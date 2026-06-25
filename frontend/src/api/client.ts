/** Axios HTTP client configured for the MII backend API. */

import axios from "axios";
import type {
  DiscoveryStatus,
  ExplainPathResponse,
  ExplainRiskResponse,
  GraphStats,
  IdentityDetail,
  IdentityFilters,
  IdentityListResponse,
  TraverseResponse,
} from "./types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api/v1",
  headers: { "Content-Type": "application/json" },
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error("API Error:", error.response?.data || error.message);
    return Promise.reject(error);
  }
);

// Identity endpoints
export async function fetchIdentities(filters: IdentityFilters = {}): Promise<IdentityListResponse> {
  const params = Object.fromEntries(
    Object.entries(filters).filter(([, v]) => v !== undefined && v !== null)
  );
  const { data } = await api.get("/identities", { params });
  return data;
}

export async function fetchIdentityDetail(id: string): Promise<IdentityDetail> {
  const { data } = await api.get(`/identities/${id}`);
  return data;
}

// Discovery endpoints
export async function triggerDiscovery(): Promise<{ status: string; message: string }> {
  const { data } = await api.post("/discovery/run");
  return data;
}

export async function fetchDiscoveryStatus(): Promise<DiscoveryStatus> {
  const { data } = await api.get("/discovery/status");
  return data;
}

// Graph endpoints
export async function fetchGraphTraverse(startId: string, maxDepth = 10): Promise<TraverseResponse> {
  const { data } = await api.get("/graph/traverse", {
    params: { start_identity_id: startId, max_depth: maxDepth },
  });
  return data;
}

export async function fetchGraphStats(): Promise<GraphStats> {
  const { data } = await api.get("/graph/stats");
  return data;
}

// AI endpoints
export async function explainRisk(identityId: string): Promise<ExplainRiskResponse> {
  const { data } = await api.post("/ai/explain-risk", { identity_id: identityId });
  return data;
}

export async function explainPath(sourceId: string, targetId: string): Promise<ExplainPathResponse> {
  const { data } = await api.post("/ai/explain-path", {
    source_identity_id: sourceId,
    target_identity_id: targetId,
  });
  return data;
}

// Risk endpoints
export async function triggerRecalculate(): Promise<{ status: string; message: string }> {
  const { data } = await api.post("/risk/recalculate");
  return data;
}

export default api;

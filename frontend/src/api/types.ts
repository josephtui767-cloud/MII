/** API response types matching backend Pydantic schemas. */

export interface RiskFactor {
  factor: string;
  points: number;
  reason: string;
}

export interface TrustedBy {
  id: string;
  name: string;
  type: string;
  trust_type: string;
}

export interface CanAccess {
  id: string;
  name: string;
  resource_type: string;
  access_type: string;
  classification: string | null;
}

export interface Identity {
  id: string;
  name: string;
  arn: string | null;
  type: string;
  source: string;
  owner: string | null;
  account_id: string | null;
  last_used_at: string | null;
  risk_score: number;
  risk_factors: RiskFactor[];
  created_at: string;
}

export interface IdentityDetail extends Identity {
  is_resolved: boolean;
  trusted_by: TrustedBy[];
  can_access: CanAccess[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export type IdentityListResponse = PaginatedResponse<Identity>;

export interface IdentityFilters {
  page?: number;
  per_page?: number;
  type?: string;
  source?: string;
  min_risk_score?: number;
  has_admin?: boolean;
  has_production_access?: boolean;
  unused_days?: number;
  trusted_by_gitlab?: boolean;
  cross_account?: boolean;
  sort_by?: string;
  sort_order?: "asc" | "desc";
}

// Graph types
export interface TrustChainStep {
  identity_id: string;
  name: string;
  type: string;
  trust_type: string | null;
}

export interface TrustChain {
  path: TrustChainStep[];
  hop_count: number;
}

export interface TraverseResponse {
  start_identity: TrustChainStep;
  chains: TrustChain[];
  total_reachable_identities: number;
  total_reachable_resources: number;
}

export interface GraphStats {
  node_count: number;
  edge_count: number;
  connected_components: number;
}

// Risk types
export interface RiskScoreListItem {
  identity_id: string;
  identity_name: string;
  identity_type: string;
  source: string;
  score: number;
  factor_count: number;
}

// AI types
export interface ExplainRiskResponse {
  identity_id: string;
  identity_name: string;
  explanation: string;
  risk_score: number;
  risk_factors: RiskFactor[];
}

export interface ExplainPathResponse {
  source_name: string;
  target_name: string;
  explanation: string;
  path_exists: boolean;
  hop_count: number | null;
}

// Discovery types
export interface DiscoveryStatus {
  status: string;
  last_run_at: string | null;
  last_duration_seconds: number | null;
  identities_discovered: number;
  trust_relationships_discovered: number;
  resources_discovered: number;
  errors: string[];
}

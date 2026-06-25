/** Executive Dashboard — security posture overview for managers. */

import { useQuery } from "@tanstack/react-query";
import api from "../../api/client";

interface ExecutiveSummary {
  metrics: {
    total_identities: number;
    high_risk_identities: number;
    critical_risk_identities: number;
    unused_identities: number;
    trust_relationships: number;
    oidc_federations: number;
    average_risk_score: number;
    compliance_score: number;
  };
  risk_summary: {
    critical_findings: number;
    high_findings: number;
    total_findings: number;
  };
  top_actions: string[];
  health_status: string;
}

function MetricCard({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <p className="text-sm text-gray-500 font-medium">{label}</p>
      <p className={`text-3xl font-bold mt-1 ${color || "text-gray-900"}`}>{value}</p>
    </div>
  );
}

function HealthBadge({ status }: { status: string }) {
  const colors = {
    critical: "bg-red-100 text-red-800 border-red-300",
    warning: "bg-orange-100 text-orange-800 border-orange-300",
    healthy: "bg-green-100 text-green-800 border-green-300",
  };
  const labels = { critical: "Critical", warning: "Needs Attention", healthy: "Healthy" };
  const color = colors[status as keyof typeof colors] || colors.warning;
  const label = labels[status as keyof typeof labels] || "Unknown";

  return (
    <span className={`px-4 py-2 rounded-full text-sm font-semibold border ${color}`}>
      {label}
    </span>
  );
}

export function ExecutiveDashboard() {
  const { data, isLoading, isError } = useQuery<ExecutiveSummary>({
    queryKey: ["executive-summary"],
    queryFn: async () => {
      const { data } = await api.get("/security/executive-summary");
      return data;
    },
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="p-6">
        <p className="text-red-600">Failed to load executive summary.</p>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Security Posture Overview</h2>
          <p className="text-sm text-gray-500 mt-1">Machine Identity Intelligence — Executive Summary</p>
        </div>
        <HealthBadge status={data.health_status} />
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <MetricCard label="Total Identities" value={data.metrics.total_identities} />
        <MetricCard label="High Risk" value={data.metrics.high_risk_identities} color="text-red-600" />
        <MetricCard label="Unused Identities" value={data.metrics.unused_identities} color="text-orange-600" />
        <MetricCard label="Compliance Score" value={`${data.metrics.compliance_score}%`} color={data.metrics.compliance_score >= 70 ? "text-green-600" : "text-red-600"} />
      </div>

      {/* Second row */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <MetricCard label="Trust Relationships" value={data.metrics.trust_relationships} />
        <MetricCard label="OIDC Federations" value={data.metrics.oidc_federations} />
        <MetricCard label="Avg Risk Score" value={data.metrics.average_risk_score} color={data.metrics.average_risk_score > 30 ? "text-orange-600" : "text-green-600"} />
        <MetricCard label="Security Findings" value={data.risk_summary.total_findings} color={data.risk_summary.total_findings > 0 ? "text-red-600" : "text-green-600"} />
      </div>

      {/* Findings Summary */}
      <div className="grid grid-cols-2 gap-6 mb-8">
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold mb-4">Risk Distribution</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-red-500" />
                Critical Findings
              </span>
              <span className="text-2xl font-bold text-red-600">{data.risk_summary.critical_findings}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-orange-500" />
                High Findings
              </span>
              <span className="text-2xl font-bold text-orange-600">{data.risk_summary.high_findings}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-blue-500" />
                Total Findings
              </span>
              <span className="text-2xl font-bold text-gray-700">{data.risk_summary.total_findings}</span>
            </div>
          </div>
        </div>

        {/* Top Actions */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold mb-4">Top Priority Actions</h3>
          {data.top_actions.length === 0 ? (
            <p className="text-sm text-green-600">No critical actions required.</p>
          ) : (
            <ol className="space-y-3">
              {data.top_actions.map((action, idx) => (
                <li key={idx} className="flex items-start gap-3">
                  <span className="flex-shrink-0 w-6 h-6 bg-red-100 text-red-700 rounded-full flex items-center justify-center text-xs font-bold">
                    {idx + 1}
                  </span>
                  <span className="text-sm text-gray-700">{action}</span>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </div>
  );
}

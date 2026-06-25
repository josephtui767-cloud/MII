/** Security Findings Page — actionable security issues with remediation. */

import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import api from "../../api/client";
import { ReportDownloadButton } from "../../components/ReportDownloadButton";

interface Finding {
  id: string;
  title: string;
  severity: string;
  category: string;
  description: string;
  affected_identity_id: string;
  affected_identity_name: string;
  remediation: string;
  remediation_command: string;
  blast_radius: string;
}

interface FindingsResponse {
  total: number;
  summary: { critical: number; high: number; medium: number; low: number };
  findings: Finding[];
}

function SeverityBadge({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    critical: "bg-red-100 text-red-800 border-red-200",
    high: "bg-orange-100 text-orange-800 border-orange-200",
    medium: "bg-yellow-100 text-yellow-800 border-yellow-200",
    low: "bg-blue-100 text-blue-800 border-blue-200",
    info: "bg-gray-100 text-gray-800 border-gray-200",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold border uppercase ${colors[severity] || colors.info}`}>
      {severity}
    </span>
  );
}

export function FindingsPage() {
  const navigate = useNavigate();
  const { data, isLoading, isError } = useQuery<FindingsResponse>({
    queryKey: ["findings"],
    queryFn: async () => {
      const { data } = await api.get("/security/findings");
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
    return <div className="p-6 text-red-600">Failed to load findings.</div>;
  }

  return (
    <div className="p-6 max-w-6xl">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Security Findings</h2>
          <p className="text-sm text-gray-500 mt-1">
            {data.total} findings — {data.summary.critical} critical, {data.summary.high} high
          </p>
        </div>
        <ReportDownloadButton endpoint="/reports/findings" label="Export" />
      </div>

      {/* Summary bar */}
      <div className="flex gap-4 mb-6">
        <div className="flex items-center gap-2 px-3 py-1.5 bg-red-50 rounded-lg border border-red-200">
          <span className="w-2 h-2 rounded-full bg-red-500" />
          <span className="text-sm font-medium text-red-800">{data.summary.critical} Critical</span>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 bg-orange-50 rounded-lg border border-orange-200">
          <span className="w-2 h-2 rounded-full bg-orange-500" />
          <span className="text-sm font-medium text-orange-800">{data.summary.high} High</span>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 bg-yellow-50 rounded-lg border border-yellow-200">
          <span className="w-2 h-2 rounded-full bg-yellow-500" />
          <span className="text-sm font-medium text-yellow-800">{data.summary.medium} Medium</span>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-50 rounded-lg border border-blue-200">
          <span className="w-2 h-2 rounded-full bg-blue-500" />
          <span className="text-sm font-medium text-blue-800">{data.summary.low} Low</span>
        </div>
      </div>

      {/* Findings list */}
      {data.findings.length === 0 ? (
        <div className="p-8 text-center bg-green-50 rounded-lg border border-green-200">
          <p className="text-green-700 text-lg font-medium">No security findings detected.</p>
          <p className="text-green-600 text-sm mt-1">Your identity landscape looks clean.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {data.findings.map((finding) => (
            <div key={finding.id} className="bg-white rounded-lg border border-gray-200 p-5">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <SeverityBadge severity={finding.severity} />
                  <h3 className="font-semibold text-gray-900">{finding.title}</h3>
                </div>
                <span className="text-xs bg-gray-100 px-2 py-0.5 rounded text-gray-600">{finding.category}</span>
              </div>

              <p className="text-sm text-gray-700 mb-3">{finding.description}</p>

              {/* Affected identity */}
              <div className="mb-3">
                <span className="text-xs font-medium text-gray-500 uppercase">Affected Identity: </span>
                <button
                  onClick={() => navigate(`/identity/${finding.affected_identity_id}`)}
                  className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                >
                  {finding.affected_identity_name}
                </button>
              </div>

              {/* Blast radius */}
              {finding.blast_radius && (
                <div className="mb-3 p-2 bg-red-50 rounded border border-red-100">
                  <span className="text-xs font-medium text-red-700 uppercase">Blast Radius: </span>
                  <span className="text-sm text-red-800">{finding.blast_radius}</span>
                </div>
              )}

              {/* Remediation */}
              <div className="p-3 bg-green-50 rounded border border-green-100">
                <span className="text-xs font-medium text-green-700 uppercase block mb-1">Remediation</span>
                <p className="text-sm text-green-900">{finding.remediation}</p>
                {finding.remediation_command && (
                  <pre className="mt-2 p-2 bg-gray-900 text-green-300 rounded text-xs overflow-x-auto">
                    {finding.remediation_command}
                  </pre>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

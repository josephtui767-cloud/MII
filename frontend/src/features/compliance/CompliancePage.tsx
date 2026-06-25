/** Compliance Page — security policy checks with pass/fail status. */

import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import api from "../../api/client";
import { ReportDownloadButton } from "../../components/ReportDownloadButton";

interface ComplianceCheck {
  id: string;
  policy_name: string;
  description: string;
  status: string;
  severity: string;
  total_checked: number;
  passing: number;
  failing: number;
  failing_identities: { id: string; name: string; reason: string }[];
  recommendation: string;
}

interface ComplianceResponse {
  compliance_score: number;
  total_checks: number;
  passing: number;
  failing: number;
  warnings: number;
  checks: ComplianceCheck[];
}

function StatusIcon({ status }: { status: string }) {
  if (status === "pass") return <span className="text-green-500 text-xl">&#10003;</span>;
  if (status === "fail") return <span className="text-red-500 text-xl">&#10007;</span>;
  return <span className="text-yellow-500 text-xl">&#9888;</span>;
}

function ScoreRing({ score }: { score: number }) {
  const color = score >= 70 ? "text-green-600" : score >= 40 ? "text-orange-600" : "text-red-600";
  const bgColor = score >= 70 ? "border-green-200 bg-green-50" : score >= 40 ? "border-orange-200 bg-orange-50" : "border-red-200 bg-red-50";

  return (
    <div className={`w-32 h-32 rounded-full border-4 ${bgColor} flex items-center justify-center`}>
      <div className="text-center">
        <p className={`text-3xl font-bold ${color}`}>{score}%</p>
        <p className="text-xs text-gray-500">Compliance</p>
      </div>
    </div>
  );
}

export function CompliancePage() {
  const navigate = useNavigate();
  const { data, isLoading, isError } = useQuery<ComplianceResponse>({
    queryKey: ["compliance"],
    queryFn: async () => {
      const { data } = await api.get("/security/compliance");
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
    return <div className="p-6 text-red-600">Failed to load compliance data.</div>;
  }

  return (
    <div className="p-6 max-w-6xl">
      <div className="flex items-start justify-between mb-8">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Compliance Dashboard</h2>
          <p className="text-sm text-gray-500 mt-1">
            {data.total_checks} policy checks — {data.passing} passing, {data.failing} failing
          </p>
        </div>
        <div className="flex items-center gap-4">
          <ReportDownloadButton endpoint="/reports/compliance" label="Export" />
          <ScoreRing score={data.compliance_score} />
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-center">
          <p className="text-3xl font-bold text-green-700">{data.passing}</p>
          <p className="text-sm text-green-600">Passing</p>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-center">
          <p className="text-3xl font-bold text-red-700">{data.failing}</p>
          <p className="text-sm text-red-600">Failing</p>
        </div>
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-center">
          <p className="text-3xl font-bold text-yellow-700">{data.warnings}</p>
          <p className="text-sm text-yellow-600">Warnings</p>
        </div>
      </div>

      {/* Policy checks */}
      <div className="space-y-4">
        {data.checks.map((check) => (
          <div key={check.id} className="bg-white rounded-lg border border-gray-200 p-5">
            <div className="flex items-center gap-3 mb-2">
              <StatusIcon status={check.status} />
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-gray-900">{check.policy_name}</h3>
                  <span className="text-xs text-gray-500">
                    {check.passing}/{check.total_checked} passing
                  </span>
                </div>
                <p className="text-sm text-gray-600">{check.description}</p>
              </div>
            </div>

            {/* Progress bar */}
            <div className="w-full bg-gray-200 rounded-full h-2 mb-3">
              <div
                className={`h-2 rounded-full ${check.status === "pass" ? "bg-green-500" : check.status === "warning" ? "bg-yellow-500" : "bg-red-500"}`}
                style={{ width: `${check.total_checked > 0 ? (check.passing / check.total_checked) * 100 : 100}%` }}
              />
            </div>

            {/* Failing identities */}
            {check.failing_identities.length > 0 && (
              <div className="mt-3">
                <p className="text-xs font-medium text-red-600 uppercase mb-2">
                  Failing ({check.failing}):
                </p>
                <div className="space-y-1">
                  {check.failing_identities.map((identity, idx) => (
                    <div
                      key={idx}
                      onClick={check.severity === "critical" || check.severity === "high" ? () => navigate(`/identity/${identity.id}`) : undefined}
                      className={`flex items-center justify-between text-sm bg-red-50 px-3 py-1.5 rounded ${
                        check.severity === "critical" || check.severity === "high" ? "cursor-pointer hover:bg-red-100 transition-colors" : ""
                      }`}
                    >
                      <span className={`font-medium ${check.severity === "critical" || check.severity === "high" ? "text-blue-700" : "text-gray-800"}`}>
                        {identity.name}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-red-600">{identity.reason}</span>
                        {(check.severity === "critical" || check.severity === "high") && (
                          <span className="text-xs text-blue-600">Fix &rarr;</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recommendation */}
            {check.status !== "pass" && (
              <div className="mt-3 p-2 bg-blue-50 rounded border border-blue-100">
                <span className="text-xs font-medium text-blue-700">Recommendation: </span>
                <span className="text-sm text-blue-900">{check.recommendation}</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

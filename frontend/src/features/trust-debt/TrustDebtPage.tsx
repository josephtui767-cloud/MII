/** Trust Debt Page — shows accumulated trust debt with grade and breakdown. */

import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import api from "../../api/client";
import { ReportDownloadButton } from "../../components/ReportDownloadButton";

interface DebtItem {
  category: string;
  description: string;
  points: number;
  affected_identity_id: string;
  affected_identity_name: string;
  recommendation: string;
  age_days: number;
}

interface TrustDebtResponse {
  total_debt_score: number;
  debt_percentage: number;
  debt_grade: string;
  trend: string;
  category_breakdown: Record<string, number>;
  top_contributors: { id: string; name: string; total_points: number; issues: string[] }[];
  debt_items: DebtItem[];
  total_items: number;
  error?: string;
}

function GradeRing({ grade, score }: { grade: string; score: number }) {
  const gradeColors: Record<string, string> = {
    A: "text-green-600 border-green-200 bg-green-50",
    B: "text-blue-600 border-blue-200 bg-blue-50",
    C: "text-yellow-600 border-yellow-200 bg-yellow-50",
    D: "text-orange-600 border-orange-200 bg-orange-50",
    F: "text-red-600 border-red-200 bg-red-50",
  };
  const color = gradeColors[grade] || gradeColors.C;

  return (
    <div className={`w-36 h-36 rounded-full border-4 ${color} flex flex-col items-center justify-center`}>
      <p className="text-4xl font-bold">{grade}</p>
      <p className="text-xs opacity-70">{score} pts debt</p>
    </div>
  );
}

export function TrustDebtPage() {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery<TrustDebtResponse>({
    queryKey: ["trust-debt"],
    queryFn: async () => {
      const { data } = await api.get("/security/trust-debt");
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

  if (!data || data.error) {
    return <div className="p-6 text-red-600">Failed to load trust debt: {data?.error}</div>;
  }

  const categoryColors: Record<string, string> = {
    "Unused OIDC Federation": "bg-purple-100 text-purple-800",
    "Admin on CI/CD Role": "bg-red-100 text-red-800",
    "No Branch Restriction": "bg-orange-100 text-orange-800",
    "Unused Trust Relationship": "bg-yellow-100 text-yellow-800",
    "Stale Trusted Identity": "bg-blue-100 text-blue-800",
    "Wildcard Resource Access": "bg-gray-100 text-gray-800",
  };

  return (
    <div className="p-6 max-w-6xl">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Trust Debt</h2>
          <p className="text-sm text-gray-500 mt-1">
            Accumulated unnecessary or overprivileged trust relationships
          </p>
          <p className="text-xs text-gray-400 mt-2">
            Like technical debt, trust debt grows over time as permissions and trust relationships are granted
            but never reviewed or removed. Lower is better.
          </p>
        </div>
        <div className="flex items-center gap-4">
          <ReportDownloadButton endpoint="/reports/trust-debt" label="Export" />
          <GradeRing grade={data.debt_grade} score={data.total_debt_score} />
        </div>
      </div>

      {/* Category Breakdown */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
        <h3 className="text-lg font-semibold mb-4">Debt by Category</h3>
        {Object.entries(data.category_breakdown).length === 0 ? (
          <p className="text-green-600">No trust debt detected. Excellent!</p>
        ) : (
          <div className="space-y-3">
            {Object.entries(data.category_breakdown)
              .sort(([, a], [, b]) => b - a)
              .map(([category, points]) => (
                <div key={category} className="flex items-center gap-3">
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className={`text-sm font-medium px-2 py-0.5 rounded ${categoryColors[category] || "bg-gray-100 text-gray-700"}`}>
                        {category}
                      </span>
                      <span className="text-sm font-bold text-gray-700">{points} pts</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-red-400 h-2 rounded-full"
                        style={{ width: `${Math.min((points / data.total_debt_score) * 100, 100)}%` }}
                      />
                    </div>
                  </div>
                </div>
              ))}
          </div>
        )}
      </div>

      {/* Top Contributors */}
      {data.top_contributors.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
          <h3 className="text-lg font-semibold mb-4">Top Debt Contributors</h3>
          <div className="space-y-3">
            {data.top_contributors.map((contributor, idx) => (
              <div
                key={contributor.id}
                onClick={() => navigate(`/identity/${contributor.id}`)}
                className="flex items-center gap-3 p-3 bg-gray-50 rounded cursor-pointer hover:bg-gray-100 transition-colors"
              >
                <span className="w-8 h-8 bg-red-100 text-red-700 rounded-full flex items-center justify-center text-sm font-bold">
                  {idx + 1}
                </span>
                <div className="flex-1">
                  <p className="font-medium text-blue-700 hover:text-blue-900">{contributor.name}</p>
                  <p className="text-xs text-gray-500">{contributor.issues.join(", ")}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-lg font-bold text-red-600">{contributor.total_points} pts</span>
                  <span className="text-xs text-blue-600">Fix &rarr;</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Debt Items */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold mb-4">All Debt Items ({data.total_items})</h3>
        <div className="space-y-3">
          {data.debt_items.map((item, idx) => (
            <div key={idx} className="border-l-4 border-red-300 pl-4 py-2">
              <div className="flex items-center justify-between">
                <span className={`text-xs font-medium px-2 py-0.5 rounded ${categoryColors[item.category] || "bg-gray-100"}`}>
                  {item.category}
                </span>
                <span className="text-sm font-bold text-red-600">+{item.points} pts</span>
              </div>
              <p className="text-sm text-gray-700 mt-1">{item.description}</p>
              <p className="text-xs text-gray-500 mt-1">
                <span className="font-medium">Fix:</span> {item.recommendation}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

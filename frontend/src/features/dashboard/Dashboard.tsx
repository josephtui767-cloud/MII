/** Identity Dashboard — paginated list with filters, sorted by risk score. */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { fetchIdentities, triggerDiscovery } from "../../api/client";
import type { IdentityFilters } from "../../api/types";
import { RiskBadge } from "../../components/RiskBadge";
import { Pagination } from "../../components/Pagination";
import { FilterPanel } from "../../components/FilterPanel";
import { ReportDownloadButton } from "../../components/ReportDownloadButton";

export function Dashboard() {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<IdentityFilters>({
    page: 1,
    per_page: 25,
    sort_by: "risk_score",
    sort_order: "desc",
  });

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["identities", filters],
    queryFn: () => fetchIdentities(filters),
  });

  const handleRunDiscovery = async () => {
    try {
      await triggerDiscovery();
      alert("Discovery scan started. Refresh in a few minutes to see results.");
    } catch {
      alert("Failed to start discovery scan.");
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Machine Identities</h2>
          <p className="text-sm text-gray-500 mt-1">
            {data?.items ? `${data.total} identities discovered` : "Loading..."}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <ReportDownloadButton endpoint="/reports/identities" label="Export" />
          <button
            onClick={handleRunDiscovery}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded hover:bg-blue-700"
          >
            Run Discovery
          </button>
        </div>
      </div>

      <div className="flex gap-6">
        {/* Filters sidebar */}
        <div className="w-64 flex-shrink-0">
          <FilterPanel filters={filters} onChange={setFilters} />
        </div>

        {/* Main content */}
        <div className="flex-1 min-w-0">
          {isError && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              Failed to load identities: {(error as Error)?.message || "Connection error"}
            </div>
          )}

          {!isError && !isLoading && data?.items?.length === 0 && (
            <div className="p-8 text-center bg-white rounded-lg border border-gray-200">
              <p className="text-gray-500 text-lg">No identities discovered yet.</p>
              <p className="text-gray-400 text-sm mt-2">
                Run a discovery scan to find machine identities in your environment.
              </p>
            </div>
          )}

          {data && data.items && data.items.length > 0 && (
            <>
              <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Name</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Type</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Source</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Account</th>
                      <th className="text-center px-4 py-3 font-medium text-gray-600">Risk</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Last Used</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {data.items.map((identity) => (
                      <tr
                        key={identity.id}
                        onClick={() => navigate(`/identity/${identity.id}`)}
                        className="hover:bg-blue-50 cursor-pointer transition-colors"
                      >
                        <td className="px-4 py-3 font-medium text-gray-900 truncate max-w-[250px]">
                          {identity.name}
                        </td>
                        <td className="px-4 py-3 text-gray-600">
                          <span className="text-xs bg-gray-100 px-2 py-0.5 rounded">
                            {identity.type.replace(/_/g, " ")}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-600">{identity.source}</td>
                        <td className="px-4 py-3 text-gray-500 text-xs font-mono">
                          {identity.account_id || "—"}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <RiskBadge score={identity.risk_score} />
                        </td>
                        <td className="px-4 py-3 text-gray-500 text-xs">
                          {identity.last_used_at
                            ? new Date(identity.last_used_at).toLocaleDateString()
                            : "Never"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="mt-4 flex justify-center">
                <Pagination
                  page={data.page}
                  pages={data.pages}
                  onPageChange={(p) => setFilters((f) => ({ ...f, page: p }))}
                />
              </div>
            </>
          )}

          {isLoading && (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

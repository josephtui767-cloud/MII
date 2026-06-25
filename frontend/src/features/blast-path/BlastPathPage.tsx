/** Blast Path Simulation — interactive attack path visualization. */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import api from "../../api/client";
import { fetchIdentities } from "../../api/client";
import { ReportDownloadButton } from "../../components/ReportDownloadButton";

interface AttackStep {
  step_number: number;
  action: string;
  from_identity: { id: string; name: string };
  to_identity: { id: string; name: string };
  trust_type: string;
  risk_level: string;
  description: string;
}

interface BlastPathResponse {
  start_identity: { id: string; name: string; type: string };
  scenario: string;
  severity: string;
  narrative: string;
  attack_steps: AttackStep[];
  compromised_identities: { id: string; name: string; type: string; risk_score: number; hop_count: number }[];
  compromised_resources: { id: string; name: string; resource_type: string; access_type: string; classification: string; reached_via: string }[];
  total_blast_radius: number;
  summary: {
    identities_compromised: number;
    resources_accessible: number;
    production_resources: number;
    admin_access_count: number;
    max_hop_count: number;
  };
  error?: string;
}

function SeverityBar({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    critical: "bg-red-500",
    high: "bg-orange-500",
    medium: "bg-yellow-500",
    low: "bg-green-500",
  };
  return (
    <div className={`px-4 py-2 rounded-lg text-white text-sm font-semibold ${colors[severity] || colors.medium}`}>
      Blast Severity: {severity.toUpperCase()}
    </div>
  );
}

function StepCard({ step, isLast }: { step: AttackStep; isLast: boolean }) {
  const riskColors: Record<string, string> = {
    critical: "border-red-400 bg-red-50",
    high: "border-orange-400 bg-orange-50",
    medium: "border-yellow-400 bg-yellow-50",
    low: "border-green-400 bg-green-50",
  };

  return (
    <div className="flex items-start gap-3">
      <div className="flex flex-col items-center">
        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold border-2 ${riskColors[step.risk_level] || ""}`}>
          {step.step_number}
        </div>
        {!isLast && <div className="w-0.5 h-12 bg-gray-300 mt-1" />}
      </div>
      <div className={`flex-1 p-3 rounded-lg border ${riskColors[step.risk_level] || "border-gray-200"}`}>
        <div className="flex items-center justify-between mb-1">
          <span className="text-sm font-semibold text-gray-900">{step.action}</span>
          <span className="text-xs bg-gray-200 px-2 py-0.5 rounded">{step.trust_type.replace(/_/g, " ")}</span>
        </div>
        <p className="text-sm text-gray-700">{step.description}</p>
      </div>
    </div>
  );
}

export function BlastPathPage() {
  const navigate = useNavigate();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [simType, setSimType] = useState<"gitlab" | "custom">("gitlab");

  const { data: identities } = useQuery({
    queryKey: ["identities-for-blast", { per_page: 50 }],
    queryFn: () => fetchIdentities({ per_page: 50, sort_by: "risk_score", sort_order: "desc" }),
  });

  const endpoint = simType === "gitlab"
    ? "/security/blast-path-gitlab"
    : `/security/blast-path/${selectedId}`;

  const { data, isLoading } = useQuery<BlastPathResponse>({
    queryKey: ["blast-path", simType, selectedId],
    queryFn: async () => {
      const { data } = await api.get(endpoint);
      return data;
    },
    enabled: simType === "gitlab" || !!selectedId,
  });

  return (
    <div className="p-6 max-w-6xl">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Blast Path Simulation</h2>
          <p className="text-sm text-gray-500 mt-1">
            Simulate what happens when an identity is compromised. Trace the attack path through trust chains.
          </p>
        </div>
        {data && !data.error && selectedId && (
          <ReportDownloadButton endpoint={`/reports/blast-path/${selectedId}`} label="Export" />
        )}
      </div>

      {/* Controls */}
      <div className="flex items-center gap-4 mb-6 p-4 bg-white rounded-lg border border-gray-200">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setSimType("gitlab")}
            className={`px-3 py-1.5 rounded text-sm font-medium ${simType === "gitlab" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-700"}`}
          >
            GitLab CI/CD Compromise
          </button>
          <button
            onClick={() => setSimType("custom")}
            className={`px-3 py-1.5 rounded text-sm font-medium ${simType === "custom" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-700"}`}
          >
            Custom Identity
          </button>
        </div>

        {simType === "custom" && identities?.items && (
          <select
            value={selectedId || ""}
            onChange={(e) => setSelectedId(e.target.value)}
            className="flex-1 text-sm border border-gray-300 rounded px-3 py-1.5"
          >
            <option value="">Select an identity to simulate compromise...</option>
            {identities.items.map((i) => (
              <option key={i.id} value={i.id}>
                {i.name} (risk: {i.risk_score})
              </option>
            ))}
          </select>
        )}
      </div>

      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-red-600" />
        </div>
      )}

      {data?.error && (
        <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-800">
          {data.error}
        </div>
      )}

      {data && !data.error && (
        <>
          {/* Scenario */}
          <div className="bg-gray-900 text-gray-100 rounded-lg p-6 mb-6">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-semibold">Attack Scenario</h3>
              <SeverityBar severity={data.severity} />
            </div>
            <p className="text-sm text-gray-300 leading-relaxed">{data.scenario}</p>
            <div className="mt-3 text-xs text-gray-400">
              Starting from: <span className="text-white font-medium">{data.start_identity.name}</span> ({data.start_identity.type.replace(/_/g, " ")})
            </div>
          </div>

          {/* Summary Cards */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-lg border p-4 text-center">
              <p className="text-3xl font-bold text-red-600">{data.summary.identities_compromised}</p>
              <p className="text-xs text-gray-500">Identities Compromised</p>
            </div>
            <div className="bg-white rounded-lg border p-4 text-center">
              <p className="text-3xl font-bold text-orange-600">{data.summary.resources_accessible}</p>
              <p className="text-xs text-gray-500">Resources Accessible</p>
            </div>
            <div className="bg-white rounded-lg border p-4 text-center">
              <p className="text-3xl font-bold text-purple-600">{data.summary.production_resources}</p>
              <p className="text-xs text-gray-500">Production Resources</p>
            </div>
            <div className="bg-white rounded-lg border p-4 text-center">
              <p className="text-3xl font-bold text-gray-700">{data.summary.max_hop_count}</p>
              <p className="text-xs text-gray-500">Max Hops</p>
            </div>
          </div>

          {/* Attack Steps */}
          {data.attack_steps.length > 0 && (
            <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
              <h3 className="text-lg font-semibold mb-4">Attack Chain</h3>
              <div className="space-y-2">
                {data.attack_steps.map((step, idx) => (
                  <StepCard key={idx} step={step} isLast={idx === data.attack_steps.length - 1} />
                ))}
              </div>
            </div>
          )}

          {/* Compromised Resources */}
          {data.compromised_resources.length > 0 && (
            <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
              <h3 className="text-lg font-semibold mb-4">
                Compromised Resources ({data.compromised_resources.length})
              </h3>
              <div className="space-y-2">
                {data.compromised_resources.map((resource, idx) => (
                  <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded">
                    <div>
                      <p className="font-medium text-sm">{resource.name}</p>
                      <p className="text-xs text-gray-500">{resource.resource_type.replace(/_/g, " ")} — via {resource.reached_via}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {resource.classification === "production" && (
                        <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded">PROD</span>
                      )}
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        resource.access_type === "Admin" ? "bg-red-100 text-red-700" :
                        resource.access_type === "Write" ? "bg-orange-100 text-orange-700" :
                        "bg-green-100 text-green-700"
                      }`}>
                        {resource.access_type}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Compromised Identities */}
          {data.compromised_identities.length > 0 && (
            <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
              <h3 className="text-lg font-semibold mb-4">
                Compromised Identities ({data.compromised_identities.length})
              </h3>
              <div className="space-y-2">
                {data.compromised_identities.map((identity, idx) => (
                  <div
                    key={idx}
                    onClick={() => navigate(`/identity/${identity.id}`)}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded cursor-pointer hover:bg-gray-100 transition-colors"
                  >
                    <div>
                      <p className="font-medium text-sm text-blue-700 hover:text-blue-900">{identity.name}</p>
                      <p className="text-xs text-gray-500">{identity.type.replace(/_/g, " ")} — {identity.hop_count} hop(s) away</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs bg-gray-200 px-2 py-0.5 rounded">Risk: {identity.risk_score}</span>
                      <span className="text-xs text-blue-600">View &rarr;</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Narrative */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-semibold mb-3">Impact Analysis</h3>
            <pre className="text-sm text-gray-700 whitespace-pre-wrap font-mono bg-gray-50 p-4 rounded">
              {data.narrative}
            </pre>
          </div>
        </>
      )}
    </div>
  );
}

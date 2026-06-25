/** Identity Detail View — full info with trusted_by, can_access, risk breakdown, AI explanation. */

import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchIdentityDetail, explainRisk } from "../../api/client";
import { RiskBadge } from "../../components/RiskBadge";

export function IdentityDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [explanation, setExplanation] = useState<string | null>(null);
  const [remediationPlan, setRemediationPlan] = useState<string | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [generating, setGenerating] = useState(false);

  const { data: identity, isLoading, isError } = useQuery({
    queryKey: ["identity", id],
    queryFn: () => fetchIdentityDetail(id!),
    enabled: !!id,
  });

  const handleExplainRisk = async () => {
    if (!id) return;
    setExplaining(true);
    try {
      const result = await explainRisk(id);
      setExplanation(result.explanation);
    } catch {
      setExplanation("Failed to generate explanation.");
    } finally {
      setExplaining(false);
    }
  };

  const handleRemediationPlan = async () => {
    if (!id) return;
    setGenerating(true);
    try {
      const { data } = await (await import("../../api/client")).default.post("/ai/remediation-plan", { identity_id: id });
      setRemediationPlan(data.plan);
    } catch {
      setRemediationPlan("Failed to generate remediation plan.");
    } finally {
      setGenerating(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (isError || !identity) {
    return (
      <div className="p-6">
        <p className="text-red-600">Identity not found.</p>
        <button onClick={() => navigate("/identities")} className="mt-2 text-blue-600 text-sm">
          Back to identities
        </button>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-5xl">
      {/* Header */}
      <button onClick={() => navigate("/identities")} className="text-sm text-blue-600 hover:text-blue-800 mb-4">
        &larr; Back to identities
      </button>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">{identity.name}</h2>
          <p className="text-sm text-gray-500 mt-1 font-mono">{identity.arn || "No ARN"}</p>
          <div className="flex items-center gap-3 mt-2 text-sm text-gray-600">
            <span className="bg-gray-100 px-2 py-0.5 rounded">{identity.type.replace(/_/g, " ")}</span>
            <span>{identity.source}</span>
            {identity.account_id && <span className="font-mono text-xs">{identity.account_id}</span>}
          </div>
        </div>
        <RiskBadge score={identity.risk_score} size="lg" />
      </div>

      {/* Metadata */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white p-4 rounded-lg border">
          <p className="text-xs text-gray-500 uppercase">Owner</p>
          <p className="font-medium">{identity.owner || "Unknown"}</p>
        </div>
        <div className="bg-white p-4 rounded-lg border">
          <p className="text-xs text-gray-500 uppercase">Last Used</p>
          <p className="font-medium">
            {identity.last_used_at ? new Date(identity.last_used_at).toLocaleDateString() : "Never"}
          </p>
        </div>
        <div className="bg-white p-4 rounded-lg border">
          <p className="text-xs text-gray-500 uppercase">Created</p>
          <p className="font-medium">{new Date(identity.created_at).toLocaleDateString()}</p>
        </div>
      </div>

      {/* Risk Factors */}
      <section className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-semibold">Risk Factors</h3>
          {identity.risk_score > 0 && (
            <div className="flex gap-2">
              <button
                onClick={handleExplainRisk}
                disabled={explaining}
                className="px-3 py-1.5 bg-purple-600 text-white text-sm rounded hover:bg-purple-700 disabled:opacity-50"
              >
                {explaining ? "Generating..." : "Explain Risk"}
              </button>
              <button
                onClick={handleRemediationPlan}
                disabled={generating}
                className="px-3 py-1.5 bg-green-600 text-white text-sm rounded hover:bg-green-700 disabled:opacity-50"
              >
                {generating ? "Generating..." : "AI Remediation Plan"}
              </button>
            </div>
          )}
        </div>

        {identity.risk_factors.length === 0 ? (
          <p className="text-sm text-gray-500">No risk factors identified.</p>
        ) : (
          <div className="bg-white rounded-lg border divide-y">
            {identity.risk_factors.map((factor, idx) => (
              <div key={idx} className="flex items-center justify-between px-4 py-3">
                <div>
                  <p className="font-medium text-sm">{factor.factor.replace(/_/g, " ")}</p>
                  <p className="text-xs text-gray-500">{factor.reason}</p>
                </div>
                <span className="text-sm font-bold text-red-600">+{factor.points}</span>
              </div>
            ))}
          </div>
        )}

        {/* AI Explanation */}
        {explanation && (
          <div className="mt-4 p-4 bg-purple-50 border border-purple-200 rounded-lg">
            <h4 className="text-sm font-semibold text-purple-800 mb-2">AI Explanation</h4>
            <p className="text-sm text-gray-700 whitespace-pre-wrap">{explanation}</p>
          </div>
        )}

        {/* AI Remediation Plan */}
        {remediationPlan && (
          <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
            <h4 className="text-sm font-semibold text-green-800 mb-2">AI Remediation Plan</h4>
            <pre className="text-sm text-gray-700 whitespace-pre-wrap font-mono bg-white p-3 rounded border border-green-100 overflow-x-auto">
              {remediationPlan}
            </pre>
          </div>
        )}
      </section>

      {/* Trusted By */}
      <section className="mb-6">
        <h3 className="text-lg font-semibold mb-3">
          Trusted By ({identity.trusted_by.length})
        </h3>
        {identity.trusted_by.length === 0 ? (
          <p className="text-sm text-gray-500">No incoming trust relationships.</p>
        ) : (
          <div className="bg-white rounded-lg border divide-y">
            {identity.trusted_by.map((trust) => (
              <div key={trust.id} className="flex items-center justify-between px-4 py-3">
                <div>
                  <p
                    className="font-medium text-sm text-blue-600 hover:text-blue-800 cursor-pointer"
                    onClick={() => navigate(`/identity/${trust.id}`)}
                  >
                    {trust.name}
                  </p>
                  <p className="text-xs text-gray-500">{trust.type.replace(/_/g, " ")}</p>
                </div>
                <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">
                  {trust.trust_type.replace(/_/g, " ")}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Can Access */}
      <section className="mb-6">
        <h3 className="text-lg font-semibold mb-3">
          Can Access ({identity.can_access.length})
        </h3>
        {identity.can_access.length === 0 ? (
          <p className="text-sm text-gray-500">No resource access mapped.</p>
        ) : (
          <div className="bg-white rounded-lg border divide-y">
            {identity.can_access.map((access) => (
              <div key={`${access.id}-${access.access_type}`} className="flex items-center justify-between px-4 py-3">
                <div>
                  <p className="font-medium text-sm">{access.name}</p>
                  <p className="text-xs text-gray-500">{access.resource_type.replace(/_/g, " ")}</p>
                </div>
                <div className="flex items-center gap-2">
                  {access.classification === "production" && (
                    <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded">PROD</span>
                  )}
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    access.access_type === "Admin"
                      ? "bg-red-100 text-red-700"
                      : access.access_type === "Write"
                        ? "bg-orange-100 text-orange-700"
                        : "bg-green-100 text-green-700"
                  }`}>
                    {access.access_type}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

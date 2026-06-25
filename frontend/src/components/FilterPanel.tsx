/** Filter sidebar for identity list. */

import type { IdentityFilters } from "../api/types";

interface FilterPanelProps {
  filters: IdentityFilters;
  onChange: (filters: IdentityFilters) => void;
}

export function FilterPanel({ filters, onChange }: FilterPanelProps) {
  const update = (partial: Partial<IdentityFilters>) => {
    onChange({ ...filters, ...partial, page: 1 });
  };

  return (
    <div className="space-y-4 p-4 bg-white rounded-lg border border-gray-200">
      <h3 className="font-semibold text-sm text-gray-700 uppercase tracking-wide">Filters</h3>

      {/* Type filter */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Type</label>
        <select
          value={filters.type || ""}
          onChange={(e) => update({ type: e.target.value || undefined })}
          className="w-full text-sm border border-gray-300 rounded px-2 py-1.5"
        >
          <option value="">All Types</option>
          <option value="AWS_IAM_Role">AWS IAM Role</option>
          <option value="GitLab_Project_Access_Token">GitLab Project Token</option>
          <option value="GitLab_Group_Access_Token">GitLab Group Token</option>
          <option value="GitLab_Runner">GitLab Runner</option>
        </select>
      </div>

      {/* Source filter */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Source</label>
        <select
          value={filters.source || ""}
          onChange={(e) => update({ source: e.target.value || undefined })}
          className="w-full text-sm border border-gray-300 rounded px-2 py-1.5"
        >
          <option value="">All Sources</option>
          <option value="AWS">AWS</option>
          <option value="GitLab">GitLab</option>
        </select>
      </div>

      {/* Min risk score */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">
          Min Risk Score: {filters.min_risk_score ?? 0}
        </label>
        <input
          type="range"
          min={0}
          max={100}
          value={filters.min_risk_score ?? 0}
          onChange={(e) => {
            const val = Number(e.target.value);
            update({ min_risk_score: val > 0 ? val : undefined });
          }}
          className="w-full"
        />
      </div>

      {/* Boolean filters */}
      <div className="space-y-2">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={filters.has_admin ?? false}
            onChange={(e) => update({ has_admin: e.target.checked || undefined })}
            className="rounded"
          />
          Admin privileges
        </label>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={filters.has_production_access ?? false}
            onChange={(e) => update({ has_production_access: e.target.checked || undefined })}
            className="rounded"
          />
          Production access
        </label>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={filters.unused_days !== undefined}
            onChange={(e) => update({ unused_days: e.target.checked ? 90 : undefined })}
            className="rounded"
          />
          Unused 90+ days
        </label>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={filters.trusted_by_gitlab ?? false}
            onChange={(e) => update({ trusted_by_gitlab: e.target.checked || undefined })}
            className="rounded"
          />
          Trusted by GitLab CI/CD
        </label>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={filters.cross_account ?? false}
            onChange={(e) => update({ cross_account: e.target.checked || undefined })}
            className="rounded"
          />
          Cross-account access
        </label>
      </div>

      {/* Reset */}
      <button
        onClick={() => onChange({ page: 1, per_page: 25, sort_by: "risk_score", sort_order: "desc" })}
        className="w-full text-sm text-blue-600 hover:text-blue-800 py-1"
      >
        Reset filters
      </button>
    </div>
  );
}

/** Reusable Report Download Button — dropdown with PDF, Markdown, Excel format options. */

import { useState, useRef, useEffect } from "react";
import api from "../api/client";

type ReportFormat = "pdf" | "markdown" | "excel";

interface ReportDownloadButtonProps {
  /** API endpoint path (e.g., "/reports/findings") */
  endpoint: string;
  /** Optional label override */
  label?: string;
}

const FORMAT_OPTIONS: { value: ReportFormat; label: string; icon: string; ext: string }[] = [
  { value: "pdf", label: "PDF Report", icon: "📄", ext: ".pdf" },
  { value: "markdown", label: "Markdown", icon: "📝", ext: ".md" },
  { value: "excel", label: "Excel", icon: "📊", ext: ".xlsx" },
];

export function ReportDownloadButton({ endpoint, label = "Export Report" }: ReportDownloadButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isDownloading, setIsDownloading] = useState<ReportFormat | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleDownload = async (format: ReportFormat) => {
    setIsDownloading(format);
    setIsOpen(false);

    try {
      const response = await api.get(endpoint, {
        params: { format },
        responseType: "blob",
      });

      // Extract filename from Content-Disposition header or generate one
      const contentDisposition = response.headers["content-disposition"];
      let filename = `report.${format === "excel" ? "xlsx" : format === "markdown" ? "md" : "pdf"}`;
      if (contentDisposition) {
        const match = contentDisposition.match(/filename="?([^";\n]+)"?/);
        if (match) filename = match[1];
      }

      // Create download link
      const blob = new Blob([response.data]);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Download failed:", error);
      alert("Failed to generate report. Please try again.");
    } finally {
      setIsDownloading(null);
    }
  };

  return (
    <div className="relative inline-block" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={isDownloading !== null}
        className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 hover:border-gray-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
      >
        {isDownloading ? (
          <>
            <span className="animate-spin h-4 w-4 border-2 border-gray-300 border-t-blue-600 rounded-full" />
            <span>Generating...</span>
          </>
        ) : (
          <>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span>{label}</span>
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-1 w-44 bg-white border border-gray-200 rounded-lg shadow-lg z-50 py-1">
          {FORMAT_OPTIONS.map((option) => (
            <button
              key={option.value}
              onClick={() => handleDownload(option.value)}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
            >
              <span>{option.icon}</span>
              <span>{option.label}</span>
              <span className="ml-auto text-xs text-gray-400">{option.ext}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

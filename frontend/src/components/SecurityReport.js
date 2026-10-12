import { AlertTriangle, ShieldAlert, ShieldCheck, ShieldQuestion } from "lucide-react";

const severityColors = {
  high: "text-rose-400",
  medium: "text-amber-400",
  low: "text-sky-400",
  info: "text-zinc-400",
};

export default function SecurityReport({ report }) {
  if (!report) return null;
  const summary = report.summary || {};
  const failed = report.outcome === "fail";
  return (
    <section className="space-y-4 border-t border-[#282828] pt-4" data-testid="passive-security-results" aria-label="Passive security findings">
      <div className="flex items-start gap-2 rounded-md border border-[#333] bg-[#111111] p-3">
        {failed ? (
          <ShieldAlert className="w-5 h-5 shrink-0 text-rose-400" />
        ) : (report.findings || []).length ? (
          <AlertTriangle className="w-5 h-5 shrink-0 text-amber-400" />
        ) : (
          <ShieldQuestion className="w-5 h-5 shrink-0 text-blue-400" />
        )}
        <div>
          <p className="text-sm font-medium">
            {failed ? "Audit could not complete" : "Observed HTTPS configuration signals"}
          </p>
          <p className="text-xs text-zinc-400 mt-1 leading-5">
            {failed
              ? "No security conclusions can be drawn from a failed scan."
              : "Findings are limited to one HTTPS HEAD response and a verified TLS connection. Missing headers are configuration signals, not proof of an exploit."}
          </p>
        </div>
      </div>

      {!failed && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {["high", "medium", "low", "info"].map((level) => (
              <div key={level} className="border border-[#292929] rounded-md p-3 bg-[#0B0B0B]">
                <p className="text-xs text-zinc-500 capitalize">{level === "info" ? "Informational" : level}</p>
                <p className={"font-mono text-xl mt-1 " + severityColors[level]}>{summary[level] ?? 0}</p>
              </div>
            ))}
          </div>

          <div className="border border-[#292929] rounded-md p-3">
            <div className="flex items-center gap-2 mb-2">
              <ShieldCheck className="w-4 h-4 text-zinc-400" />
              <p className="text-xs font-semibold">TLS observations</p>
            </div>
            <p className="text-xs text-zinc-400">Certificate verified: {report.tls?.verified ? "Yes" : "Not verified"}</p>
            <p className="text-xs text-zinc-400 mt-1">Negotiated version: {report.tls?.version || "Not observed"}</p>
            <p className="text-xs text-zinc-400 mt-1">
              Certificate expiry: {Number.isInteger(report.tls?.days_until_expiry) ? report.tls.days_until_expiry + " days remaining" : "Not observed"}
            </p>
          </div>
        </>
      )}

      <div>
        <p className="text-xs font-semibold mb-2">Evidence-backed findings</p>
        {(report.findings || []).length === 0 && (
          <p className="text-xs text-zinc-500">
            {failed ? "No confirmed observations." : "No configuration concerns detected in the sampled response. This does not establish application security."}
          </p>
        )}
        <div className="space-y-2">
          {(report.findings || []).map((item) => (
            <article key={item.id} className="rounded-md border border-[#292929] bg-[#0B0B0B] p-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span className={"text-[10px] font-semibold uppercase " + (severityColors[item.severity] || severityColors.info)}>
                  {item.severity}
                </span>
                <span className="text-[10px] text-zinc-500">{item.cwe || "Unmapped"}</span>
                {item.owasp_top_10_2025_related && (
                  <span className="text-[10px] text-zinc-500">{item.owasp_top_10_2025_related} (related)</span>
                )}
                <span className="text-[10px] text-zinc-500">Confidence: {item.confidence || "Unspecified"}</span>
              </div>
              <p className="text-sm mt-2 font-medium">{item.title}</p>
              <p className="text-xs text-zinc-400 mt-1">{item.evidence || item.detail}</p>
              <p className="text-xs text-zinc-500 mt-2">Recommendation: {item.recommendation}</p>
            </article>
          ))}
        </div>
      </div>
      <p className="text-[11px] text-zinc-500">
        One HTTPS HEAD request; no content retrieval, no redirect following, no authentication testing,
        no vulnerability exploitation, and no penetration test.
      </p>
    </section>
  );
}

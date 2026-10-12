import { useEffect, useState } from "react";
import { AlertTriangle, BrainCircuit, ClipboardList, ShieldCheck, Users, WandSparkles } from "lucide-react";
import { createTestingReview, getTestingAgents, getTestingReviews } from "@/lib/api";

const errText = (err) => {
  const detail = err?.response?.data?.detail;
  return typeof detail === "string" ? detail : err?.message || "Review request failed.";
};

const LABEL = {
  qa_engineer: "QA Engineer",
  security_engineer: "Security Engineer",
  test_architect: "Test Architect",
};

export default function SpecialistReview({ scan, token, aiEnabled }) {
  const [agents, setAgents] = useState([]);
  const [review, setReview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [withAi, setWithAi] = useState(false);

  const scanId = scan?.id;
  useEffect(() => {
    if (!scanId || !token) {
      setReview(null);
      setAgents([]);
      return;
    }
    let active = true;
    setLoading(true);
    setReview(null);
    setError("");
    Promise.all([getTestingReviews(scanId, token), getTestingAgents(token)])
      .then(([history, specialistList]) => {
        if (!active) return;
        setReview(history[0] || null);
        setAgents(specialistList);
      })
      .catch(err => {
        if (active) setError(errText(err));
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [scanId, token]);

  if (!scan) return null;

  const reviewed = scan.status === "completed" &&
    (scan.result?.outcome === "pass" || scan.result?.outcome === "warning");

  const run = async () => {
    if (!reviewed || busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await createTestingReview(scanId, Boolean(withAi && aiEnabled), token);
      setReview(result);
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  };

  const noteMap = Object.fromEntries((review?.ai_notes || []).map(item => [item.id, item.note]));

  return (
    <section className="border-t border-[#282828] pt-4 space-y-3" data-testid="testing-agent-reviews" aria-label="Specialist agent review">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <BrainCircuit className="w-4 h-4 text-blue-400" />
            <h3 className="text-sm font-semibold">Specialist reviews</h3>
          </div>
          <p className="text-xs text-zinc-500 mt-1">
            QA, security and coverage analysis grounded in the recorded scan.
          </p>
        </div>
        <button type="button" disabled={!reviewed || busy || loading}
          onClick={run}
          data-testid="run-testing-review"
          className="btn-primary text-xs px-3 py-2 disabled:opacity-50">
          {busy ? "Reviewing..." : review ? "Run another review" : "Review scan"}
        </button>
      </div>

      {!!agents.length && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {agents.map(agent => (
            <div key={agent.role} className="p-3 bg-[#0B0B0B] border border-[#2A2A2A] rounded-md">
              <p className="text-xs font-semibold">{agent.name}</p>
              <p className="text-[11px] text-zinc-500">{agent.title}</p>
            </div>
          ))}
        </div>
      )}

      {!reviewed && (
        <div className="p-3 border border-amber-800/50 bg-amber-950/20 rounded-md text-xs text-amber-200">
          The scan did not complete with usable results. A specialist cannot
          verify findings from failed or incomplete testing.
        </div>
      )}

      {aiEnabled && reviewed && (
        <label className="flex gap-2 items-start text-xs text-zinc-400">
          <input type="checkbox" checked={withAi} onChange={e => setWithAi(e.target.checked)}
            className="mt-0.5" />
          <span>
            Request additional AI commentary. This sends limited recorded observation
            snippets to the configured AI provider. Comments are unverified suggestions
            and cannot introduce new findings or mark a fix complete.
          </span>
        </label>
      )}

      {error && <p role="alert" className="text-xs text-rose-300">{error}</p>}
      {loading && <p className="text-xs text-zinc-500">Loading reviews...</p>}

      {review && (
        <>
          <div className="p-3 border border-amber-800/40 bg-amber-950/10 rounded-md flex gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400" />
            <div>
              <p className="text-xs font-semibold text-amber-200">Release readiness: Not verified</p>
              <p className="text-xs text-zinc-400 mt-1">{review.release_reason}</p>
              <p className="text-[11px] text-zinc-500 mt-1">
                Analysis: {review.analysis_engine}. AI: {review.ai?.status || "not requested"}
                {review.ai?.accepted_notes ? " · " + review.ai.accepted_notes + " unverified note(s)" : ""}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
            {[
              ["QA observations", review.summary?.qa_findings],
              ["Security signals", review.summary?.security_findings],
              ["Coverage gaps", review.summary?.gaps],
              ["Suggested handoffs", review.summary?.handoffs],
            ].map(([label, count]) => (
              <div key={label} className="bg-[#0C0C0C] border border-[#282828] rounded-md p-2">
                <p className="font-mono text-lg">{count ?? 0}</p>
                <p className="text-[11px] text-zinc-500">{label}</p>
              </div>
            ))}
          </div>

          {(review.roles || []).map(role => (
            <div key={role.role} className="border border-[#282828] rounded-md p-3 space-y-2">
              <div className="flex items-center gap-2">
                {role.role === "security_engineer"
                  ? <ShieldCheck className="w-4 h-4 text-blue-400" />
                  : role.role === "test_architect"
                    ? <ClipboardList className="w-4 h-4 text-blue-400" />
                    : <Users className="w-4 h-4 text-blue-400" />}
                <p className="text-sm font-semibold">{role.name} · {LABEL[role.role] || role.role}</p>
              </div>
              <p className="text-xs text-zinc-400">{role.assessment}</p>
              {(role.findings || []).map(item => (
                <div key={item.source_finding_id} className="bg-[#0A0A0A] border-l-2 border-blue-700 pl-3 py-2">
                  <p className="text-xs font-medium">
                    {item.title} <span className="text-zinc-500">· {item.severity}</span>
                  </p>
                  <p className="text-xs text-zinc-400 mt-1">{item.observation || "Check original scan evidence."}</p>
                  <p className="text-xs text-zinc-500 mt-1">Suggested: {item.recommendation || "Investigate recorded finding."}</p>
                  {noteMap[item.source_finding_id] && (
                    <p className="text-xs text-amber-300 mt-2 flex gap-1 items-start">
                      <WandSparkles className="w-3 h-3 shrink-0 mt-0.5" />
                      Unverified AI note: {noteMap[item.source_finding_id]}
                    </p>
                  )}
                </div>
              ))}
              {role.role === "test_architect" && (role.gaps || []).map(gap => (
                <div key={gap.id} className="border-l-2 border-amber-800 pl-3 py-2">
                  <p className="text-xs text-zinc-400">{gap.description}</p>
                  <p className="text-[11px] text-amber-300 mt-1">Not tested</p>
                  {noteMap[gap.id] && (
                    <p className="text-xs text-amber-300 mt-1">
                      Unverified AI note: {noteMap[gap.id]}
                    </p>
                  )}
                </div>
              ))}
            </div>
          ))}

          {!!review.handoffs?.length && (
            <div className="border border-[#282828] rounded-md p-3">
              <p className="text-xs font-semibold mb-2">Suggested engineering handoffs (not assigned)</p>
              <div className="space-y-2">
                {review.handoffs.map(h => (
                  <div key={h.source_finding_id} className="bg-[#0A0A0A] rounded-md p-2">
                    <p className="text-xs"><span className="font-medium capitalize">{h.owner}</span> · {h.action}</p>
                    <p className="text-[11px] text-zinc-500 mt-1">{h.verification}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}

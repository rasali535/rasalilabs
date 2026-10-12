import { useCallback, useEffect, useState } from "react";
import { ClipboardCopy, GitPullRequest, RotateCw, ShieldAlert, Wrench } from "lucide-react";
import {
  createTestingRepair,
  createTestingScan,
  getTestingRepairs,
  publishTestingRepairPR,
  verifyTestingRepair,
} from "@/lib/api";

const detail = err => {
  const message = err?.response?.data?.detail;
  return typeof message === "string" ? message : err?.message || "Operation failed.";
};

export default function RepairWorkbench({ scan, token, config }) {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [editingCase, setEditingCase] = useState(null);
  const [filePath, setFilePath] = useState("");
  const [baseSha, setBaseSha] = useState("");
  const [source, setSource] = useState("");
  const [approvalToken, setApprovalToken] = useState("");
  const [confirmed, setConfirmed] = useState(false);

  const scanId = scan?.id;
  const reload = useCallback(async (active) => {
    const rows = await getTestingRepairs(token);
    if (active()) setCases(rows.filter(item => item.source_scan_id === scanId));
  }, [token, scanId]);

  useEffect(() => {
    if (!scanId || !token) { setCases([]); return; }
    let active = true;
    setCases([]);
    setError("");
    setFeedback("");
    setEditingCase(null);
    setLoading(true);
    reload(() => active)
      .catch(err => { if (active) setError(detail(err)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [reload, scanId, token]);

  if (!scan) return null;
  const usable = scan.status === "completed" && ["pass", "warning"].includes(scan.result?.outcome);
  const candidates = ["browser_smoke", "passive_security"].includes(scan.test_type) && usable
    ? (scan.result?.findings || []).filter(item => item.id && item.title && item.severity)
    : [];
  const existingIds = new Set(cases.map(item => item.source_finding_id));

  const action = async (label, task) => {
    setBusy(label);
    setError("");
    setFeedback("");
    try { await task(); }
    catch (err) { setError(detail(err)); }
    finally { setBusy(""); }
  };

  const createCase = finding => action("create-" + finding.id, async () => {
    const saved = await createTestingRepair(scanId, finding.id, token);
    setCases(prev => [saved, ...prev]);
    setFeedback("Repair case created. No code has been changed.");
  });

  const retest = item => action("retest-" + item.id, async () => {
    // Reuse Stage 2/3 scan endpoints, so authorization, approved host,
    // profile and isolation rules remain enforced by the existing backend.
    const fresh = await createTestingScan(
      { url: item.url, test_type: item.test_type }, token);
    const comparison = await verifyTestingRepair(item.id, fresh.id, token);
    setCases(prev => prev.map(row => row.id === item.id
      ? { ...row, latest_verification: comparison }
      : row));
    setFeedback("Retest " + comparison.result.replaceAll("_", " ") +
      ". This is not a release certification.");
  });

  const publish = item => action("publish-" + item.id, async () => {
    if (!confirmed) throw new Error("Review and explicitly approve the file replacement first.");
    const result = await publishTestingRepairPR(item.id, {
      repo: config?.repair_allowlisted_repo,
      file_path: filePath,
      expected_blob_sha: baseSha,
      new_source: source,
      approval_phrase: "CREATE DRAFT PR",
    }, token, approvalToken);
    setCases(prev => prev.map(row => row.id === item.id
      ? { ...row, status: result.status, pr: result.pr } : row));
    setEditingCase(null);
    setSource("");
    setApprovalToken("");
    setConfirmed(false);
    setFeedback("Draft PR opened for human review. It has not been merged or tested.");
  });

  return (
    <section className="border-t border-[#282828] pt-4 space-y-4" data-testid="testing-repair-workbench">
      <div className="flex items-center gap-2">
        <Wrench className="w-4 h-4 text-blue-400" />
        <h3 className="text-sm font-semibold">Fix &amp; Verify · Stage 5</h3>
      </div>
      <div className="border border-amber-800/40 bg-amber-950/10 rounded-md p-3 text-xs text-amber-200">
        Repairs are proposals until a human reviews an actual source patch. Retests
        execute the same approved scan profile and only report whether a specific
        observation reappears. No code changes, PR merges or deployments are automatic.
      </div>
      {error && <p role="alert" className="text-xs text-rose-300">{error}</p>}
      {feedback && <p role="status" className="text-xs text-sky-300">{feedback}</p>}
      {loading && <p className="text-xs text-zinc-500">Loading repair cases...</p>}
      {!candidates.length && (
        <p className="text-xs text-zinc-500">
          No actionable recorded findings are available in this scan. HTTP availability
          checks and incomplete scans cannot produce repair cases.
        </p>
      )}
      {candidates.length > 0 && (
        <div>
          <p className="text-xs font-medium mb-2">Open a case for an observed issue</p>
          <div className="space-y-2">
            {candidates.map(item => (
              <div key={item.id} className="rounded-md border border-[#292929] bg-[#0C0C0C] p-3 flex flex-wrap gap-2 items-center justify-between">
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium">{item.title}</p>
                  <p className="text-[11px] text-zinc-500 mt-1">
                    {item.category} · {item.severity} · {item.viewport || "all viewports"}
                  </p>
                </div>
                <button type="button" disabled={Boolean(busy) || existingIds.has(item.id)}
                  onClick={() => createCase(item)}
                  className="btn-secondary text-xs px-3 py-2 disabled:opacity-50">
                  {existingIds.has(item.id) ? "Case created" : "Create repair case"}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
      {!!cases.length && (
        <div className="space-y-3">
          <p className="text-xs font-medium">Repair cases</p>
          {cases.map(item => {
            const verification = item.latest_verification;
            return (
              <div key={item.id} className="border border-[#333] rounded-md p-3 space-y-3">
                <div className="flex justify-between gap-2 flex-wrap">
                  <div>
                    <p className="text-xs font-semibold">{item.finding?.title}</p>
                    <p className="text-[11px] text-zinc-500 mt-1">
                      Case {item.id.slice(0, 8)} · Suggested owner: {item.assigned_role} · {item.status}
                    </p>
                  </div>
                  {item.pr?.url && (
                    <a href={item.pr.url} target="_blank" rel="noreferrer noopener"
                      className="text-xs text-blue-400 flex gap-1 items-center">
                      <GitPullRequest className="w-3 h-3" /> Review draft PR #{item.pr.number}
                    </a>
                  )}
                </div>
                <p className="text-xs text-zinc-400">{item.proposed_action}</p>
                <button type="button" onClick={() => navigator.clipboard.writeText(item.coding_agent_prompt || "")}
                  className="text-xs text-blue-400 hover:underline flex items-center gap-1">
                  <ClipboardCopy className="w-3 h-3" /> Copy coding-agent investigation prompt
                </button>
                <div className="flex flex-wrap items-center gap-2">
                  <button type="button" disabled={Boolean(busy)}
                    onClick={() => retest(item)} className="btn-secondary text-xs px-3 py-2 flex items-center gap-2">
                    <RotateCw className="w-3 h-3" />
                    {busy === "retest-" + item.id ? "Retesting..." : "Run live retest"}
                  </button>
                  {config?.repair_pr_publisher_enabled && item.status === "proposed" && (
                    <button type="button" className="btn-secondary text-xs px-3 py-2"
                      onClick={() => setEditingCase(editingCase === item.id ? null : item.id)}>
                      Prepare approved GitHub PR
                    </button>
                  )}
                </div>
                {verification && (
                  <div className="border border-[#292929] rounded-md bg-[#111111] p-3">
                    <p className="text-xs font-medium">Latest comparison: {verification.result.replaceAll("_", " ")}</p>
                    <p className="text-xs text-zinc-500 mt-1">{verification.reason}</p>
                    <p className="text-[11px] text-amber-300 mt-1">Release readiness: not verified</p>
                  </div>
                )}
                {editingCase === item.id && (
                  <div className="border border-amber-800/50 rounded-md p-3 space-y-3 bg-[#0B0B0B]">
                    <div className="flex gap-2 items-start">
                      <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0" />
                      <p className="text-xs text-zinc-300">
                        Advanced staging integration: manually review the exact replacement file
                        and its GitHub main blob SHA first. Publishing writes a new feature
                        branch and opens a DRAFT PR; it never merges into main.
                      </p>
                    </div>
                    <p className="text-xs text-zinc-400">Operator-approved repository: {config?.repair_allowlisted_repo}</p>
                    <label className="block text-xs text-zinc-400">
                      Reviewed repository file path
                      <input value={filePath} onChange={e => setFilePath(e.target.value)}
                        placeholder="src/components/Example.tsx"
                        className="block w-full mt-1 bg-[#111] border border-[#333] rounded-md p-2 text-white" />
                    </label>
                    <label className="block text-xs text-zinc-400">
                      Current main file blob SHA (40 hex characters)
                      <input value={baseSha} onChange={e => setBaseSha(e.target.value)}
                        placeholder="Exact GitHub file SHA on main"
                        className="block w-full mt-1 bg-[#111] border border-[#333] rounded-md p-2 text-white" />
                    </label>
                    <label className="block text-xs text-zinc-400">
                      Full reviewed replacement source (up to 48 KB)
                      <textarea value={source} onChange={e => setSource(e.target.value)}
                        rows={6} placeholder="Paste the complete reviewed file content"
                        className="block w-full mt-1 bg-[#111] border border-[#333] rounded-md p-2 text-white font-mono text-xs" />
                    </label>
                    <label className="block text-xs text-zinc-400">
                      Separate operator repair approval token
                      <input type="password" autoComplete="off" value={approvalToken}
                        onChange={e => setApprovalToken(e.target.value)}
                        className="block w-full mt-1 bg-[#111] border border-[#333] rounded-md p-2 text-white" />
                    </label>
                    <label className="flex gap-2 text-xs text-amber-200 items-start">
                      <input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />
                      I reviewed this exact replacement against the recorded issue and authorize
                      opening a draft PR in the specified repository.
                    </label>
                    <button type="button" disabled={Boolean(busy) || !confirmed || !approvalToken ||
                      !filePath || !baseSha || !source}
                      onClick={() => publish(item)}
                      className="btn-primary text-xs px-3 py-2 disabled:opacity-50">
                      Create review-only GitHub draft PR
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

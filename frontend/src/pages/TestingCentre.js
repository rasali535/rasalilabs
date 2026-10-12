import { useCallback, useState } from "react";
import { toast } from "sonner";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Globe,
  History,
  Loader2,
  LockKeyhole,
  RefreshCw,
  ShieldCheck,
  Image as ImageIcon,
} from "lucide-react";
import { createTestingScan, getTestingConfig, getTestingScans, getTestingEvidence } from "@/lib/api";
import SecurityReport from "@/components/SecurityReport";
import SpecialistReview from "@/components/SpecialistReview";

const getError = (error) => {
  const detail = error?.response?.data?.detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg || "Invalid input").join("; ");
  return typeof detail === "string" ? detail : error?.message || "Request failed.";
};

export default function TestingCentre() {
  const [token, setToken] = useState("");
  const [url, setUrl] = useState("");
  const [testType, setTestType] = useState("availability");
  const [preview, setPreview] = useState(null);
  const [evidenceBusy, setEvidenceBusy] = useState(false);
  const [scans, setScans] = useState([]);
  const [selected, setSelected] = useState(null);
  const [config, setConfig] = useState(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const loadHistory = useCallback(async (providedToken) => {
    if (!providedToken) return;
    setLoading(true);
    setErrorMessage("");
    try {
      const [details, items] = await Promise.all([
        getTestingConfig(providedToken),
        getTestingScans(providedToken),
      ]);
      setConfig(details);
      setScans(items);
    } catch (error) {
      setConfig(null);
      setScans([]);
      setErrorMessage(getError(error));
    } finally {
      setLoading(false);
    }
  }, []);

  const selectScan = (scan) => {
    setSelected(scan);
    setPreview(null);
  };

  const loadEvidence = async (id) => {
    setEvidenceBusy(true);
    setErrorMessage("");
    try {
      const evidence = await getTestingEvidence(id, token.trim());
      setPreview(evidence);
    } catch (error) {
      setErrorMessage(getError(error));
    } finally {
      setEvidenceBusy(false);
    }
  };

  const submitScan = async (event) => {
    event.preventDefault();
    if (!token.trim() || !url.trim() || busy) return;
    setBusy(true);
    setErrorMessage("");
    try {
      const result = await createTestingScan({ url: url.trim(), test_type: testType }, token.trim());
      selectScan(result);
      setUrl("");
      toast.success("Check recorded. Review the measured results.");
      await loadHistory(token.trim());
    } catch (error) {
      const message = getError(error);
      setErrorMessage(message);
      toast.error(message);
    } finally {
      setBusy(false);
    }
  };

  const active = scans.find((scan) => scan.id === selected?.id) || selected;
  const outcome = active?.result?.outcome;
  const statusClass =
    outcome === "pass"
      ? "text-emerald-400"
      : outcome === "fail"
      ? "text-rose-400"
      : "text-amber-400";

  return (
    <div className="h-full overflow-auto bg-[#0A0A0A] text-white" data-testid="testing-centre-page">
      <div className="px-4 sm:px-6 py-5 border-b border-[#222222]">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-md border border-[#273E8F] bg-[#111E41]">
            <ShieldCheck className="w-5 h-5 text-blue-400" aria-hidden="true" />
          </div>
          <div>
            <h1 className="font-['Chivo'] text-xl font-bold">Testing Centre</h1>
            <p className="text-xs text-zinc-500 mt-1">
              Stage 3 · Development preview · Browser QA + passive security checks
            </p>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto p-4 sm:p-6 space-y-5">
        <div className="border border-amber-800/50 bg-amber-950/20 p-4 rounded-md flex gap-3" role="note">
          <AlertTriangle className="w-5 h-5 shrink-0 text-amber-400" aria-hidden="true" />
          <div>
            <p className="text-sm font-medium text-amber-100">Not a security certification or penetration test</p>
            <p className="text-xs text-amber-200/70 mt-1 leading-5">
              Availability, browser smoke checks and passive HTTPS security observations run
              only on approved destinations with operator access. Passive scans inspect one
              TLS connection and response headers. No attacks or penetration testing.
              Domain ownership and customer accounts are not yet implemented.
            </p>
          </div>
        </div>

        <section className="border border-[#252525] rounded-lg p-4 sm:p-5 bg-[#111111] space-y-4" aria-label="Scan setup">
          <div className="flex gap-2 items-center">
            <LockKeyhole className="w-4 h-4 text-zinc-400" aria-hidden="true" />
            <h2 className="font-semibold text-sm">Development access</h2>
          </div>
          <p className="text-zinc-500 text-xs">
            Ask your operator to enable the feature, approve the target hostname and supply
            a testing token. The token stays in this tab's memory and is not saved to your browser.
          </p>
          <div className="flex flex-col sm:flex-row gap-2">
            <label className="sr-only" htmlFor="testing-access-token">Testing access token</label>
            <input
              id="testing-access-token"
              type="password"
              autoComplete="off"
              value={token}
              onChange={(e) => { setToken(e.target.value); setConfig(null); setScans([]); setSelected(null); }}
              placeholder="Testing access token"
              className="w-full bg-[#0C0C0C] border border-[#333] rounded-md px-3 py-2.5 text-sm focus:outline-none focus:border-blue-500"
              data-testid="testing-token-input"
            />
            <button
              type="button"
              className="btn-secondary px-4 py-2.5 text-sm shrink-0"
              onClick={() => loadHistory(token.trim())}
              disabled={!token.trim() || loading || busy}
              data-testid="testing-unlock"
            >
              {loading ? "Checking..." : "Open Testing Centre"}
            </button>
          </div>
          {config && (
            <div className="text-xs text-zinc-400">
              Approved hosts: <span className="text-white">{config.allowed_hosts.join(", ")}</span>
            </div>
          )}
        </section>

        {errorMessage && (
          <div role="alert" className="border border-rose-700/50 bg-rose-950/20 text-rose-300 rounded-md p-3 text-sm">
            {errorMessage}
          </div>
        )}

        {config && (
          <>
            <section className="border border-[#252525] rounded-lg p-4 sm:p-5 bg-[#111111]" aria-label="New scan">
              <div className="flex items-center gap-2 mb-3">
                <Globe className="w-4 h-4 text-blue-400" aria-hidden="true" />
                <h2 className="font-semibold text-sm">New application check</h2>
              </div>
              <div className="mb-3">
                <label htmlFor="testing-mode" className="block text-xs text-zinc-400 mb-1">Test profile</label>
                <select
                  id="testing-mode"
                  value={testType}
                  onChange={(event) => setTestType(event.target.value)}
                  className="w-full bg-[#0C0C0C] border border-[#333] rounded-md px-3 py-2.5 text-sm"
                  data-testid="testing-mode-select"
                >
                  <option value="availability">Availability check (HTTP)</option>
                  <option value="browser_smoke" disabled={!config.browser_enabled}>
                    Live browser QA (desktop, tablet, mobile){config.browser_enabled ? "" : " — worker not enabled"}
                  </option>
                  <option value="passive_security" disabled={!config.passive_security_enabled}>
                    Passive security (HTTPS/TLS, headers, cookies, API signals){config.passive_security_enabled ? "" : " — worker not enabled"}
                  </option>
                </select>
              </div>
              <form onSubmit={submitScan} className="flex flex-col sm:flex-row gap-2">
                <label className="sr-only" htmlFor="testing-url">Approved website URL</label>
                <input
                  id="testing-url"
                  type="url"
                  required
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://approved-example.com/"
                  className="min-w-0 w-full bg-[#0C0C0C] border border-[#333] rounded-md px-3 py-2.5 text-sm focus:outline-none focus:border-blue-500"
                  data-testid="testing-url-input"
                />
                <button
                  type="submit"
                  disabled={busy}
                  className="btn-primary px-5 py-2.5 text-sm flex items-center justify-center gap-2 shrink-0"
                  data-testid="testing-start-scan"
                >
                  {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
                  {busy ? "Checking..." : "Run check"}
                </button>
              </form>
              <p className="text-xs text-zinc-500 mt-3">
                Only approved domains. No redirects followed, no login attempts, no crawling or attack traffic.
              </p>
            </section>

            <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
              <section className="lg:col-span-2 border border-[#252525] rounded-lg bg-[#111111] p-4" aria-label="Scan history">
                <div className="flex justify-between items-center mb-4">
                  <div className="flex gap-2 items-center">
                    <History className="w-4 h-4 text-zinc-400" />
                    <h2 className="font-semibold text-sm">Recent checks</h2>
                  </div>
                  <button
                    type="button"
                    onClick={() => loadHistory(token.trim())}
                    disabled={loading || busy}
                    aria-label="Refresh scan history"
                    className="text-zinc-400 hover:text-white disabled:opacity-50"
                  >
                    <RefreshCw className={"w-4 h-4 " + (loading ? "animate-spin" : "")} />
                  </button>
                </div>
                {scans.length === 0 && (
                  <p className="text-sm text-zinc-500 py-8 text-center">No checks recorded yet.</p>
                )}
                <div className="space-y-2">
                  {scans.map((scan) => (
                    <button
                      key={scan.id}
                      type="button"
                      onClick={() => selectScan(scan)}
                      className={"w-full text-left border rounded-md p-3 hover:border-blue-600 " +
                        (active?.id === scan.id ? "border-blue-600 bg-blue-950/20" : "border-[#292929] bg-[#151515]")}
                    >
                      <span className="block text-sm truncate">{scan.host}</span>
                      <span className="block text-xs text-zinc-500 mt-1">
                        {scan.test_type === "browser_smoke" ? "Browser QA" : scan.test_type === "passive_security" ? "Passive Security" : "HTTP"} · {scan.status} · {new Date(scan.created_at).toLocaleString()}
                      </span>
                    </button>
                  ))}
                </div>
              </section>

              <section className="lg:col-span-3 border border-[#252525] rounded-lg bg-[#111111] p-4" aria-label="Scan results" data-testid="testing-results">
                <h2 className="font-semibold text-sm mb-4">Check results</h2>
                {!active ? (
                  <div className="flex flex-col items-center justify-center text-center py-12 gap-2 text-zinc-500">
                    <Clock3 className="w-7 h-7" />
                    <p className="text-sm">Select a previous check or run a new one.</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div>
                      <p className="text-sm font-medium break-all">{active.url}</p>
                      <p className="text-xs text-zinc-500 mt-1">Check ID: {active.id}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {outcome === "pass" ? <CheckCircle2 className="w-5 h-5 text-emerald-400" /> : <AlertTriangle className={"w-5 h-5 " + statusClass} />}
                      <span className={"capitalize font-semibold text-sm " + statusClass}>
                        {outcome || active.status}
                      </span>
                    </div>
                    {active.test_type === "browser_smoke" && (
                      <div className="bg-[#0B0B0B] border border-[#282828] rounded-md p-3 space-y-1">
                        <p className="text-xs text-zinc-500">Browser audit summary</p>
                        <p className="text-sm">
                          {active.result?.summary?.viewports_completed ?? 0}/3 viewports loaded ·
                          {" "}{active.result?.summary?.high ?? 0} high ·
                          {" "}{active.result?.summary?.medium ?? 0} medium ·
                          {" "}{active.result?.summary?.low ?? 0} low
                        </p>
                        <p className="text-xs text-zinc-500">
                          {active.result?.third_party_requests_blocked ?? 0} external/overflow requests blocked
                        </p>
                      </div>
                    )}
                    <div className="grid grid-cols-2 gap-3">
                      <div className="bg-[#0B0B0B] border border-[#282828] rounded-md p-3">
                        <p className="text-xs text-zinc-500">HTTP status</p>
                        <p className="font-mono text-lg mt-1">{active.result?.http_status ?? active.result?.viewports?.[0]?.http_status ?? "—"}</p>
                      </div>
                      <div className="bg-[#0B0B0B] border border-[#282828] rounded-md p-3">
                        <p className="text-xs text-zinc-500">Response time</p>
                        <p className="font-mono text-lg mt-1">{active.result?.latency_ms ?? active.result?.elapsed_ms ?? "—"} ms</p>
                      </div>
                    </div>
                    {active.result?.redirect_not_followed && (
                      <p className="text-xs text-amber-300">The server redirected this request. Redirects are deliberately not followed.</p>
                    )}
                    {active.result?.error && (
                      <p className="text-xs text-rose-300">Network check failed: {active.result.error}</p>
                    )}
                    {active.test_type === "passive_security" && <SecurityReport report={active.result} />}
                    {active.test_type === "browser_smoke" && (
                      <div className="space-y-4 border-t border-[#282828] pt-4">
                        <div>
                          <p className="font-medium text-xs mb-2">Observed findings</p>
                          {!(active.result?.findings || []).length && (
                            <p className="text-zinc-500 text-xs">No findings from the limited checks that completed.</p>
                          )}
                          <div className="space-y-2">
                            {(active.result?.findings || []).map((item) => (
                              <div key={item.id} className="border border-[#292929] rounded-md p-3 bg-[#0B0B0B]">
                                <div className="flex flex-wrap items-center gap-2 mb-1">
                                  <span className={
                                    "text-[10px] uppercase font-semibold " +
                                    (item.severity === "high" ? "text-rose-400" : item.severity === "medium" ? "text-amber-400" : "text-blue-400")
                                  }>{item.severity}</span>
                                  <span className="text-xs text-zinc-500">{item.viewport || "General"}</span>
                                </div>
                                <p className="font-medium text-xs">{item.title}</p>
                                <p className="text-xs text-zinc-400 mt-1 break-words">{item.detail}</p>
                                <p className="text-xs text-zinc-500 mt-2">Suggested action: {item.recommendation}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div>
                          <p className="font-medium text-xs mb-2">Viewport measurements</p>
                          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                            {(active.result?.viewports || []).map((view) => (
                              <div key={view.name} className="p-2 rounded-md border border-[#292929] text-xs">
                                <p className="font-semibold capitalize">{view.name}</p>
                                <p className="text-zinc-500 mt-1">{view.width} × {view.height}</p>
                                <p className="text-zinc-400 mt-1">DOM: {view.metrics?.dom_content_loaded_ms ?? "—"} ms</p>
                                <p className="text-zinc-400">FCP: {view.metrics?.fcp_ms ?? "—"} ms</p>
                                {view.evidence_id && (
                                  <button
                                    type="button"
                                    disabled={evidenceBusy}
                                    onClick={() => loadEvidence(view.evidence_id)}
                                    className="text-blue-400 hover:underline mt-2 flex items-center gap-1"
                                  ><ImageIcon className="w-3 h-3" /> View screenshot</button>
                                )}
                              </div>
                            ))}
                          </div>
                          {preview?.data_uri && (
                            <div className="mt-3 border border-[#333] rounded-md p-2">
                              <div className="flex justify-between text-xs pb-2">
                                <span className="capitalize">{preview.viewport} screenshot</span>
                                <button type="button" onClick={() => setPreview(null)}
                                  className="text-zinc-400 hover:text-white">Close</button>
                              </div>
                              <img src={preview.data_uri} alt={preview.viewport + " viewport evidence"}
                                   className="w-full rounded-md" />
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                    <div className="border-t border-[#282828] pt-4">
                      <p className="text-xs font-medium mb-2">What was checked</p>
                      <ul className="text-xs text-zinc-400 space-y-1 list-disc pl-4">
                        {(active.result?.checks || active.result?.tested_checks || []).map((item) => <li key={item}>{item}</li>)}
                      </ul>
                      <p className="text-xs font-medium mt-4 mb-2">Not tested</p>
                      <ul className="text-xs text-zinc-400 space-y-1 list-disc pl-4">
                        {(active.result?.limitations || active.result?.not_tested || []).map((item) => <li key={item}>{item}</li>)}
                      </ul>
                    </div>
                    <SpecialistReview scan={active} token={token.trim()}
                                      aiEnabled={Boolean(config.agent_ai_enabled)} />
                  </div>
                )}
              </section>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

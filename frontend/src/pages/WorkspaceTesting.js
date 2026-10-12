import { useState } from "react";
import { CheckCircle2, Globe2, LockKeyhole, RefreshCw, ShieldCheck, Users } from "lucide-react";
import {
  registerTestingAccount, loginTestingAccount, getCustomerWorkspaces,
  getCustomerDomains, addCustomerDomain, verifyCustomerDomain,
  getCustomerJobs, submitCustomerJob,
} from "@/lib/api";

const errorText = e => {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map(v => v.msg).join("; ");
  return e?.message || "Request failed.";
};

export default function WorkspaceTesting() {
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [invite, setInvite] = useState("");
  const [name, setName] = useState("");
  const [mode, setMode] = useState("login");
  const [workspaces, setWorkspaces] = useState([]);
  const [workspace, setWorkspace] = useState("");
  const [domains, setDomains] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [hostname, setHostname] = useState("");
  const [url, setUrl] = useState("");
  const [domainId, setDomainId] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const exec = async (label, action) => {
    if (busy) return;
    setBusy(label);
    setError("");
    setNotice("");
    try { await action(); }
    catch (e) { setError(errorText(e)); }
    finally { setBusy(""); }
  };

  const showWorkspaces = async (accessToken, preferred = "") => {
    const items = await getCustomerWorkspaces(accessToken);
    setWorkspaces(items);
    const chosen = items.some(x => x.id === preferred) ? preferred : items[0]?.id || "";
    setWorkspace(chosen);
    if (chosen) {
      const [d, j] = await Promise.all([
        getCustomerDomains(accessToken, chosen),
        getCustomerJobs(accessToken, chosen),
      ]);
      setDomains(d);
      setJobs(j);
      setDomainId(d[0]?.id || "");
    }
  };

  const selectWorkspace = async (id) => {
    setWorkspace(id);
    setDomains([]);
    setJobs([]);
    setDomainId("");
    if (!id) return;
    await exec("workspace", async () => {
      const [d, j] = await Promise.all([
        getCustomerDomains(token, id), getCustomerJobs(token, id),
      ]);
      setDomains(d);
      setJobs(j);
      setDomainId(d[0]?.id || "");
    });
  };

  const authSubmit = e => {
    e.preventDefault();
    exec("auth", async () => {
      if (mode === "register") {
        await registerTestingAccount({
          email: email.trim(), password, workspace_name: name.trim(),
          invitation_code: invite,
        });
        setMode("login");
        setPassword("");
        setInvite("");
        setNotice("Invite accepted. Sign in with the account you just created.");
      } else {
        const session = await loginTestingAccount({ email: email.trim(), password });
        // Deliberately in-memory only: no persistent bearer token in browser storage.
        setToken(session.access_token);
        setPassword("");
        await showWorkspaces(session.access_token);
        setNotice("Signed in. Your Testing Centre session expires in 30 minutes.");
      }
    });
  };

  const logout = () => {
    setToken(""); setWorkspaces([]); setWorkspace("");
    setDomains([]); setJobs([]); setDomainId("");
    setPassword(""); setNotice("Signed out of this browser tab.");
  };

  const refresh = () => exec("refresh", async () => {
    await showWorkspaces(token, workspace);
    setNotice("Workspace records refreshed.");
  });

  const registerDomain = e => {
    e.preventDefault();
    exec("domain", async () => {
      const d = await addCustomerDomain(hostname.trim(), token, workspace);
      setDomains(prev => [...prev, d]);
      setDomainId(d.id);
      setHostname("");
      setNotice("Add the displayed DNS TXT record, then select Verify.");
    });
  };

  const verifyDomain = id => exec("verify-" + id, async () => {
    await verifyCustomerDomain(id, token, workspace);
    const list = await getCustomerDomains(token, workspace);
    setDomains(list);
    setNotice("DNS ownership verified. Reverify after expiration.");
  });

  const queue = e => {
    e.preventDefault();
    exec("queue", async () => {
      const job = await submitCustomerJob(domainId, url.trim(), token, workspace);
      setJobs(prev => [job, ...prev]);
      setUrl("");
      setNotice("Queued for a separate, isolated worker. This is not a completed scan.");
    });
  };

  return (
    <div className="h-full overflow-auto bg-[#0A0A0A] text-white p-4 sm:p-6" data-testid="customer-testing-page">
      <div className="max-w-5xl mx-auto space-y-5">
        <header className="flex items-center gap-3">
          <div className="p-2 rounded-md border border-blue-900 bg-blue-950/20">
            <ShieldCheck className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold font-['Chivo']">Testing Workspaces</h1>
            <p className="text-xs text-zinc-500 mt-1">Stage 6A · Invite-only customer preview · Tenant-isolated records</p>
          </div>
        </header>
        <div className="rounded-md border border-amber-800/40 bg-amber-950/20 p-3 text-xs text-amber-200">
          Customer testing is limited to ownership-verified domains and queued HTTPS availability checks.
          Live browser QA, penetration testing, production billing and autonomous repairs are not enabled.
          A separate network-isolated worker must be deployed to process jobs.
        </div>
        {error && <p role="alert" className="rounded-md border border-rose-800 p-3 text-sm text-rose-300">{error}</p>}
        {notice && <p role="status" className="text-xs text-sky-300">{notice}</p>}
        {!token ? (
          <form onSubmit={authSubmit} className="rounded-lg border border-[#292929] bg-[#111] p-4 sm:p-6 space-y-3 max-w-xl">
            <div className="flex items-center gap-2">
              <LockKeyhole className="w-4 h-4 text-blue-400" />
              <h2 className="font-semibold">{mode === "login" ? "Customer sign-in" : "Invite-only account creation"}</h2>
            </div>
            <label className="block text-xs text-zinc-400">Email
              <input required type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)}
                className="mt-1 w-full rounded-md border border-[#383838] bg-[#0B0B0B] p-3 text-sm text-white" />
            </label>
            <label className="block text-xs text-zinc-400">Password
              <input required type="password" minLength={mode === "register" ? 12 : 1}
                autoComplete={mode === "register" ? "new-password" : "current-password"}
                value={password} onChange={e => setPassword(e.target.value)}
                className="mt-1 w-full rounded-md border border-[#383838] bg-[#0B0B0B] p-3 text-sm text-white" />
            </label>
            {mode === "register" && (
              <>
                <label className="block text-xs text-zinc-400">Workspace name
                  <input required value={name} onChange={e => setName(e.target.value)}
                    className="mt-1 w-full rounded-md border border-[#383838] bg-[#0B0B0B] p-3 text-sm text-white" />
                </label>
                <label className="block text-xs text-zinc-400">Operator invitation code
                  <input required type="password" autoComplete="off" value={invite}
                    onChange={e => setInvite(e.target.value)}
                    className="mt-1 w-full rounded-md border border-[#383838] bg-[#0B0B0B] p-3 text-sm text-white" />
                </label>
              </>
            )}
            <button type="submit" disabled={Boolean(busy)} className="btn-primary px-5 py-2.5 text-sm disabled:opacity-50">
              {busy === "auth" ? "Checking..." : mode === "login" ? "Sign in" : "Create invited account"}
            </button>
            <button type="button" onClick={() => {setMode(mode === "login" ? "register" : "login"); setError("");}}
              className="block text-xs text-blue-400 hover:underline">
              {mode === "login" ? "Have an invitation? Create an account" : "Already registered? Sign in"}
            </button>
          </form>
        ) : (
          <>
            <section className="border border-[#292929] rounded-md bg-[#111] p-4 flex flex-col sm:flex-row sm:items-end justify-between gap-3">
              <div className="flex-1">
                <label className="block text-xs text-zinc-400 mb-1" htmlFor="customer-workspace-select">Active workspace</label>
                <select id="customer-workspace-select" value={workspace} onChange={e => selectWorkspace(e.target.value)}
                  className="w-full border border-[#383838] bg-[#0B0B0B] p-2.5 rounded-md text-sm text-white">
                  {workspaces.map(w => <option key={w.id} value={w.id}>{w.name} ({w.role})</option>)}
                </select>
              </div>
              <div className="flex gap-2">
                <button type="button" onClick={refresh} disabled={Boolean(busy)}
                  className="btn-secondary px-3 py-2 text-xs flex items-center gap-2">
                  <RefreshCw className="w-3 h-3" /> Refresh
                </button>
                <button type="button" onClick={logout} className="btn-secondary px-3 py-2 text-xs">Sign out</button>
              </div>
            </section>

            {workspace && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <section className="border border-[#292929] rounded-md bg-[#111] p-4 space-y-3">
                  <h2 className="font-semibold text-sm flex items-center gap-2">
                    <Globe2 className="w-4 h-4 text-blue-400" /> Verified domains
                  </h2>
                  <form onSubmit={registerDomain} className="flex flex-col sm:flex-row gap-2">
                    <input required placeholder="staging.example.com" value={hostname}
                      onChange={e => setHostname(e.target.value)}
                      className="w-full border border-[#383838] bg-[#0B0B0B] p-2.5 rounded-md text-sm" />
                    <button type="submit" disabled={Boolean(busy)} className="btn-primary px-3 py-2 text-xs shrink-0">
                      Add domain
                    </button>
                  </form>
                  {!domains.length && <p className="text-xs text-zinc-500">No domain registered.</p>}
                  {domains.map(d => {
                    const active = Boolean(d.verification_expires_at && Date.parse(d.verification_expires_at) > Date.now());
                    return (
                      <div key={d.id} className="border border-[#303030] rounded-md p-3 space-y-2 text-xs">
                        <div className="flex gap-2 items-center">
                          {active && <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
                          <span className="font-medium">{d.hostname}</span>
                          <span className="text-zinc-500">{active ? "Verified" : "Not verified"}</span>
                        </div>
                        <p className="text-zinc-500">DNS TXT hostname</p>
                        <p className="font-mono break-all select-all">{d.challenge_record}</p>
                        <p className="text-zinc-500">TXT value</p>
                        <p className="font-mono break-all select-all">{d.challenge_value}</p>
                        <button type="button" disabled={Boolean(busy)} onClick={() => verifyDomain(d.id)}
                          className="btn-secondary px-3 py-2 text-xs">
                          Verify ownership
                        </button>
                      </div>
                    );
                  })}
                </section>

                <section className="border border-[#292929] rounded-md bg-[#111] p-4 space-y-3">
                  <h2 className="font-semibold text-sm flex gap-2 items-center">
                    <Users className="w-4 h-4 text-blue-400" /> Queued HTTPS checks
                  </h2>
                  <form onSubmit={queue} className="space-y-2">
                    <label className="block text-xs text-zinc-400">Verified target
                      <select value={domainId} required onChange={e => setDomainId(e.target.value)}
                        className="mt-1 w-full border border-[#383838] bg-[#0B0B0B] p-2.5 rounded-md text-sm">
                        <option value="">Choose a domain</option>
                        {domains.filter(d => d.verification_expires_at && Date.parse(d.verification_expires_at) > Date.now())
                          .map(d => <option key={d.id} value={d.id}>{d.hostname}</option>)}
                      </select>
                    </label>
                    <label className="block text-xs text-zinc-400">HTTPS URL to check
                      <input type="url" required placeholder="https://staging.example.com/" value={url}
                        onChange={e => setUrl(e.target.value)}
                        className="mt-1 w-full border border-[#383838] bg-[#0B0B0B] p-2.5 rounded-md text-sm" />
                    </label>
                    <button type="submit" disabled={Boolean(busy) || !domainId} className="btn-primary px-3 py-2.5 text-xs disabled:opacity-50">
                      {busy === "queue" ? "Queueing..." : "Queue availability check"}
                    </button>
                  </form>
                  <p className="text-xs text-zinc-500">Requests are queued, not executed by this web server.</p>
                  {!jobs.length && <p className="text-xs text-zinc-500">No scans yet.</p>}
                  <div className="max-h-96 overflow-auto space-y-2">
                    {jobs.map(j => (
                      <div key={j.id} className="bg-[#0B0B0B] border border-[#292929] rounded-md p-3">
                        <p className="text-xs truncate">{j.url}</p>
                        <p className="text-[11px] text-zinc-400 mt-1">
                          {j.status} · {j.result?.outcome || "not tested"}
                          {j.result?.http_status ? " · HTTP " + j.result.http_status : ""}
                        </p>
                        <p className="text-[11px] text-zinc-500 mt-1">
                          {j.result?.error || "No penetration or browser tests"}
                        </p>
                      </div>
                    ))}
                  </div>
                </section>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { LockKeyhole, ShieldAlert } from "lucide-react";
import {
  checkLegacyOperatorToken, clearLegacyOperatorToken,
  getLegacyAccessStatus, setLegacyOperatorGateRequired,
  setLegacyOperatorToken,
} from "@/lib/api";

export default function LegacyOperatorAccess() {
  const [status, setStatus] = useState("loading");
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    getLegacyAccessStatus().then(info => {
      if (!active) return;
      setLegacyOperatorGateRequired(Boolean(info.required));
      setStatus(info.required ? "locked" : "open");
    }).catch(() => {
      if (active) {
        setLegacyOperatorGateRequired(true);
        setStatus("error");
      }
    });
    return () => { active = false; };
  }, []);

  if (status === "open") return <Outlet />;
  if (status === "loading") return (
    <div className="h-full grid place-items-center text-xs text-zinc-500">
      Checking operator access...
    </div>
  );
  const unlock = async e => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await checkLegacyOperatorToken(value);
      setLegacyOperatorToken(value);
      setValue("");
      setStatus("open");
    } catch (err) {
      clearLegacyOperatorToken();
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Operator access could not be verified.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="h-full overflow-auto bg-[#090909] p-5 sm:p-10 flex justify-center items-center">
      <div className="w-full max-w-md space-y-4 rounded-lg border border-[#333] bg-[#111] p-6">
        <div className="flex items-center gap-3">
          {status === "error" ? <ShieldAlert className="text-amber-400" /> : <LockKeyhole className="text-blue-400" />}
          <div>
            <h2 className="font-semibold">Private AI-agent workspace</h2>
            <p className="text-xs text-zinc-400 mt-1">Separate from customer Testing Workspaces</p>
          </div>
        </div>
        <p className="text-xs text-zinc-400 leading-5">
          The original eight-agent dashboard is protected by operator access.
          Your access code stays in this browser tab's memory and is not saved.
        </p>
        {status === "error" ? (
          <div className="text-xs text-amber-300">
            Unable to check access status. Private routes remain locked.
            <button type="button" onClick={() => window.location.reload()}
              className="block text-blue-400 underline mt-3">Retry status check</button>
          </div>
        ) : (
          <form onSubmit={unlock} className="space-y-3">
            <label className="block text-xs text-zinc-400">Operator access token
              <input required type="password" autoComplete="off" value={value}
                onChange={e => setValue(e.target.value)}
                className="mt-1 w-full bg-[#0B0B0B] border border-[#383838] rounded-md p-3 text-white text-sm" />
            </label>
            {error && <p role="alert" className="text-xs text-rose-300">{error}</p>}
            <button type="submit" disabled={busy}
              className="btn-primary px-4 py-2.5 text-sm disabled:opacity-50">
              {busy ? "Verifying..." : "Unlock private workspace"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

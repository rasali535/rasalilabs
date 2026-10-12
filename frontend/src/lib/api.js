import axios from "axios";

// The API runs on the secured Ras Ali Labs Render service, NOT the old Render
// account and NOT the publicly routed Vercel Python function.
// For future production migration, configure REACT_APP_BACKEND_URL explicitly
// at build time. No credentials belong in this public frontend variable.
const configuredBackend = (process.env.REACT_APP_BACKEND_URL || "").trim().replace(/\\/+$/, "");
export const BACKEND_URL = configuredBackend || "https://rasalilabs-api-staging.onrender.com";
const API = `${BACKEND_URL}/api`;

const api = axios.create({ baseURL: API });

// Operator token is deliberately ephemeral: never persisted to localStorage,
// cookies, URLs, or bundled source. Customer bearer auth remains independent.
let legacyOperatorToken = "";
let legacyOperatorGateRequired = false;

export const setLegacyOperatorToken = (token) => { legacyOperatorToken = token || ""; };
export const clearLegacyOperatorToken = () => { legacyOperatorToken = ""; };
export const setLegacyOperatorGateRequired = (required) => { legacyOperatorGateRequired = Boolean(required); };
export const getLegacyWsProtocols = () =>
  legacyOperatorGateRequired && legacyOperatorToken
    ? ["rasali-operator." + legacyOperatorToken]
    : [];

export const getLegacyAccessStatus = () =>
  api.get("/legacy-access/status").then(r => r.data);
export const checkLegacyOperatorToken = (token) =>
  api.post("/legacy-access/check", {}, {
    headers: { "X-Legacy-Operator-Token": token },
  }).then(r => r.data);

api.interceptors.request.use((config) => {
  const path = config.url || "";
  if (legacyOperatorToken &&
      !path.startsWith("/customer-testing/") &&
      !path.startsWith("/testing/") &&
      !path.startsWith("/legacy-access/")) {
    config.headers = config.headers || {};
    config.headers["X-Legacy-Operator-Token"] = legacyOperatorToken;
  }
  return config;
});


api.interceptors.response.use(
  (response) => {
    if (typeof response.data === 'string' && response.data.trim().startsWith('<')) {
      console.error("API returned HTML instead of JSON. Check BACKEND_URL configuration.");
      return Promise.reject(new Error("API returned HTML."));
    }
    return response;
  },
  (error) => Promise.reject(error)
);

// ─── Health ───
export const getHealth = () => api.get("/health").then(r => r.data);
export const getStats = () => api.get("/stats").then(r => r.data);
export const getLogoUrl = () => `${API}/logo`;

// ─── Agents ───
export const getAgents = () => api.get("/agents").then(r => Array.isArray(r.data) ? r.data : []);
export const getAgent = (role) => api.get(`/agents/${role}`).then(r => r.data);

// ─── Projects ───
export const createProject = (data) => api.post("/projects", data).then(r => r.data);
export const getProjects = () => api.get("/projects").then(r => Array.isArray(r.data) ? r.data : []);
export const getProject = (id) => api.get(`/projects/${id}`).then(r => r.data);

// ─── Meetings ───
export const createMeeting = (data) => api.post("/meetings", data).then(r => r.data);
export const getMeetings = (projectId) => api.get("/meetings", { params: projectId ? { project_id: projectId } : {} }).then(r => Array.isArray(r.data) ? r.data : []);
export const getMeeting = (id) => api.get(`/meetings/${id}`).then(r => r.data);

// ─── Tasks ───
export const createTask = (data) => api.post("/tasks", data).then(r => r.data);
export const getTasks = (params) => api.get("/tasks", { params }).then(r => Array.isArray(r.data) ? r.data : []);
export const getTask = (id) => api.get(`/tasks/${id}`).then(r => r.data);
export const updateTask = (id, data) => api.patch(`/tasks/${id}`, data).then(r => r.data);

// ─── Messages ───
export const sendMessage = (data) => api.post("/messages", data).then(r => r.data);
export const getMessages = (params) => api.get("/messages", { params }).then(r => r.data);
export const getThreads = (projectId) => api.get("/threads", { params: projectId ? { project_id: projectId } : {} }).then(r => r.data);

// ─── Decisions ───
export const createDecision = (data) => api.post("/decisions", data).then(r => r.data);
export const getDecisions = (params) => api.get("/decisions", { params }).then(r => Array.isArray(r.data) ? r.data : []);
export const voteDecision = (id, data) => api.post(`/decisions/${id}/vote`, data).then(r => r.data);

// ─── Artifacts ───
export const getArtifacts = (projectId) => api.get("/artifacts", { params: projectId ? { project_id: projectId } : {} }).then(r => Array.isArray(r.data) ? r.data : []);
export const getArtifact = (id) => api.get(`/artifacts/${id}`).then(r => r.data);

// ─── Execution ───
export const executeProject = (projectId) => api.post("/execute", { project_id: projectId }).then(r => r.data);

// ─── Chat ───
export const chatWithAgent = (data) => api.post("/chat", data).then(r => r.data);
export const getChatHistory = () => api.get("/chat/history").then(r => r.data);

// ─── Budget ───
export const getBudgetSummary = () => api.get("/budget/summary").then(r => r.data);
export const getBudgetByProject = () => api.get("/budget/projects").then(r => r.data);

// ─── Models ───
export const getModels = () => api.get("/models").then(r => r.data);
export const updateModelConfig = (data) => api.post("/models/config", data).then(r => r.data);
export const pullModel = (data) => api.post("/models/pull", data).then(r => r.data);
export const testModel = (name) => api.get(`/models/test/${encodeURIComponent(name)}`).then(r => r.data);

// ─── Artifact Rendering ───
export const renderArtifact = (data) => api.post("/artifacts/render", data).then(r => r.data);
export const downloadArtifact = (id) => `${API}/artifacts/${id}/download`;

// ─── Testing Centre (development-only; token is never persisted in browser storage) ───
const testingHeaders = (token) => ({ headers: { "X-Testing-Token": token } });
export const getTestingConfig = (token) =>
  api.get("/testing/config", testingHeaders(token)).then(r => r.data);
export const getTestingScans = (token) =>
  api.get("/testing/scans", testingHeaders(token)).then(r => Array.isArray(r.data) ? r.data : []);
export const createTestingScan = (data, token) =>
  api.post("/testing/scans", data, testingHeaders(token)).then(r => r.data);
export const getTestingEvidence = (id, token) =>
  api.get(`/testing/evidence/${encodeURIComponent(id)}`, testingHeaders(token)).then(r => r.data);
export const getTestingAgents = (token) =>
  api.get("/testing/agents", testingHeaders(token)).then(r => r.data);
export const getTestingReviews = (scanId, token) =>
  api.get(`/testing/scans/${encodeURIComponent(scanId)}/reviews`, testingHeaders(token)).then(r => Array.isArray(r.data) ? r.data : []);
export const createTestingReview = (scanId, useAi, token) =>
  api.post(`/testing/scans/${encodeURIComponent(scanId)}/reviews`, { use_ai: useAi }, testingHeaders(token)).then(r => r.data);
export const getTestingRepairs = (token) =>
  api.get("/testing/repairs", testingHeaders(token)).then(r => Array.isArray(r.data) ? r.data : []);
export const createTestingRepair = (scanId, findingId, token) =>
  api.post("/testing/scans/" + encodeURIComponent(scanId) + "/repairs",
    { finding_id: findingId }, testingHeaders(token)).then(r => r.data);
export const verifyTestingRepair = (repairId, retestScanId, token) =>
  api.post("/testing/repairs/" + encodeURIComponent(repairId) + "/verify",
    { retest_scan_id: retestScanId }, testingHeaders(token)).then(r => r.data);
export const publishTestingRepairPR = (repairId, payload, token, approvalToken) =>
  api.post("/testing/repairs/" + encodeURIComponent(repairId) + "/publish-pr",
    payload, { headers: { "X-Testing-Token": token, "X-Repair-Approval-Token": approvalToken } }).then(r => r.data);

// ─── Stage 6A customer Testing Centre (separate from operator access) ───
const customerHeaders = (token, workspaceId) => ({
  headers: {
    Authorization: "Bearer " + token,
    ...(workspaceId ? { "X-Workspace-ID": workspaceId } : {}),
  },
});
export const registerTestingAccount = (data) =>
  api.post("/customer-testing/auth/register", data).then(r => r.data);
export const loginTestingAccount = (data) =>
  api.post("/customer-testing/auth/login", data).then(r => r.data);
export const getCustomerTestingMe = (token) =>
  api.get("/customer-testing/auth/me", customerHeaders(token)).then(r => r.data);
export const getCustomerWorkspaces = (token) =>
  api.get("/customer-testing/workspaces", customerHeaders(token)).then(r => r.data);
export const createCustomerWorkspace = (name, token) =>
  api.post("/customer-testing/workspaces", { name }, customerHeaders(token)).then(r => r.data);
export const getCustomerDomains = (token, workspaceId) =>
  api.get("/customer-testing/domains", customerHeaders(token, workspaceId)).then(r => r.data);
export const addCustomerDomain = (hostname, token, workspaceId) =>
  api.post("/customer-testing/domains", { hostname }, customerHeaders(token, workspaceId)).then(r => r.data);
export const verifyCustomerDomain = (id, token, workspaceId) =>
  api.post("/customer-testing/domains/" + encodeURIComponent(id) + "/verify",
    {}, customerHeaders(token, workspaceId)).then(r => r.data);
export const getCustomerJobs = (token, workspaceId) =>
  api.get("/customer-testing/jobs", customerHeaders(token, workspaceId)).then(r => r.data);
export const submitCustomerJob = (domainId, url, token, workspaceId) =>
  api.post("/customer-testing/jobs", { domain_id: domainId, url, test_type: "availability" },
    customerHeaders(token, workspaceId)).then(r => r.data);

// ─── WebSocket ───
export const getWsUrl = (projectId) => {
  const base = BACKEND_URL || window.location.origin.replace(":3000", ":12000");
  const wsBase = base
    .replace("https://", "wss://")
    .replace("http://", "ws://");
  return `${wsBase}/api/ws/${projectId}`;
};

export const AGENT_META = {
  ceo: { name: "Ivy", title: "CEO", color: "#FFFFFF", icon: "Crown" },
  cfo: { name: "Meridian", title: "CFO", color: "#FFD700", icon: "DollarSign" },
  hr: { name: "Harmony", title: "HR", color: "#F472B6", icon: "Users" },
  ux: { name: "Prism", title: "UI/UX", color: "#A78BFA", icon: "Palette" },
  developer: { name: "Cipher", title: "Developer", color: "#38BDF8", icon: "Code" },
  frontend: { name: "Pixel", title: "Frontend", color: "#38BDF8", icon: "Monitor" },
  backend: { name: "Forge", title: "Backend", color: "#F97316", icon: "Server" },
  devops: { name: "Sentinel", title: "DevOps", color: "#22C55E", icon: "Terminal" },
};

export default api;

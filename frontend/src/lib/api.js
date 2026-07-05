import axios from "axios";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || (window.location.origin.includes("vercel.app") ? "https://rasalilabs.onrender.com" : window.location.origin.replace(":3000", ":4001"));
const API = `${BACKEND_URL}/api`;

const api = axios.create({ baseURL: API });

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

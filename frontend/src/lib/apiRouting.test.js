import { BACKEND_URL, getWsUrl, getLegacyWsProtocols, setLegacyOperatorGateRequired, clearLegacyOperatorToken } from "./api";

test("REST and WebSocket share the configured secured backend", () => {
  expect(BACKEND_URL).not.toContain("rasalilabs.onrender.com");
  expect(BACKEND_URL).toMatch(/^https:\/\//);
  const socket = getWsUrl("project-01");
  const apiUrl = new URL(BACKEND_URL);
  const wsUrl = new URL(socket);
  expect(wsUrl.hostname).toBe(apiUrl.hostname);
  expect(wsUrl.pathname).toBe("/api/ws/project-01");
  expect(wsUrl.protocol).toBe("wss:");
});

test("private agent sockets are not assigned an operator credential until unlock", () => {
  clearLegacyOperatorToken();
  setLegacyOperatorGateRequired(true);
  expect(getLegacyWsProtocols()).toEqual([]);
});

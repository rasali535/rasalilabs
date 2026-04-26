#!/usr/bin/env python3
"""
Backend API Testing for Autonomous AI Company Workflow Engine
Tests all API endpoints with comprehensive validation
"""

import requests
import json
import sys
from datetime import datetime
from typing import Dict, Any, List

class APITester:
    def __init__(self, base_url: str = "http://localhost:12000"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.project_id = None
        self.meeting_id = None
        self.task_id = None
        self.decision_id = None
        self.html_artifact_id = None

    def log_test(self, name: str, success: bool, details: str = "", response_data: Any = None):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"[PASS] {name}")
        else:
            print(f"[FAIL] {name} - {details}")
        
        # Convert response_data to JSON-serializable format
        serializable_data = None
        if response_data is not None:
            try:
                if hasattr(response_data, 'json'):
                    serializable_data = response_data.json()
                elif isinstance(response_data, (dict, list, str, int, float, bool)):
                    serializable_data = response_data
                else:
                    serializable_data = str(response_data)
            except:
                serializable_data = str(response_data)
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details,
            "response_data": serializable_data
        })

    def test_health_endpoint(self):
        """Test GET /api/health"""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=10)
            success = response.status_code == 200
            data = response.json() if success else {}
            
            if success:
                # Validate health response structure including model routing info
                required_fields = ["status", "ollama_available", "routing_mode", "reasoning_model", "coding_model"]
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    success = False
                    self.log_test("Health endpoint", success, f"Missing model routing fields: {missing_fields}", data)
                    return success
                required_fields = ["status", "ollama_available", "mode"]
                missing_fields = [f for f in required_fields if f not in data]
                if missing_fields:
                    success = False
                    details = f"Missing fields: {missing_fields}"
                else:
                    details = f"Status: {data.get('status')}, Mode: {data.get('mode')}"
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("Health Check", success, details, data)
            return success
        except Exception as e:
            self.log_test("Health Check", False, str(e))
            return False

    def test_agents_endpoint(self):
        """Test GET /api/agents - should return 8 agents"""
        try:
            response = requests.get(f"{self.api_url}/agents", timeout=10)
            success = response.status_code == 200
            
            if success:
                agents = response.json()
                if len(agents) == 8:
                    # Validate agent structure
                    required_roles = {"ceo", "cfo", "hr", "ux", "developer", "frontend", "backend", "devops"}
                    agent_roles = {agent.get("role") for agent in agents}
                    if agent_roles == required_roles:
                        details = f"All 8 agents found with correct roles"
                    else:
                        success = False
                        details = f"Missing roles: {required_roles - agent_roles}"
                else:
                    success = False
                    details = f"Expected 8 agents, got {len(agents)}"
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("Get Agents", success, details, response.json() if success else None)
            return success
        except Exception as e:
            self.log_test("Get Agents", False, str(e))
            return False

    def test_stats_endpoint(self):
        """Test GET /api/stats"""
        try:
            response = requests.get(f"{self.api_url}/stats", timeout=10)
            success = response.status_code == 200
            
            if success:
                stats = response.json()
                required_fields = ["projects", "tasks", "meetings", "messages", "decisions", "artifacts"]
                missing_fields = [f for f in required_fields if f not in stats]
                if missing_fields:
                    success = False
                    details = f"Missing fields: {missing_fields}"
                else:
                    details = f"Projects: {stats.get('projects', {}).get('total', 0)}, Tasks: {stats.get('tasks', {}).get('total', 0)}"
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("Get Stats", success, details, stats if success else None)
            return success
        except Exception as e:
            self.log_test("Get Stats", False, str(e))
            return False

    def test_create_project(self):
        """Test POST /api/projects - creates project and triggers kickoff"""
        try:
            project_data = {
                "goal": "Test project for API validation",
                "output_format": "html"
            }
            response = requests.post(f"{self.api_url}/projects", json=project_data, timeout=15)
            success = response.status_code == 200
            
            if success:
                project = response.json()
                if "id" in project and "goal" in project:
                    self.project_id = project["id"]
                    details = f"Project created with ID: {self.project_id}"
                else:
                    success = False
                    details = "Invalid project response structure"
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("Create Project", success, details, project if success else None)
            return success
        except Exception as e:
            self.log_test("Create Project", False, str(e))
            return False

    def test_get_projects(self):
        """Test GET /api/projects"""
        try:
            response = requests.get(f"{self.api_url}/projects", timeout=10)
            success = response.status_code == 200
            
            if success:
                projects = response.json()
                details = f"Found {len(projects)} projects"
                if self.project_id:
                    # Check if our created project exists
                    project_ids = [p.get("id") for p in projects]
                    if self.project_id not in project_ids:
                        success = False
                        details += f", but created project {self.project_id} not found"
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("Get Projects", success, details, projects if success else None)
            return success
        except Exception as e:
            self.log_test("Get Projects", False, str(e))
            return False

    def test_get_meetings(self):
        """Test GET /api/meetings"""
        try:
            response = requests.get(f"{self.api_url}/meetings", timeout=10)
            success = response.status_code == 200
            
            if success:
                meetings = response.json()
                details = f"Found {len(meetings)} meetings"
                if meetings and self.project_id:
                    # Look for kickoff meeting for our project
                    project_meetings = [m for m in meetings if m.get("project_id") == self.project_id]
                    if project_meetings:
                        self.meeting_id = project_meetings[0]["id"]
                        details += f", including kickoff for project {self.project_id}"
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("Get Meetings", success, details, meetings if success else None)
            return success
        except Exception as e:
            self.log_test("Get Meetings", False, str(e))
            return False

    def test_get_messages(self):
        """Test GET /api/messages"""
        try:
            response = requests.get(f"{self.api_url}/messages", timeout=10)
            success = response.status_code == 200
            
            if success:
                messages = response.json()
                details = f"Found {len(messages)} messages"
                if self.meeting_id:
                    # Check for messages in our meeting
                    meeting_messages = [m for m in messages if m.get("meeting_id") == self.meeting_id]
                    details += f", {len(meeting_messages)} in our meeting"
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("Get Messages", success, details, messages if success else None)
            return success
        except Exception as e:
            self.log_test("Get Messages", False, str(e))
            return False

    def test_get_threads(self):
        """Test GET /api/threads"""
        try:
            response = requests.get(f"{self.api_url}/threads", timeout=10)
            success = response.status_code == 200
            
            if success:
                threads = response.json()
                details = f"Found {len(threads)} conversation threads"
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("Get Threads", success, details, threads if success else None)
            return success
        except Exception as e:
            self.log_test("Get Threads", False, str(e))
            return False

    def test_get_tasks(self):
        """Test GET /api/tasks"""
        try:
            response = requests.get(f"{self.api_url}/tasks", timeout=10)
            success = response.status_code == 200
            
            if success:
                tasks = response.json()
                details = f"Found {len(tasks)} tasks"
                if self.project_id:
                    # Check for tasks in our project
                    project_tasks = [t for t in tasks if t.get("project_id") == self.project_id]
                    if project_tasks:
                        self.task_id = project_tasks[0]["id"]
                        details += f", {len(project_tasks)} for our project"
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("Get Tasks", success, details, tasks if success else None)
            return success
        except Exception as e:
            self.log_test("Get Tasks", False, str(e))
            return False

    def test_update_task(self):
        """Test PATCH /api/tasks/{id}"""
        if not self.task_id:
            self.log_test("Update Task", False, "No task ID available")
            return False
        
        try:
            update_data = {"status": "in_progress"}
            response = requests.patch(f"{self.api_url}/tasks/{self.task_id}", json=update_data, timeout=10)
            success = response.status_code == 200
            
            if success:
                task = response.json()
                if task.get("status") == "in_progress":
                    details = f"Task {self.task_id} updated to in_progress"
                else:
                    success = False
                    details = f"Task status not updated correctly: {task.get('status')}"
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("Update Task", success, details, task if success else None)
            return success
        except Exception as e:
            self.log_test("Update Task", False, str(e))
            return False

    def test_get_decisions(self):
        """Test GET /api/decisions"""
        try:
            response = requests.get(f"{self.api_url}/decisions", timeout=10)
            success = response.status_code == 200
            
            if success:
                decisions = response.json()
                details = f"Found {len(decisions)} decisions"
                if self.project_id:
                    # Check for decisions in our project
                    project_decisions = [d for d in decisions if d.get("project_id") == self.project_id]
                    if project_decisions:
                        self.decision_id = project_decisions[0]["id"]
                        details += f", {len(project_decisions)} for our project"
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("Get Decisions", success, details, decisions if success else None)
            return success
        except Exception as e:
            self.log_test("Get Decisions", False, str(e))
            return False

    def test_vote_decision(self):
        """Test POST /api/decisions/{id}/vote"""
        if not self.decision_id:
            self.log_test("Vote Decision", False, "No decision ID available")
            return False
        
        try:
            vote_data = {"agent_role": "cfo", "vote": "approved"}
            response = requests.post(f"{self.api_url}/decisions/{self.decision_id}/vote", json=vote_data, timeout=10)
            success = response.status_code == 200
            
            if success:
                decision = response.json()
                votes = decision.get("votes", {})
                if votes.get("cfo") == "approved":
                    details = f"CFO vote recorded successfully"
                else:
                    success = False
                    details = f"Vote not recorded correctly: {votes}"
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("Vote Decision", success, details, decision if success else None)
            return success
        except Exception as e:
            self.log_test("Vote Decision", False, str(e))
            return False

    def test_execute_project(self):
        """Test POST /api/execute"""
        if not self.project_id:
            self.log_test("Execute Project", False, "No project ID available")
            return False
        
        try:
            execute_data = {"project_id": self.project_id}
            response = requests.post(f"{self.api_url}/execute", json=execute_data, timeout=15)
            success = response.status_code == 200
            
            if success:
                result = response.json()
                if result.get("status") == "execution_started":
                    details = f"Execution started for project {self.project_id}"
                else:
                    success = False
                    details = f"Unexpected response: {result}"
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("Execute Project", success, details, result if success else None)
            return success
        except Exception as e:
            self.log_test("Execute Project", False, str(e))
            return False

    def test_get_artifacts(self):
        """Test GET /api/artifacts"""
        try:
            response = requests.get(f"{self.api_url}/artifacts", timeout=10)
            success = response.status_code == 200
            
            if success:
                artifacts = response.json()
                details = f"Found {len(artifacts)} artifacts"
                if self.project_id:
                    # Check for artifacts in our project
                    project_artifacts = [a for a in artifacts if a.get("project_id") == self.project_id]
                    details += f", {len(project_artifacts)} for our project"
                    # Store HTML artifact ID for rendering tests
                    for artifact in project_artifacts:
                        if artifact.get("artifact_type") == "html":
                            self.html_artifact_id = artifact["id"]
                            break
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("Get Artifacts", success, details, artifacts if success else None)
            return success
        except Exception as e:
            self.log_test("Get Artifacts", False, str(e))
            return False

    def test_chat_with_agent(self):
        """Test POST /api/chat - user sends message to agent"""
        try:
            chat_data = {
                "to_agent": "ceo",
                "content": "Hello, I need to discuss the project status.",
                "project_id": self.project_id
            }
            response = requests.post(f"{self.api_url}/chat", json=chat_data, timeout=15)
            success = response.status_code == 200
            
            if success:
                result = response.json()
                required_fields = ["thread_id", "user_message", "agent_response"]
                missing_fields = [f for f in required_fields if f not in result]
                if missing_fields:
                    success = False
                    details = f"Missing fields: {missing_fields}"
                else:
                    user_msg = result["user_message"]
                    agent_msg = result["agent_response"]
                    if (user_msg.get("from_agent") == "user" and 
                        agent_msg.get("from_agent") == "ceo" and
                        agent_msg.get("content")):
                        details = f"Chat successful - Agent responded: {agent_msg['content'][:50]}..."
                    else:
                        success = False
                        details = "Invalid chat response structure"
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("Chat with Agent", success, details, result if success else None)
            return success
        except Exception as e:
            self.log_test("Chat with Agent", False, str(e))
            return False

    def test_get_chat_history(self):
        """Test GET /api/chat/history - returns chat history"""
        try:
            response = requests.get(f"{self.api_url}/chat/history", timeout=10)
            success = response.status_code == 200
            
            if success:
                history = response.json()
                details = f"Found {len(history)} chat messages"
                # Check if our recent chat message is in history
                user_messages = [msg for msg in history if msg.get("from_agent") == "user"]
                agent_messages = [msg for msg in history if msg.get("to_agent") == "user"]
                details += f" ({len(user_messages)} from user, {len(agent_messages)} to user)"
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("Get Chat History", success, details, history if success else None)
            return success
        except Exception as e:
            self.log_test("Get Chat History", False, str(e))
            return False

    def test_budget_summary(self):
        """Test GET /api/budget/summary - returns budget summary"""
        try:
            response = requests.get(f"{self.api_url}/budget/summary", timeout=10)
            success = response.status_code == 200
            
            if success:
                summary = response.json()
                required_fields = ["total_budget", "total_spent", "remaining", "utilization_pct", "by_department", "by_agent"]
                missing_fields = [f for f in required_fields if f not in summary]
                if missing_fields:
                    success = False
                    details = f"Missing fields: {missing_fields}"
                else:
                    details = f"Budget: ${summary['total_budget']}, Spent: ${summary['total_spent']}, Utilization: {summary['utilization_pct']}%"
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("Get Budget Summary", success, details, summary if success else None)
            return success
        except Exception as e:
            self.log_test("Get Budget Summary", False, str(e))
            return False

    def test_budget_projects(self):
        """Test GET /api/budget/projects - returns per-project budget breakdown"""
        try:
            response = requests.get(f"{self.api_url}/budget/projects", timeout=10)
            success = response.status_code == 200
            
            if success:
                projects = response.json()
                details = f"Found budget data for {len(projects)} projects"
                if projects:
                    # Validate structure of first project
                    project = projects[0]
                    required_fields = ["project_id", "goal", "status", "budget", "spent", "remaining"]
                    missing_fields = [f for f in required_fields if f not in project]
                    if missing_fields:
                        success = False
                        details += f", but missing fields: {missing_fields}"
                    else:
                        details += f", first project budget: ${project['budget']}"
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("Get Budget Projects", success, details, projects if success else None)
            return success
        except Exception as e:
            self.log_test("Get Budget Projects", False, str(e))
            return False

    def test_render_artifact_png(self):
        """Test POST /api/artifacts/render with render_type=png"""
        if not hasattr(self, 'html_artifact_id') or not self.html_artifact_id:
            self.log_test("Render Artifact PNG", False, "No HTML artifact ID available")
            return False
        
        try:
            render_data = {
                "artifact_id": self.html_artifact_id,
                "render_type": "png"
            }
            response = requests.post(f"{self.api_url}/artifacts/render", json=render_data, timeout=30)
            success = response.status_code == 200
            
            if success:
                result = response.json()
                if (result.get("artifact_type") == "png" and 
                    result.get("content") and 
                    result.get("name")):
                    details = f"PNG rendered successfully: {result['name']}"
                else:
                    success = False
                    details = "Invalid PNG render response structure"
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("Render Artifact PNG", success, details, result if success else None)
            return success
        except Exception as e:
            self.log_test("Render Artifact PNG", False, str(e))
            return False

    def test_render_artifact_pdf(self):
        """Test POST /api/artifacts/render with render_type=pdf"""
        if not hasattr(self, 'html_artifact_id') or not self.html_artifact_id:
            self.log_test("Render Artifact PDF", False, "No HTML artifact ID available")
            return False
        
        try:
            render_data = {
                "artifact_id": self.html_artifact_id,
                "render_type": "pdf"
            }
            response = requests.post(f"{self.api_url}/artifacts/render", json=render_data, timeout=30)
            success = response.status_code == 200
            
            if success:
                result = response.json()
                if (result.get("artifact_type") == "pdf" and 
                    result.get("content") and 
                    result.get("name")):
                    details = f"PDF rendered successfully: {result['name']}"
                else:
                    success = False
                    details = "Invalid PDF render response structure"
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("Render Artifact PDF", success, details, result if success else None)
            return success
        except Exception as e:
            self.log_test("Render Artifact PDF", False, str(e))
            return False

    def test_websocket_connection(self):
        """Test WebSocket endpoint at /api/ws/{project_id}"""
        if not self.project_id:
            self.log_test("WebSocket Connection", False, "No project ID available")
            return False
        
        try:
            import websocket
            import threading
            import time
            
            ws_url = self.base_url.replace("https://", "wss://").replace("http://", "ws://")
            ws_url += f"/api/ws/{self.project_id}"
            
            connection_success = False
            error_msg = ""
            
            def on_open(ws):
                nonlocal connection_success
                connection_success = True
            
            def on_error(ws, error):
                nonlocal error_msg
                error_msg = str(error)
            
            def on_close(ws, close_status_code, close_msg):
                pass
            
            ws = websocket.WebSocketApp(ws_url,
                                      on_open=on_open,
                                      on_error=on_error,
                                      on_close=on_close)
            
            # Run WebSocket in a separate thread
            wst = threading.Thread(target=ws.run_forever)
            wst.daemon = True
            wst.start()
            
            # Wait for connection
            time.sleep(2)
            ws.close()
            
            if connection_success:
                details = f"WebSocket connection successful to {ws_url}"
                success = True
            else:
                details = f"WebSocket connection failed: {error_msg}"
                success = False
            
            self.log_test("WebSocket Connection", success, details)
            return success
        except ImportError:
            # websocket-client not available, skip test
            self.log_test("WebSocket Connection", True, "Skipped - websocket-client not available")
            return True
        except Exception as e:
            self.log_test("WebSocket Connection", False, str(e))
            return False

    def test_get_models(self):
        """Test GET /api/models returns complete config"""
        try:
            response = requests.get(f"{self.api_url}/models", timeout=10)
            success = response.status_code == 200
            data = response.json() if success else {}
            
            if success:
                # Validate models response structure
                required_sections = ["config", "ollama_available", "available_models", "routing_table"]
                missing_sections = [section for section in required_sections if section not in data]
                if missing_sections:
                    success = False
                    details = f"Missing sections: {missing_sections}"
                else:
                    # Verify routing table has all 8 agents
                    expected_agents = ["ceo", "cfo", "hr", "ux", "developer", "frontend", "backend", "devops"]
                    routing_table = data.get('routing_table', {})
                    missing_agents = [agent for agent in expected_agents if agent not in routing_table]
                    if missing_agents:
                        success = False
                        details = f"Missing agents in routing table: {missing_agents}"
                    else:
                        details = f"Complete config with {len(routing_table)} agents, Ollama: {data.get('ollama_available')}"
            else:
                details = f"HTTP {response.status_code}: {response.text[:100]}"
            
            self.log_test("Get Models Config", success, details, data)
            return success
        except Exception as e:
            self.log_test("Get Models Config", False, str(e))
            return False

    def test_update_model_config(self):
        """Test POST /api/models/config updates configuration"""
        try:
            test_config = {
                "mode": "simulation",
                "reasoning_model": "test-llama",
                "coding_model": "test-qwen",
                "role_overrides": {"ceo": "custom-model"}
            }
            
            response = requests.post(f"{self.api_url}/models/config", json=test_config, timeout=10)
            success = response.status_code == 200
            data = response.json() if success else {}
            
            if success:
                if data.get("status") == "updated":
                    # Verify the config was actually updated
                    verify_response = requests.get(f"{self.api_url}/models", timeout=10)
                    if verify_response.status_code == 200:
                        verify_data = verify_response.json()
                        config = verify_data.get("config", {})
                        if (config.get("mode") == "simulation" and 
                            config.get("reasoning_model") == "test-llama" and
                            config.get("coding_model") == "test-qwen" and
                            config.get("role_overrides", {}).get("ceo") == "custom-model"):
                            details = "Config updated and persisted successfully"
                        else:
                            success = False
                            details = "Config not persisted correctly"
                    else:
                        success = False
                        details = "Failed to verify config update"
                else:
                    success = False
                    details = f"Unexpected response status: {data.get('status')}"
            else:
                details = f"HTTP {response.status_code}: {response.text[:100]}"
            
            self.log_test("Update Model Config", success, details, data)
            return success
        except Exception as e:
            self.log_test("Update Model Config", False, str(e))
            return False

    def test_model_testing(self):
        """Test GET /api/models/test/{model_name}"""
        try:
            response = requests.get(f"{self.api_url}/models/test/simulation", timeout=15)
            success = response.status_code == 200
            data = response.json() if success else {}
            
            if success:
                if data.get("status") == "error" and "not available" in data.get("detail", ""):
                    details = "Correctly reports Ollama offline"
                elif data.get("status") == "ok":
                    details = f"Model test successful: {data.get('response', '')[:50]}"
                else:
                    details = f"Unexpected test result: {data.get('status')}"
            else:
                details = f"HTTP {response.status_code}: {response.text[:100]}"
            
            self.log_test("Test Model", success, details, data)
            return success
        except Exception as e:
            self.log_test("Test Model", False, str(e))
            return False

    def test_model_pull(self):
        """Test POST /api/models/pull"""
        try:
            response = requests.post(f"{self.api_url}/models/pull", 
                                   json={"model_name": "test-model"}, timeout=10)
            # Expecting 200 (if online) or 503 (if offline)
            success = response.status_code in [200, 503]
            data = response.json() if response.status_code in [200, 503] else {}
            
            if success:
                details = f"Handled model pull request (Status {response.status_code})"
            else:
                details = f"HTTP {response.status_code}: {response.text[:100]}"
            
            self.log_test("Model Pull (Offline)", success, details, data)
            return success
        except Exception as e:
            self.log_test("Model Pull (Offline)", False, str(e))
            return False

    def test_chat_with_model_info(self):
        """Test POST /api/chat returns model_info"""
        try:
            chat_data = {
                "to_agent": "developer",
                "content": "Hello, can you help with a coding task?"
            }
            
            response = requests.post(f"{self.api_url}/chat", json=chat_data, timeout=15)
            success = response.status_code == 200
            data = response.json() if success else {}
            
            if success:
                required_fields = ["thread_id", "user_message", "agent_response", "model_info"]
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    success = False
                    details = f"Missing fields: {missing_fields}"
                else:
                    model_info = data.get("model_info", {})
                    model_info_fields = ["model", "mode", "routing"]
                    missing_model_fields = [field for field in model_info_fields if field not in model_info]
                    if missing_model_fields:
                        success = False
                        details = f"Missing model_info fields: {missing_model_fields}"
                    else:
                        agent_response = data.get("agent_response", {})
                        if "model_used" not in agent_response or "model_mode" not in agent_response:
                            success = False
                            details = "Agent response missing model_used or model_mode fields"
                        else:
                            details = f"Chat with model info: {model_info.get('model')} ({model_info.get('mode')})"
            else:
                details = f"HTTP {response.status_code}: {response.text[:100]}"
            
            self.log_test("Chat with Model Info", success, details, data)
            return success
        except Exception as e:
            self.log_test("Chat with Model Info", False, str(e))
            return False

    def test_messages_include_model_fields(self):
        """Test that messages include model_used and model_mode fields"""
        try:
            response = requests.get(f"{self.api_url}/messages?from_agent=developer", timeout=10)
            success = response.status_code == 200
            data = response if success else []
            
            if success and data:
                messages = data if isinstance(data, list) else []
                if messages:
                    recent_message = messages[0]
                    if "model_used" in recent_message and "model_mode" in recent_message:
                        details = f"Messages include model fields: {recent_message.get('model_used')} ({recent_message.get('model_mode')})"
                    else:
                        success = False
                        details = "Messages missing model_used or model_mode fields"
                else:
                    details = "No messages found to verify model fields"
            else:
                details = f"HTTP {response.status_code}: {response.text[:100]}" if not success else "No messages to check"
            
            self.log_test("Messages Model Fields", success, details, data)
            return success
        except Exception as e:
            self.log_test("Messages Model Fields", False, str(e))
            return False

    def run_all_tests(self):
        """Run all API tests in sequence"""
        print(f"Starting API tests for {self.base_url}")
        print("=" * 60)
        
        # Core endpoints
        self.test_health_endpoint()
        self.test_agents_endpoint()
        self.test_stats_endpoint()
        
        # Project workflow
        self.test_create_project()
        self.test_get_projects()
        
        # Wait a moment for kickoff meeting to be created
        import time
        time.sleep(3)
        
        self.test_get_meetings()
        self.test_get_messages()
        self.test_get_threads()
        self.test_get_tasks()
        self.test_update_task()
        self.test_get_decisions()
        self.test_vote_decision()
        self.test_execute_project()
        
        # Wait for execution to generate artifacts
        time.sleep(5)
        self.test_get_artifacts()
        
        # Test new features
        self.test_chat_with_agent()
        self.test_get_chat_history()
        self.test_budget_summary()
        self.test_budget_projects()
        
        # Test model routing features
        self.test_get_models()
        self.test_update_model_config()
        self.test_model_testing()
        self.test_model_pull()
        self.test_chat_with_model_info()
        self.test_messages_include_model_fields()
        
        # Test artifact rendering (if HTML artifact exists)
        if hasattr(self, 'html_artifact_id') and self.html_artifact_id:
            self.test_render_artifact_png()
            self.test_render_artifact_pdf()
        
        # Test WebSocket connection
        self.test_websocket_connection()
        
        # Print summary
        print("=" * 60)
        if self.tests_passed == self.tests_run:
            print("All tests passed!")
            return True
        else:
            print("Some tests failed. Check details above.")
            return False

def main():
    """Main test runner"""
    tester = APITester()
    success = tester.run_all_tests()
    
    # Save detailed results
    with open("backend_test_results.json", "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_tests": tester.tests_run,
            "passed_tests": tester.tests_passed,
            "success_rate": tester.tests_passed / tester.tests_run if tester.tests_run > 0 else 0,
            "results": tester.test_results
        }, f, indent=2)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
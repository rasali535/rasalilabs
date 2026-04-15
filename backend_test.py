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
    def __init__(self, base_url: str = "https://autonomous-agents-23.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.project_id = None
        self.meeting_id = None
        self.task_id = None
        self.decision_id = None

    def log_test(self, name: str, success: bool, details: str = "", response_data: Any = None):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name} - {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details,
            "response_data": response_data
        })

    def test_health_endpoint(self):
        """Test GET /api/health"""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=10)
            success = response.status_code == 200
            data = response.json() if success else {}
            
            if success:
                # Validate health response structure
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
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("Get Artifacts", success, details, artifacts if success else None)
            return success
        except Exception as e:
            self.log_test("Get Artifacts", False, str(e))
            return False

    def run_all_tests(self):
        """Run all API tests in sequence"""
        print(f"🚀 Starting API tests for {self.base_url}")
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
        time.sleep(2)
        
        self.test_get_meetings()
        self.test_get_messages()
        self.test_get_threads()
        self.test_get_tasks()
        self.test_update_task()
        self.test_get_decisions()
        self.test_vote_decision()
        self.test_execute_project()
        
        # Wait for execution to generate artifacts
        time.sleep(3)
        self.test_get_artifacts()
        
        # Print summary
        print("=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return True
        else:
            print("❌ Some tests failed. Check details above.")
            return False

def main():
    """Main test runner"""
    tester = APITester()
    success = tester.run_all_tests()
    
    # Save detailed results
    with open("/tmp/backend_test_results.json", "w") as f:
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
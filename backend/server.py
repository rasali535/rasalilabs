from fastapi import FastAPI, APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import httpx
import json
import asyncio
import tempfile
import base64
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
from enum import Enum

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434')
LLAMA_MODEL = os.environ.get('LLAMA_MODEL', 'llama3.2')
QWEN_MODEL = os.environ.get('QWEN_MODEL', 'qwen2.5-coder')

# ─── Model Routing Config (mutable at runtime) ───
model_config = {
    "ollama_url": OLLAMA_URL,
    "reasoning_model": LLAMA_MODEL,
    "coding_model": QWEN_MODEL,
    "role_overrides": {},  # e.g. {"cfo": "mistral"} to override per-role
    "mode": "auto",  # "auto" | "llama_only" | "qwen_only" | "simulation"
}

# Cache for Ollama availability
_ollama_cache = {"available": None, "checked_at": 0, "models": []}

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def load_model_config():
    """Load persisted model config from MongoDB."""
    try:
        doc = await db.system_config.find_one({"key": "model_config"}, {"_id": 0})
        if doc and "value" in doc:
            stored = doc["value"]
            model_config["ollama_url"] = stored.get("ollama_url", model_config["ollama_url"])
            model_config["reasoning_model"] = stored.get("reasoning_model", model_config["reasoning_model"])
            model_config["coding_model"] = stored.get("coding_model", model_config["coding_model"])
            model_config["mode"] = stored.get("mode", model_config["mode"])
            model_config["role_overrides"] = stored.get("role_overrides", {})
            logger.info(f"Loaded model config: mode={model_config['mode']}, reasoning={model_config['reasoning_model']}, coding={model_config['coding_model']}")
    except Exception as e:
        logger.warning(f"Failed to load model config: {e}")

# ─── Enums ───
class AgentRole(str, Enum):
    CEO = "ceo"
    CFO = "cfo"
    HR = "hr"
    UX = "ux"
    DEVELOPER = "developer"
    FRONTEND = "frontend"
    BACKEND = "backend"
    DEVOPS = "devops"

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    BLOCKED = "blocked"

class MeetingType(str, Enum):
    KICKOFF = "kickoff"
    APPROVAL = "approval"
    BLOCKER = "blocker"
    HIRING = "hiring"
    DELIVERY = "delivery"

class DecisionStatus(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"
    DELEGATED = "delegated"
    BLOCKED = "blocked"
    PENDING = "pending"

class ThreadType(str, Enum):
    DIRECT = "direct"
    DEPARTMENT = "department"
    CROSS_FUNCTIONAL = "cross_functional"
    ESCALATION = "escalation"
    REVIEW = "review"

# ─── Pydantic Models ───
class AgentOut(BaseModel):
    id: str
    role: str
    name: str
    title: str
    status: str = "active"
    skills: List[str] = []
    department: str = ""
    description: str = ""

class ProjectCreate(BaseModel):
    goal: str
    output_format: str = "html"
    constraints: Optional[Dict[str, Any]] = None

class ProjectOut(BaseModel):
    id: str
    goal: str
    output_format: str
    status: str
    constraints: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str

class MeetingCreate(BaseModel):
    project_id: str
    meeting_type: str = "kickoff"
    title: str = ""
    agenda_items: List[str] = []

class MeetingOut(BaseModel):
    id: str
    project_id: str
    meeting_type: str
    title: str
    status: str
    agenda_items: List[str]
    participants: List[str]
    created_at: str
    summary: Optional[str] = None

class TaskCreate(BaseModel):
    project_id: str
    title: str
    description: str = ""
    assigned_to: Optional[str] = None
    priority: str = "medium"
    depends_on: List[str] = []

class TaskOut(BaseModel):
    id: str
    project_id: str
    title: str
    description: str
    status: str
    assigned_to: Optional[str] = None
    priority: str
    depends_on: List[str]
    created_at: str
    output: Optional[str] = None

class MessageCreate(BaseModel):
    thread_id: Optional[str] = None
    project_id: Optional[str] = None
    meeting_id: Optional[str] = None
    from_agent: str
    to_agent: Optional[str] = None
    content: str
    thread_type: str = "direct"

class MessageOut(BaseModel):
    id: str
    thread_id: str
    project_id: Optional[str] = None
    meeting_id: Optional[str] = None
    from_agent: str
    to_agent: Optional[str] = None
    content: str
    thread_type: str
    model_used: Optional[str] = None
    model_mode: Optional[str] = None
    created_at: str

class DecisionCreate(BaseModel):
    meeting_id: str
    project_id: str
    title: str
    description: str = ""
    decided_by: str = "ceo"

class DecisionOut(BaseModel):
    id: str
    meeting_id: str
    project_id: str
    title: str
    description: str
    status: str
    decided_by: str
    votes: Dict[str, str] = {}
    created_at: str

class VoteCreate(BaseModel):
    agent_role: str
    vote: str  # approved, rejected, needs_revision

class ArtifactOut(BaseModel):
    id: str
    project_id: str
    task_id: Optional[str] = None
    name: str
    artifact_type: str
    content: Optional[str] = None
    file_path: Optional[str] = None
    created_at: str

class ExecuteProjectRequest(BaseModel):
    project_id: str

class UserChatRequest(BaseModel):
    to_agent: str
    content: str
    project_id: Optional[str] = None

class RenderArtifactRequest(BaseModel):
    artifact_id: str
    render_type: str  # "png" or "pdf"

# ─── WebSocket Manager ───
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, project_id: str):
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = []
        self.active_connections[project_id].append(websocket)

    def disconnect(self, websocket: WebSocket, project_id: str):
        if project_id in self.active_connections:
            self.active_connections[project_id] = [
                c for c in self.active_connections[project_id] if c != websocket
            ]

    async def broadcast(self, project_id: str, data: dict):
        if project_id in self.active_connections:
            dead = []
            for connection in self.active_connections[project_id]:
                try:
                    await connection.send_json(data)
                except Exception:
                    dead.append(connection)
            for d in dead:
                self.active_connections[project_id].remove(d)

ws_manager = ConnectionManager()

# Artifacts directory
ARTIFACTS_DIR = Path("/app/artifacts")
ARTIFACTS_DIR.mkdir(exist_ok=True)

# ─── Agent Registry ───
AGENTS = {
    "ceo": {
        "id": "agent-ceo",
        "role": "ceo",
        "name": "Atlas",
        "title": "Chief Executive Officer",
        "status": "active",
        "skills": ["strategy", "leadership", "planning", "delegation"],
        "department": "executive",
        "description": "Leads overall company strategy, chairs boardroom meetings, and makes final decisions."
    },
    "cfo": {
        "id": "agent-cfo",
        "role": "cfo",
        "name": "Meridian",
        "title": "Chief Financial Officer",
        "status": "active",
        "skills": ["budgeting", "cost_analysis", "risk_assessment", "financial_planning"],
        "department": "finance",
        "description": "Manages budgets, approves costs, and assesses financial risks for projects."
    },
    "hr": {
        "id": "agent-hr",
        "role": "hr",
        "name": "Harmony",
        "title": "Head of Human Resources",
        "status": "active",
        "skills": ["team_management", "capacity_planning", "hiring", "agent_lifecycle"],
        "department": "people",
        "description": "Manages agent activation, team capacity, and resource allocation."
    },
    "ux": {
        "id": "agent-ux",
        "role": "ux",
        "name": "Prism",
        "title": "UI/UX Lead",
        "status": "active",
        "skills": ["design", "wireframing", "prototyping", "user_research"],
        "department": "design",
        "description": "Creates design specs, wireframes, and ensures quality user experiences."
    },
    "developer": {
        "id": "agent-developer",
        "role": "developer",
        "name": "Cipher",
        "title": "Senior Developer",
        "status": "active",
        "skills": ["full_stack", "architecture", "code_review", "testing"],
        "department": "engineering",
        "description": "Handles complex coding tasks, architecture decisions, and code reviews."
    },
    "frontend": {
        "id": "agent-frontend",
        "role": "frontend",
        "name": "Pixel",
        "title": "Frontend Engineer",
        "status": "active",
        "skills": ["react", "css", "html", "javascript", "responsive_design"],
        "department": "engineering",
        "description": "Builds user interfaces, implements designs, and handles frontend logic."
    },
    "backend": {
        "id": "agent-backend",
        "role": "backend",
        "name": "Forge",
        "title": "Backend Engineer",
        "status": "active",
        "skills": ["python", "apis", "databases", "server_architecture"],
        "department": "engineering",
        "description": "Develops APIs, manages databases, and builds server-side logic."
    },
    "devops": {
        "id": "agent-devops",
        "role": "devops",
        "name": "Sentinel",
        "title": "DevOps Engineer",
        "status": "active",
        "skills": ["deployment", "ci_cd", "docker", "monitoring", "infrastructure"],
        "department": "operations",
        "description": "Manages deployments, infrastructure, CI/CD pipelines, and system reliability."
    }
}

# ─── Ollama / LLM Service ───
import time as _time

async def check_ollama_available():
    """Check Ollama with 10s cache to avoid hammering."""
    now = _time.time()
    if _ollama_cache["available"] is not None and (now - _ollama_cache["checked_at"]) < 10:
        return _ollama_cache["available"]
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{model_config['ollama_url']}/api/tags")
            if r.status_code == 200:
                data = r.json()
                _ollama_cache["models"] = [m["name"] for m in data.get("models", [])]
                _ollama_cache["available"] = True
                _ollama_cache["checked_at"] = now
                return True
    except Exception:
        pass
    _ollama_cache["available"] = False
    _ollama_cache["checked_at"] = now
    _ollama_cache["models"] = []
    return False

async def list_ollama_models():
    """Fetch available models from Ollama."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{model_config['ollama_url']}/api/tags")
            if r.status_code == 200:
                return r.json().get("models", [])
    except Exception:
        pass
    return []

def resolve_model_for(role: str, task_type: str) -> tuple:
    """Determine which model to use for a given role+task_type.
    Returns (model_name, routing_reason)."""
    # Check per-role overrides first
    if role in model_config.get("role_overrides", {}):
        return model_config["role_overrides"][role], f"role_override:{role}"

    mode = model_config.get("mode", "auto")
    if mode == "simulation":
        return "simulation", "forced_simulation"
    if mode == "llama_only":
        return model_config["reasoning_model"], "llama_only_mode"
    if mode == "qwen_only":
        return model_config["coding_model"], "qwen_only_mode"

    # Auto mode: route by role and task
    coding_roles = {"developer", "frontend", "backend"}
    coding_tasks = {"code", "implementation", "debug", "test"}

    if role in coding_roles and task_type in coding_tasks:
        return model_config["coding_model"], f"auto:coding({role}/{task_type})"
    if task_type in coding_tasks:
        return model_config["coding_model"], f"auto:coding_task({task_type})"

    return model_config["reasoning_model"], f"auto:reasoning({role}/{task_type})"

SIMULATION_RESPONSES = {
    "ceo": {
        "kickoff": "I've reviewed the project goal. Let me outline the scope: we need to define clear deliverables, set milestones, and assign ownership. I'm calling in the relevant team members for a kickoff discussion.",
        "approval": "After reviewing all inputs, I'm approving this plan. The scope is reasonable, budget is within limits, and the team has capacity. Let's proceed with execution.",
        "planning": "Here's my strategic assessment: we should prioritize the core deliverable first, then iterate on secondary features. I recommend a phased approach with clear checkpoints.",
        "review": "The output meets our quality standards. I'm satisfied with the execution. Let's prepare for delivery.",
        "default": "Understood. I'll coordinate with the team and ensure we stay on track."
    },
    "cfo": {
        "kickoff": "From a budget perspective, this project looks feasible. I estimate moderate resource costs. I recommend we keep scope tight to stay within budget.",
        "approval": "Budget allocation approved. The projected costs are within acceptable range. I'll monitor spend throughout execution.",
        "default": "I've assessed the financial implications. The cost-benefit ratio looks favorable for this initiative."
    },
    "hr": {
        "kickoff": "Team capacity check: we have all required roles available and active. No staffing blockers identified. The team is ready to take this on.",
        "approval": "Staffing approved. All assigned agents have bandwidth for this project. I'll monitor workload distribution.",
        "default": "The team is well-equipped for this task. All agents are active and available."
    },
    "ux": {
        "kickoff": "I'll start with a design brief based on the requirements. For the UI, I recommend a clean layout with clear hierarchy and intuitive navigation.",
        "design": "Here's my design specification: Hero section with strong CTA, benefits grid, and clean typography. Using a modern color palette that aligns with brand guidelines.",
        "review": "The implementation matches the design spec. Layout, spacing, and visual hierarchy are on point.",
        "default": "From a design perspective, I recommend focusing on clarity and user experience. Let me prepare a detailed spec."
    },
    "developer": {
        "kickoff": "I've analyzed the technical requirements. The architecture is straightforward. I'll coordinate with frontend and backend on the implementation plan.",
        "code": "Implementation complete. I've followed best practices with clean, modular code. All components are properly structured and tested.",
        "review": "Code review passed. The implementation is clean, well-structured, and follows our coding standards.",
        "default": "I'll handle the technical implementation. The approach is well-defined and achievable within the timeline."
    },
    "frontend": {
        "kickoff": "I can build this quickly using React. I'll follow the UI/UX spec and ensure responsive design across all breakpoints.",
        "code": "Frontend implementation complete. Built with React, includes responsive layout, proper accessibility, and clean component architecture.",
        "default": "I'm ready to implement the frontend. Will coordinate with UI/UX for the design spec."
    },
    "backend": {
        "kickoff": "Backend architecture is clear. I'll set up the API endpoints, data models, and business logic. No complex integrations needed for this scope.",
        "code": "Backend implementation complete. APIs are structured, data validation is in place, and error handling is comprehensive.",
        "default": "I'll handle the server-side implementation. The API design is straightforward."
    },
    "devops": {
        "kickoff": "No deployment blockers. The infrastructure is ready. I'll prepare the build pipeline and artifact generation once development is complete.",
        "approval": "Deployment readiness confirmed. All systems are operational. Ready to release when approved.",
        "default": "Infrastructure is stable. I'll monitor the deployment pipeline and ensure smooth delivery.",
        "chat": "Hi! I'm Sentinel, your DevOps engineer. I handle deployments, CI/CD, Docker, and infrastructure monitoring. How can I help you with operations today?"
    }
}

# User chat response templates for simulation mode
USER_CHAT_RESPONSES = {
    "ceo": "Thank you for reaching out. As CEO, I oversee all company operations and strategy. I've noted your message and will factor it into our planning. Is there a specific project or decision you'd like to discuss?",
    "cfo": "Thanks for your message. I manage all financial aspects including budgets, cost analysis, and resource allocation. I can provide you with budget breakdowns or cost projections for any active project. What financial information do you need?",
    "hr": "Hello! As Head of HR, I manage team capacity, agent availability, and resource allocation. I can tell you about current staffing levels, workload distribution, or help with any team-related concerns. What can I help with?",
    "ux": "Hi there! I'm the UI/UX lead. I handle design specifications, wireframes, and user experience strategy. I can discuss design approaches, review layouts, or create visual specs. What design topic would you like to explore?",
    "developer": "Hey! I'm the senior developer on the team. I handle architecture decisions, code reviews, and complex implementations. I can help with technical questions, code approaches, or system design. What technical challenge are you working on?",
    "frontend": "Hi! I'm the frontend engineer. I specialize in React, CSS, HTML, and responsive design. I can discuss UI implementation, component architecture, or frontend performance. What frontend topic interests you?",
    "backend": "Hello! I'm the backend engineer. I work with Python, APIs, databases, and server architecture. I can help with API design, data modeling, or backend optimization. What server-side question do you have?",
    "devops": "Hi! I'm the DevOps engineer. I manage deployments, CI/CD pipelines, Docker, and infrastructure. I can discuss deployment strategies, monitoring, or system reliability. What ops topic do you need help with?",
}

async def get_agent_response(role: str, context: str, task_type: str = "default") -> dict:
    """Get response from Ollama or simulation.
    Returns {"content": str, "model": str, "routing": str, "mode": str}"""
    model_name, routing_reason = resolve_model_for(role, task_type)

    # Forced simulation mode
    if model_name == "simulation":
        text = _get_simulation_text(role, task_type)
        return {"content": text, "model": "simulation", "routing": routing_reason, "mode": "simulation"}

    ollama_available = await check_ollama_available()

    if ollama_available:
        try:
            agent = AGENTS.get(role, AGENTS["developer"])
            system_prompt = (
                f"You are {agent['name']}, the {agent['title']} of an AI company. "
                f"{agent['description']} Respond concisely and in-character. "
                f"Keep responses under 3 sentences."
            )

            async with httpx.AsyncClient(timeout=60.0) as c:
                r = await c.post(f"{model_config['ollama_url']}/api/generate", json={
                    "model": model_name,
                    "prompt": f"{system_prompt}\n\nContext: {context}\n\nRespond:",
                    "stream": False
                })
                if r.status_code == 200:
                    text = r.json().get("response", "").strip()
                    if text:
                        return {"content": text, "model": model_name, "routing": routing_reason, "mode": "live"}
        except Exception as e:
            logger.warning(f"Ollama call failed for {role} using {model_name}: {e}")

    # Fallback to simulation
    text = _get_simulation_text(role, task_type)
    return {"content": text, "model": "simulation", "routing": routing_reason, "mode": "simulation"}


def _get_simulation_text(role: str, task_type: str) -> str:
    role_responses = SIMULATION_RESPONSES.get(role, SIMULATION_RESPONSES["developer"])
    return role_responses.get(task_type, role_responses.get("default", "Acknowledged. I'll proceed with my assigned responsibilities."))

# ─── Orchestration Engine ───
async def run_kickoff_meeting(project_id: str, goal: str, output_format: str):
    """Automatically run a kickoff meeting for a new project."""
    meeting_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    participants = list(AGENTS.keys())
    
    meeting_doc = {
        "id": meeting_id,
        "project_id": project_id,
        "meeting_type": "kickoff",
        "title": f"Kickoff: {goal[:60]}",
        "status": "in_progress",
        "agenda_items": [
            "Review project goal and scope",
            "Assess budget and resource requirements",
            "Confirm team capacity and availability",
            "Define deliverables and milestones",
            "Approve execution plan"
        ],
        "participants": participants,
        "created_at": now,
        "summary": None
    }
    await db.meetings.insert_one(meeting_doc)
    
    # Generate agent dialogue for kickoff
    dialogue_order = ["ceo", "cfo", "hr", "ux", "frontend", "backend", "devops", "ceo"]
    thread_id = str(uuid.uuid4())
    
    messages = []
    for i, role in enumerate(dialogue_order):
        context = f"Project goal: {goal}. Output format: {output_format}. This is a kickoff meeting. Previous discussion: {'; '.join([m['content'][:80] for m in messages[-3:]])}"
        result = await get_agent_response(role, context, "kickoff")
        
        msg = {
            "id": str(uuid.uuid4()),
            "thread_id": thread_id,
            "project_id": project_id,
            "meeting_id": meeting_id,
            "from_agent": role,
            "to_agent": None,
            "content": result["content"],
            "thread_type": "cross_functional",
            "model_used": result["model"],
            "model_mode": result["mode"],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        messages.append(msg)
        # Broadcast via WebSocket
        await ws_manager.broadcast(project_id, {"type": "message", "data": msg})
        await asyncio.sleep(0.05)
    
    if messages:
        await db.messages.insert_many(messages)
    
    # Create approval decision
    decision_doc = {
        "id": str(uuid.uuid4()),
        "meeting_id": meeting_id,
        "project_id": project_id,
        "title": f"Approve kickoff plan for: {goal[:60]}",
        "description": "Approve the project scope, budget allocation, and team assignment.",
        "status": "approved",
        "decided_by": "ceo",
        "votes": {r: "approved" for r in participants},
        "created_at": now
    }
    await db.decisions.insert_one(decision_doc)
    
    # Auto-generate tasks
    tasks = await generate_project_tasks(project_id, goal, output_format)
    
    # Update meeting status
    await db.meetings.update_one(
        {"id": meeting_id},
        {"$set": {
            "status": "completed",
            "summary": f"Kickoff meeting completed. {len(tasks)} tasks created. All agents approved the plan. Execution begins immediately."
        }}
    )
    
    # Update project status
    await db.projects.update_one(
        {"id": project_id},
        {"$set": {"status": "in_progress", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return meeting_id

async def generate_project_tasks(project_id: str, goal: str, output_format: str) -> list:
    """Generate tasks based on project goal."""
    now = datetime.now(timezone.utc).isoformat()
    
    task_templates = [
        {"title": "Define project scope and requirements", "assigned_to": "ceo", "priority": "high", "description": f"Break down the goal into clear requirements: {goal}"},
        {"title": "Budget assessment and allocation", "assigned_to": "cfo", "priority": "high", "description": "Assess resource costs and allocate budget for the project."},
        {"title": "Team capacity and assignment", "assigned_to": "hr", "priority": "medium", "description": "Verify team availability and assign roles to tasks."},
        {"title": "Create design specification", "assigned_to": "ux", "priority": "high", "description": f"Design the UI/UX for the deliverable. Output format: {output_format}"},
        {"title": "Implement core functionality", "assigned_to": "developer", "priority": "high", "description": "Build the main logic and features as specified."},
        {"title": "Build user interface", "assigned_to": "frontend", "priority": "high", "description": "Implement the frontend based on design specs."},
        {"title": "Develop API and data layer", "assigned_to": "backend", "priority": "medium", "description": "Build backend APIs and data models needed."},
        {"title": "Prepare deployment and artifacts", "assigned_to": "devops", "priority": "medium", "description": f"Package final output as {output_format} and prepare for delivery."},
        {"title": "Quality review and approval", "assigned_to": "ceo", "priority": "high", "description": "Final review of all deliverables before release."},
    ]
    
    tasks = []
    for i, t in enumerate(task_templates):
        task = {
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "title": t["title"],
            "description": t["description"],
            "status": "pending" if i > 0 else "in_progress",
            "assigned_to": t["assigned_to"],
            "priority": t["priority"],
            "depends_on": [],
            "created_at": now,
            "output": None
        }
        tasks.append(task)
    
    if tasks:
        await db.tasks.insert_many(tasks)
    return tasks

async def execute_project(project_id: str):
    """Execute all project tasks autonomously."""
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        return
    
    tasks = await db.tasks.find({"project_id": project_id}, {"_id": 0}).sort("created_at", 1).to_list(100)
    
    for task in tasks:
        if task["status"] == "completed":
            continue
        
        await db.tasks.update_one({"id": task["id"]}, {"$set": {"status": "in_progress"}})
        
        role = task.get("assigned_to", "developer")
        task_type = "code" if role in ["developer", "frontend", "backend"] else "default"
        context = f"Task: {task['title']}. Description: {task['description']}. Project goal: {project['goal']}"
        
        response = await get_agent_response(role, context, task_type)
        
        # Log execution message
        msg = {
            "id": str(uuid.uuid4()),
            "thread_id": str(uuid.uuid4()),
            "project_id": project_id,
            "meeting_id": None,
            "from_agent": role,
            "to_agent": None,
            "content": f"[Task: {task['title']}] {response['content']}",
            "thread_type": "direct",
            "model_used": response["model"],
            "model_mode": response["mode"],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.messages.insert_one(msg)
        
        # Broadcast via WebSocket
        await ws_manager.broadcast(project_id, {"type": "message", "data": msg})
        await ws_manager.broadcast(project_id, {"type": "task_update", "data": {"task_id": task["id"], "status": "completed"}})
        
        await db.tasks.update_one(
            {"id": task["id"]},
            {"$set": {"status": "completed", "output": response["content"]}}
        )
        await asyncio.sleep(0.05)
    
    # Generate artifacts
    await generate_artifacts(project_id, project["goal"], project["output_format"])
    
    # Update project
    await db.projects.update_one(
        {"id": project_id},
        {"$set": {"status": "completed", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

async def generate_artifacts(project_id: str, goal: str, output_format: str):
    """Generate output artifacts based on format."""
    now = datetime.now(timezone.utc).isoformat()
    artifacts = []
    
    fmt = output_format.lower()
    html_content = None
    
    if "html" in fmt or fmt == "html" or "png" in fmt or "pdf" in fmt:
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{goal[:50]}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', sans-serif; background: #0a0a0a; color: #fff; }}
        .hero {{ min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 2rem; text-align: center; }}
        h1 {{ font-size: 3rem; margin-bottom: 1rem; background: linear-gradient(135deg, #0030FF, #00B4D8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        p {{ font-size: 1.25rem; color: #a1a1aa; max-width: 600px; line-height: 1.6; }}
        .cta {{ margin-top: 2rem; padding: 0.75rem 2rem; background: #0030FF; color: white; border: none; border-radius: 4px; font-size: 1rem; cursor: pointer; }}
        .cta:hover {{ background: #0025CC; }}
    </style>
</head>
<body>
    <div class="hero">
        <h1>{goal[:80]}</h1>
        <p>This artifact was autonomously generated by the AI Company Workflow Engine. All agents collaborated to produce this deliverable.</p>
        <button class="cta">Get Started</button>
    </div>
</body>
</html>"""
        if "html" in fmt or fmt == "html" or "png" in fmt or "pdf" in fmt:
            artifacts.append({
                "id": str(uuid.uuid4()),
                "project_id": project_id,
                "task_id": None,
                "name": "output.html",
                "artifact_type": "html",
                "content": html_content,
                "file_path": None,
                "created_at": now
            })
    
    # PNG generation from HTML
    if ("png" in fmt or fmt == "png") and html_content:
        try:
            png_path = await render_html_to_png(html_content, project_id)
            if png_path:
                # Read PNG and encode as base64 for storage
                with open(png_path, "rb") as f:
                    png_b64 = base64.b64encode(f.read()).decode()
                artifacts.append({
                    "id": str(uuid.uuid4()),
                    "project_id": project_id,
                    "task_id": None,
                    "name": "output.png",
                    "artifact_type": "png",
                    "content": png_b64,
                    "file_path": png_path,
                    "created_at": now
                })
        except Exception as e:
            logger.error(f"PNG generation failed: {e}")
    
    # PDF generation
    if ("pdf" in fmt or fmt == "pdf"):
        try:
            pdf_path = await render_to_pdf(goal, project_id)
            if pdf_path:
                with open(pdf_path, "rb") as f:
                    pdf_b64 = base64.b64encode(f.read()).decode()
                artifacts.append({
                    "id": str(uuid.uuid4()),
                    "project_id": project_id,
                    "task_id": None,
                    "name": "output.pdf",
                    "artifact_type": "pdf",
                    "content": pdf_b64,
                    "file_path": pdf_path,
                    "created_at": now
                })
        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
    
    if "json" in fmt or fmt == "json":
        json_content = json.dumps({
            "project_goal": goal,
            "status": "completed",
            "generated_at": now,
            "output_format": output_format,
            "deliverables": ["Project completed successfully by the AI Company team."]
        }, indent=2)
        artifacts.append({
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "task_id": None,
            "name": "output.json",
            "artifact_type": "json",
            "content": json_content,
            "file_path": None,
            "created_at": now
        })
    
    if "code" in fmt or "js" in fmt or "py" in fmt:
        code_content = f"""# Auto-generated code artifact
# Project: {goal}
# Generated by AI Company Workflow Engine

def main():
    print("Project: {goal[:60]}")
    print("Status: Completed")
    print("Generated by autonomous AI workflow")

if __name__ == "__main__":
    main()
"""
        artifacts.append({
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "task_id": None,
            "name": "output.py",
            "artifact_type": "code",
            "content": code_content,
            "file_path": None,
            "created_at": now
        })
    
    # Always generate a summary JSON
    artifacts.append({
        "id": str(uuid.uuid4()),
        "project_id": project_id,
        "task_id": None,
        "name": "project_summary.json",
        "artifact_type": "json",
        "content": json.dumps({
            "project_goal": goal,
            "output_format": output_format,
            "status": "delivered",
            "timestamp": now
        }, indent=2),
        "file_path": None,
        "created_at": now
    })
    
    if artifacts:
        await db.artifacts.insert_many(artifacts)

async def render_html_to_png(html_content: str, project_id: str) -> str:
    """Render HTML to PNG using Playwright."""
    try:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/pw-browsers"
        from playwright.async_api import async_playwright
        png_path = str(ARTIFACTS_DIR / f"{project_id}_output.png")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1280, "height": 720})
            await page.set_content(html_content, wait_until="networkidle")
            await page.screenshot(path=png_path, full_page=True)
            await browser.close()
        
        return png_path
    except Exception as e:
        logger.error(f"Playwright PNG render failed: {e}")
        return None

async def render_to_pdf(goal: str, project_id: str) -> str:
    """Generate a PDF report using fpdf2."""
    try:
        from fpdf import FPDF
        
        pdf_path = str(ARTIFACTS_DIR / f"{project_id}_output.pdf")
        
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # Title
        pdf.set_font("Helvetica", "B", 24)
        pdf.set_text_color(0, 48, 255)
        pdf.cell(0, 20, "AI Company Workflow Engine", ln=True, align="C")
        pdf.ln(5)
        
        # Project goal
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(0, 12, "Project Report", ln=True, align="C")
        pdf.ln(10)
        
        pdf.set_font("Helvetica", "", 12)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(0, 8, f"Goal: {goal}")
        pdf.ln(5)
        
        # Fetch project tasks for report
        tasks = await db.tasks.find({"project_id": project_id}, {"_id": 0}).to_list(50)
        
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(0, 10, f"Tasks ({len(tasks)})", ln=True)
        pdf.ln(3)
        
        pdf.set_font("Helvetica", "", 10)
        for task in tasks:
            status_icon = "[OK]" if task.get("status") == "completed" else "[--]"
            agent = AGENTS.get(task.get("assigned_to", ""), {}).get("name", "Unassigned")
            pdf.set_text_color(80, 80, 80)
            pdf.cell(0, 7, f"  {status_icon} {task['title']} - {agent} ({task.get('status', 'pending')})", ln=True)
        
        pdf.ln(10)
        
        # Summary
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(0, 10, "Summary", ln=True)
        pdf.ln(3)
        
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(60, 60, 60)
        completed = sum(1 for t in tasks if t.get("status") == "completed")
        pdf.multi_cell(0, 7, f"Total tasks: {len(tasks)}\nCompleted: {completed}\nStatus: {'Delivered' if completed == len(tasks) else 'In Progress'}\nGenerated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        
        pdf.output(pdf_path)
        return pdf_path
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        return None

# ─── API Routes ───

# Health / Status
@api_router.get("/")
async def root():
    return {"message": "AI Company Workflow Engine API", "status": "operational"}

@api_router.get("/health")
async def health():
    ollama_ok = await check_ollama_available()
    return {
        "status": "healthy",
        "ollama_available": ollama_ok,
        "mode": model_config["mode"] if model_config["mode"] != "auto" else ("live" if ollama_ok else "simulation"),
        "reasoning_model": model_config["reasoning_model"],
        "coding_model": model_config["coding_model"],
        "routing_mode": model_config["mode"],
        "cached_models": _ollama_cache.get("models", []),
    }

# ─── Agents ───
@api_router.get("/agents", response_model=List[AgentOut])
async def get_agents():
    return list(AGENTS.values())

@api_router.get("/agents/{role}", response_model=AgentOut)
async def get_agent(role: str):
    if role not in AGENTS:
        raise HTTPException(404, "Agent not found")
    return AGENTS[role]

# ─── Projects ───
@api_router.post("/projects", response_model=ProjectOut)
async def create_project(req: ProjectCreate):
    project_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": project_id,
        "goal": req.goal,
        "output_format": req.output_format,
        "status": "planning",
        "constraints": req.constraints or {},
        "created_at": now,
        "updated_at": now
    }
    await db.projects.insert_one(doc)
    
    # Trigger kickoff meeting asynchronously
    asyncio.create_task(run_kickoff_meeting(project_id, req.goal, req.output_format))
    
    return ProjectOut(**{k: v for k, v in doc.items() if k != "_id"})

@api_router.get("/projects", response_model=List[ProjectOut])
async def get_projects():
    docs = await db.projects.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return docs

@api_router.get("/projects/{project_id}", response_model=ProjectOut)
async def get_project(project_id: str):
    doc = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Project not found")
    return doc

# ─── Meetings ───
@api_router.post("/meetings", response_model=MeetingOut)
async def create_meeting(req: MeetingCreate):
    meeting_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": meeting_id,
        "project_id": req.project_id,
        "meeting_type": req.meeting_type,
        "title": req.title or f"{req.meeting_type.capitalize()} Meeting",
        "status": "scheduled",
        "agenda_items": req.agenda_items,
        "participants": list(AGENTS.keys()),
        "created_at": now,
        "summary": None
    }
    await db.meetings.insert_one(doc)
    return MeetingOut(**{k: v for k, v in doc.items() if k != "_id"})

@api_router.get("/meetings", response_model=List[MeetingOut])
async def get_meetings(project_id: Optional[str] = Query(None)):
    query = {}
    if project_id:
        query["project_id"] = project_id
    docs = await db.meetings.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return docs

@api_router.get("/meetings/{meeting_id}", response_model=MeetingOut)
async def get_meeting(meeting_id: str):
    doc = await db.meetings.find_one({"id": meeting_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Meeting not found")
    return doc

# ─── Tasks ───
@api_router.post("/tasks", response_model=TaskOut)
async def create_task(req: TaskCreate):
    task_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": task_id,
        "project_id": req.project_id,
        "title": req.title,
        "description": req.description,
        "status": "pending",
        "assigned_to": req.assigned_to,
        "priority": req.priority,
        "depends_on": req.depends_on,
        "created_at": now,
        "output": None
    }
    await db.tasks.insert_one(doc)
    return TaskOut(**{k: v for k, v in doc.items() if k != "_id"})

@api_router.get("/tasks", response_model=List[TaskOut])
async def get_tasks(project_id: Optional[str] = Query(None), status: Optional[str] = Query(None), assigned_to: Optional[str] = Query(None)):
    query = {}
    if project_id:
        query["project_id"] = project_id
    if status:
        query["status"] = status
    if assigned_to:
        query["assigned_to"] = assigned_to
    docs = await db.tasks.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return docs

@api_router.patch("/tasks/{task_id}")
async def update_task(task_id: str, updates: Dict[str, Any]):
    allowed = {"status", "assigned_to", "priority", "output", "description"}
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if not filtered:
        raise HTTPException(400, "No valid fields to update")
    result = await db.tasks.update_one({"id": task_id}, {"$set": filtered})
    if result.matched_count == 0:
        raise HTTPException(404, "Task not found")
    doc = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    return doc

# ─── Messages / Dialogue ───
@api_router.post("/messages", response_model=MessageOut)
async def create_message(req: MessageCreate):
    msg_id = str(uuid.uuid4())
    thread_id = req.thread_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": msg_id,
        "thread_id": thread_id,
        "project_id": req.project_id,
        "meeting_id": req.meeting_id,
        "from_agent": req.from_agent,
        "to_agent": req.to_agent,
        "content": req.content,
        "thread_type": req.thread_type,
        "created_at": now
    }
    await db.messages.insert_one(doc)
    return MessageOut(**{k: v for k, v in doc.items() if k != "_id"})

@api_router.get("/messages", response_model=List[MessageOut])
async def get_messages(
    project_id: Optional[str] = Query(None),
    meeting_id: Optional[str] = Query(None),
    thread_id: Optional[str] = Query(None),
    from_agent: Optional[str] = Query(None)
):
    query = {}
    if project_id:
        query["project_id"] = project_id
    if meeting_id:
        query["meeting_id"] = meeting_id
    if thread_id:
        query["thread_id"] = thread_id
    if from_agent:
        query["from_agent"] = from_agent
    docs = await db.messages.find(query, {"_id": 0}).sort("created_at", 1).to_list(1000)
    return docs

@api_router.get("/threads")
async def get_threads(project_id: Optional[str] = Query(None)):
    pipeline = [
        {"$group": {
            "_id": "$thread_id",
            "project_id": {"$first": "$project_id"},
            "meeting_id": {"$first": "$meeting_id"},
            "thread_type": {"$first": "$thread_type"},
            "participants": {"$addToSet": "$from_agent"},
            "message_count": {"$sum": 1},
            "last_message": {"$last": "$content"},
            "last_agent": {"$last": "$from_agent"},
            "last_at": {"$max": "$created_at"}
        }},
        {"$sort": {"last_at": -1}}
    ]
    if project_id:
        pipeline.insert(0, {"$match": {"project_id": project_id}})
    
    threads = await db.messages.aggregate(pipeline).to_list(100)
    # Rename _id to thread_id
    for t in threads:
        t["thread_id"] = t.pop("_id")
    return threads

# ─── Decisions / Approvals ───
@api_router.post("/decisions", response_model=DecisionOut)
async def create_decision(req: DecisionCreate):
    dec_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": dec_id,
        "meeting_id": req.meeting_id,
        "project_id": req.project_id,
        "title": req.title,
        "description": req.description,
        "status": "pending",
        "decided_by": req.decided_by,
        "votes": {},
        "created_at": now
    }
    await db.decisions.insert_one(doc)
    return DecisionOut(**{k: v for k, v in doc.items() if k != "_id"})

@api_router.post("/decisions/{decision_id}/vote")
async def vote_decision(decision_id: str, vote: VoteCreate):
    result = await db.decisions.update_one(
        {"id": decision_id},
        {"$set": {f"votes.{vote.agent_role}": vote.vote}}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Decision not found")
    
    dec = await db.decisions.find_one({"id": decision_id}, {"_id": 0})
    
    # Auto-resolve: if majority approved or CEO approved
    votes = dec.get("votes", {})
    approved_count = sum(1 for v in votes.values() if v == "approved")
    if approved_count >= 4 or votes.get("ceo") == "approved":
        await db.decisions.update_one({"id": decision_id}, {"$set": {"status": "approved"}})
    elif votes.get("ceo") == "rejected":
        await db.decisions.update_one({"id": decision_id}, {"$set": {"status": "rejected"}})
    
    doc = await db.decisions.find_one({"id": decision_id}, {"_id": 0})
    return doc

@api_router.get("/decisions", response_model=List[DecisionOut])
async def get_decisions(project_id: Optional[str] = Query(None), status: Optional[str] = Query(None)):
    query = {}
    if project_id:
        query["project_id"] = project_id
    if status:
        query["status"] = status
    docs = await db.decisions.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return docs

# ─── Artifacts ───
@api_router.get("/artifacts", response_model=List[ArtifactOut])
async def get_artifacts(project_id: Optional[str] = Query(None)):
    query = {}
    if project_id:
        query["project_id"] = project_id
    docs = await db.artifacts.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return docs

@api_router.get("/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str):
    doc = await db.artifacts.find_one({"id": artifact_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Artifact not found")
    return doc

# ─── Execution ───
@api_router.post("/execute")
async def execute_project_route(req: ExecuteProjectRequest):
    project = await db.projects.find_one({"id": req.project_id}, {"_id": 0})
    if not project:
        raise HTTPException(404, "Project not found")
    
    asyncio.create_task(execute_project(req.project_id))
    return {"status": "execution_started", "project_id": req.project_id}

# ─── Stats ───
@api_router.get("/stats")
async def get_stats():
    projects = await db.projects.count_documents({})
    active = await db.projects.count_documents({"status": {"$in": ["planning", "in_progress"]}})
    completed = await db.projects.count_documents({"status": "completed"})
    tasks_total = await db.tasks.count_documents({})
    tasks_done = await db.tasks.count_documents({"status": "completed"})
    meetings = await db.meetings.count_documents({})
    messages = await db.messages.count_documents({})
    decisions = await db.decisions.count_documents({})
    artifacts = await db.artifacts.count_documents({})
    pending_approvals = await db.decisions.count_documents({"status": "pending"})
    
    return {
        "projects": {"total": projects, "active": active, "completed": completed},
        "tasks": {"total": tasks_total, "completed": tasks_done},
        "meetings": meetings,
        "messages": messages,
        "decisions": decisions,
        "artifacts": artifacts,
        "pending_approvals": pending_approvals,
        "agents_active": len([a for a in AGENTS.values() if a["status"] == "active"])
    }

# ─── Model Management ───
class ModelConfigUpdate(BaseModel):
    reasoning_model: Optional[str] = None
    coding_model: Optional[str] = None
    ollama_url: Optional[str] = None
    mode: Optional[str] = None  # auto | llama_only | qwen_only | simulation
    role_overrides: Optional[Dict[str, str]] = None

class ModelPullRequest(BaseModel):
    model_name: str

@api_router.get("/models")
async def get_models():
    """Get model config and available Ollama models."""
    ollama_ok = await check_ollama_available()
    available_models = await list_ollama_models() if ollama_ok else []

    # Build routing table showing what each agent will use
    routing_table = {}
    for role in AGENTS:
        for task_type in ["default", "code", "chat", "kickoff"]:
            model_name, reason = resolve_model_for(role, task_type)
            if role not in routing_table:
                routing_table[role] = {}
            routing_table[role][task_type] = {"model": model_name, "reason": reason}

    return {
        "config": {
            "ollama_url": model_config["ollama_url"],
            "reasoning_model": model_config["reasoning_model"],
            "coding_model": model_config["coding_model"],
            "mode": model_config["mode"],
            "role_overrides": model_config.get("role_overrides", {}),
        },
        "ollama_available": ollama_ok,
        "available_models": [
            {
                "name": m.get("name", ""),
                "size": m.get("size", 0),
                "modified_at": m.get("modified_at", ""),
                "digest": m.get("digest", "")[:12],
            }
            for m in available_models
        ],
        "routing_table": routing_table,
        "cached_models": _ollama_cache.get("models", []),
    }

@api_router.post("/models/config")
async def update_model_config(req: ModelConfigUpdate):
    """Update model routing configuration."""
    if req.reasoning_model is not None:
        model_config["reasoning_model"] = req.reasoning_model
    if req.coding_model is not None:
        model_config["coding_model"] = req.coding_model
    if req.ollama_url is not None:
        model_config["ollama_url"] = req.ollama_url
        _ollama_cache["available"] = None  # reset cache
    if req.mode is not None:
        if req.mode not in ("auto", "llama_only", "qwen_only", "simulation"):
            raise HTTPException(400, "mode must be: auto, llama_only, qwen_only, or simulation")
        model_config["mode"] = req.mode
    if req.role_overrides is not None:
        model_config["role_overrides"] = req.role_overrides

    # Persist to MongoDB
    await db.system_config.update_one(
        {"key": "model_config"},
        {"$set": {"key": "model_config", "value": model_config}},
        upsert=True,
    )

    return {"status": "updated", "config": model_config}

@api_router.post("/models/pull")
async def pull_model(req: ModelPullRequest):
    """Trigger an Ollama model pull (async)."""
    ollama_ok = await check_ollama_available()
    if not ollama_ok:
        raise HTTPException(503, "Ollama is not available")
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.post(
                f"{model_config['ollama_url']}/api/pull",
                json={"name": req.model_name, "stream": False},
            )
            if r.status_code == 200:
                _ollama_cache["available"] = None  # reset cache
                return {"status": "pull_started", "model": req.model_name}
            return {"status": "error", "detail": r.text}
    except httpx.TimeoutException:
        # Pull takes time, that's OK
        return {"status": "pull_started", "model": req.model_name, "note": "Pull in progress (may take minutes)"}
    except Exception as e:
        raise HTTPException(500, str(e))

@api_router.get("/models/test/{model_name}")
async def test_model(model_name: str):
    """Quick test a specific model with a simple prompt."""
    ollama_ok = await check_ollama_available()
    if not ollama_ok:
        return {"status": "error", "detail": "Ollama not available", "mode": "simulation"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.post(f"{model_config['ollama_url']}/api/generate", json={
                "model": model_name,
                "prompt": "Say hello in one sentence.",
                "stream": False
            })
            if r.status_code == 200:
                resp = r.json()
                return {
                    "status": "ok",
                    "model": model_name,
                    "response": resp.get("response", "").strip()[:200],
                    "total_duration_ms": resp.get("total_duration", 0) / 1_000_000,
                    "eval_count": resp.get("eval_count", 0),
                }
            return {"status": "error", "detail": f"HTTP {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:200], "model": model_name}

# ─── User Chat with Agents ───
@api_router.post("/chat")
async def user_chat(req: UserChatRequest):
    if req.to_agent not in AGENTS:
        raise HTTPException(400, f"Unknown agent: {req.to_agent}")
    
    thread_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    # Store user message
    user_msg = {
        "id": str(uuid.uuid4()),
        "thread_id": thread_id,
        "project_id": req.project_id,
        "meeting_id": None,
        "from_agent": "user",
        "to_agent": req.to_agent,
        "content": req.content,
        "thread_type": "direct",
        "created_at": now
    }
    await db.messages.insert_one(user_msg)
    
    # Generate agent response
    context = f"A user is directly messaging you. Their message: {req.content}"
    if req.project_id:
        project = await db.projects.find_one({"id": req.project_id}, {"_id": 0})
        if project:
            context += f"\nProject context: {project['goal']}"
    
    # Generate agent response using the model routing system
    result = await get_agent_response(req.to_agent, context, "chat")
    response_text = result["content"]
    # If simulation and we have a better chat-specific template, use it
    if result["mode"] == "simulation":
        chat_text = USER_CHAT_RESPONSES.get(req.to_agent)
        if chat_text:
            response_text = chat_text
    
    # Store agent response
    agent_msg = {
        "id": str(uuid.uuid4()),
        "thread_id": thread_id,
        "project_id": req.project_id,
        "meeting_id": None,
        "from_agent": req.to_agent,
        "to_agent": "user",
        "content": response_text,
        "thread_type": "direct",
        "model_used": result["model"],
        "model_mode": result["mode"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.messages.insert_one(agent_msg)
    
    return {
        "thread_id": thread_id,
        "user_message": {k: v for k, v in user_msg.items() if k != "_id"},
        "agent_response": {k: v for k, v in agent_msg.items() if k != "_id"},
        "model_info": {"model": result["model"], "mode": result["mode"], "routing": result["routing"]}
    }

@api_router.get("/chat/history")
async def get_chat_history():
    """Get all user-agent chat messages."""
    pipeline = [
        {"$match": {"$or": [{"from_agent": "user"}, {"to_agent": "user"}]}},
        {"$sort": {"created_at": -1}},
        {"$limit": 200}
    ]
    docs = await db.messages.aggregate(pipeline).to_list(200)
    for d in docs:
        d.pop("_id", None)
    return docs

# ─── Budget Tracking ───
AGENT_HOURLY_RATES = {
    "ceo": 250, "cfo": 200, "hr": 150, "ux": 175,
    "developer": 200, "frontend": 180, "backend": 180, "devops": 190,
}

TASK_BASE_COSTS = {
    "high": 500, "medium": 300, "low": 150,
}

@api_router.get("/budget/summary")
async def get_budget_summary():
    """Get overall budget summary across all projects."""
    projects = await db.projects.find({}, {"_id": 0}).to_list(100)
    tasks = await db.tasks.find({}, {"_id": 0}).to_list(500)
    
    total_budget = 0
    total_spent = 0
    by_department = {}
    by_agent = {}
    by_status = {"allocated": 0, "spent": 0, "remaining": 0}
    
    for task in tasks:
        role = task.get("assigned_to", "developer")
        priority = task.get("priority", "medium")
        base_cost = TASK_BASE_COSTS.get(priority, 300)
        hourly = AGENT_HOURLY_RATES.get(role, 180)
        task_cost = base_cost + (hourly * 0.5)  # 30 min estimated per task
        
        total_budget += task_cost
        
        dept = AGENTS.get(role, {}).get("department", "unknown")
        by_department[dept] = by_department.get(dept, 0) + task_cost
        
        agent_name = AGENTS.get(role, {}).get("name", role)
        by_agent[role] = by_agent.get(role, {"name": agent_name, "cost": 0, "tasks": 0})
        by_agent[role]["cost"] += task_cost
        by_agent[role]["tasks"] += 1
        
        if task.get("status") == "completed":
            total_spent += task_cost
    
    by_status["allocated"] = total_budget
    by_status["spent"] = total_spent
    by_status["remaining"] = total_budget - total_spent
    
    return {
        "total_budget": round(total_budget, 2),
        "total_spent": round(total_spent, 2),
        "remaining": round(total_budget - total_spent, 2),
        "utilization_pct": round((total_spent / total_budget * 100) if total_budget > 0 else 0, 1),
        "by_department": {k: round(v, 2) for k, v in by_department.items()},
        "by_agent": {k: {"name": v["name"], "cost": round(v["cost"], 2), "tasks": v["tasks"]} for k, v in by_agent.items()},
        "by_status": {k: round(v, 2) for k, v in by_status.items()},
        "projects_count": len(projects),
        "total_tasks": len(tasks),
    }

@api_router.get("/budget/projects")
async def get_budget_by_project():
    """Get budget breakdown per project."""
    projects = await db.projects.find({}, {"_id": 0}).to_list(100)
    result = []
    
    for project in projects:
        tasks = await db.tasks.find({"project_id": project["id"]}, {"_id": 0}).to_list(100)
        project_budget = 0
        project_spent = 0
        agent_costs = {}
        
        for task in tasks:
            role = task.get("assigned_to", "developer")
            priority = task.get("priority", "medium")
            base_cost = TASK_BASE_COSTS.get(priority, 300)
            hourly = AGENT_HOURLY_RATES.get(role, 180)
            task_cost = base_cost + (hourly * 0.5)
            
            project_budget += task_cost
            if task.get("status") == "completed":
                project_spent += task_cost
            
            agent_name = AGENTS.get(role, {}).get("name", role)
            agent_costs[role] = agent_costs.get(role, {"name": agent_name, "cost": 0})
            agent_costs[role]["cost"] += task_cost
        
        result.append({
            "project_id": project["id"],
            "goal": project["goal"],
            "status": project["status"],
            "budget": round(project_budget, 2),
            "spent": round(project_spent, 2),
            "remaining": round(project_budget - project_spent, 2),
            "task_count": len(tasks),
            "agent_costs": {k: {"name": v["name"], "cost": round(v["cost"], 2)} for k, v in agent_costs.items()},
        })
    
    return result

# ─── Artifact Rendering ───
@api_router.post("/artifacts/render")
async def render_artifact(req: RenderArtifactRequest):
    """On-demand render an existing HTML artifact to PNG or PDF."""
    artifact = await db.artifacts.find_one({"id": req.artifact_id}, {"_id": 0})
    if not artifact:
        raise HTTPException(404, "Artifact not found")
    
    if artifact.get("artifact_type") != "html":
        raise HTTPException(400, "Can only render HTML artifacts")
    
    now = datetime.now(timezone.utc).isoformat()
    project_id = artifact.get("project_id", "unknown")
    
    if req.render_type == "png":
        png_path = await render_html_to_png(artifact["content"], project_id + "_render")
        if not png_path:
            raise HTTPException(500, "PNG rendering failed")
        with open(png_path, "rb") as f:
            png_b64 = base64.b64encode(f.read()).decode()
        new_artifact = {
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "task_id": None,
            "name": "rendered_output.png",
            "artifact_type": "png",
            "content": png_b64,
            "file_path": png_path,
            "created_at": now
        }
        await db.artifacts.insert_one(new_artifact)
        return {k: v for k, v in new_artifact.items() if k != "_id"}
    
    elif req.render_type == "pdf":
        # Use the project goal for PDF
        project = await db.projects.find_one({"id": project_id}, {"_id": 0})
        goal = project["goal"] if project else "Rendered artifact"
        pdf_path = await render_to_pdf(goal, project_id + "_render")
        if not pdf_path:
            raise HTTPException(500, "PDF rendering failed")
        with open(pdf_path, "rb") as f:
            pdf_b64 = base64.b64encode(f.read()).decode()
        new_artifact = {
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "task_id": None,
            "name": "rendered_output.pdf",
            "artifact_type": "pdf",
            "content": pdf_b64,
            "file_path": pdf_path,
            "created_at": now
        }
        await db.artifacts.insert_one(new_artifact)
        return {k: v for k, v in new_artifact.items() if k != "_id"}
    else:
        raise HTTPException(400, "render_type must be 'png' or 'pdf'")

@api_router.get("/artifacts/{artifact_id}/download")
async def download_artifact(artifact_id: str):
    """Download a file-based artifact."""
    artifact = await db.artifacts.find_one({"id": artifact_id}, {"_id": 0})
    if not artifact:
        raise HTTPException(404, "Artifact not found")
    
    if artifact.get("file_path") and os.path.exists(artifact["file_path"]):
        media_types = {"png": "image/png", "pdf": "application/pdf", "html": "text/html"}
        mt = media_types.get(artifact.get("artifact_type"), "application/octet-stream")
        return FileResponse(artifact["file_path"], media_type=mt, filename=artifact["name"])

app.include_router(api_router)

# ─── WebSocket (mounted directly on app, not router) ───
@app.websocket("/api/ws/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    await ws_manager.connect(websocket, project_id)
    try:
        while True:
            await websocket.receive_text()
            # Keep connection alive, handle incoming WS messages if needed
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, project_id)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

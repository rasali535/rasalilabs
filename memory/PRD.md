# AI Company Workflow Engine - PRD

## Original Problem Statement
Autonomous AI Company Workflow Engine with Boardroom and Agent Dialogue. A local-first AI company system that can take a goal, let specialized agents discuss it internally, hold structured boardroom meetings, approve tasks, delegate work, execute autonomously, and return final outputs in requested formats (HTML, PNG, PDF, JSON, MP4/MPEG, code files).

## User Personas
- **Solo Developer/Entrepreneur**: Wants to submit a business goal and have an AI company autonomously plan, discuss, and execute it
- **Team Lead/Manager**: Wants visibility into how AI agents collaborate, make decisions, and delegate work
- **Technical User**: Wants to see coding tasks assigned to technical agents and review generated artifacts

## Core Requirements (Static)
1. Role-based AI agents: CEO, CFO, HR, UI/UX, Developer, Frontend, Backend, DevOps
2. Inter-agent dialogue system with task-linked threads
3. Boardroom meeting system with approvals and delegation
4. Autonomous workflow execution engine
5. Artifact generation (HTML, JSON, code files, PNG, PDF)
6. LLM integration: Llama (reasoning) + Qwen (coding) via Ollama, with simulation fallback

## Architecture
- **Frontend**: React + Tailwind + Shadcn UI (dark theme, Swiss/High-Contrast aesthetic)
- **Backend**: FastAPI + MongoDB (Motor async driver)
- **LLM**: Ollama integration with simulation fallback mode
- **Design**: Chivo/IBM Plex Sans/JetBrains Mono fonts, Klein Blue accent (#0030FF)

## What's Been Implemented (Feb 2026)
### Backend (server.py)
- 8 agent roles with personalities, skills, and departments
- Project CRUD with auto-kickoff meeting on creation
- Meeting system with agenda, participants, summaries
- Task system with assignment, status tracking, dependencies
- Message/dialogue system with threads and aggregation
- Decision/approval system with voting logic
- Artifact generation (HTML, JSON, code, PNG via Playwright, PDF via fpdf2)
- On-demand artifact rendering (POST /api/artifacts/render)
- Orchestration engine: goal → plan → meeting → delegation → execution → artifacts
- Ollama integration with intelligent simulation fallback
- Stats API for dashboard metrics
- **User-to-Agent Chat** (POST /api/chat) with per-agent personality responses
- **CFO Budget Tracking** (GET /api/budget/summary, /api/budget/projects) with department/agent/project cost analysis
- **WebSocket real-time updates** (/api/ws/{project_id}) for live meeting dialogue broadcasting
- **PNG rendering** via Playwright (chromium headless) with base64 storage
- **PDF generation** via fpdf2 with task report format

### Frontend (React)
- Dashboard: Stats grid, Agent Team display, Projects list, New Project dialog
- Boardroom: 4-panel layout with **WebSocket Live/Polling indicator** for real-time updates
- Dialogue: Thread list with search, message view with agent-colored bubbles
- Delegation: Kanban-style board grouped by agent, status/agent filters
- Approvals: Decision cards with voting, status filtering
- Projects: Project list, detail view with Tasks/Artifacts/Meetings tabs, artifact preview/download, **Render PNG/PDF buttons** for HTML artifacts, PNG image preview
- **CFO Budget Dashboard**: Summary cards, utilization bar, tabs for department/agent/project breakdowns with colored progress bars
- **Chat Drawer**: Floating chat button, agent selector dropdown, send messages to any agent, role-appropriate responses

## Prioritized Backlog
### P0 (Critical - Next)
- Real Ollama integration testing (when user has Ollama running locally)

### P1 (Important)
- MP4/MPEG media generation pipeline
- Real-time WebSocket updates for chat messages too
- Meeting minutes auto-generation and export
- Budget alerts and thresholds (CFO approval triggers)

### P2 (Nice to Have)
- Agent activation/deactivation (HR controls)
- Override and kill-switch controls
- Audit trail and decision log views
- Boardroom analytics and decision insights
- Advanced task dependency graph visualization
- Meeting scheduling and calendar integration

## Next Tasks
1. Implement real Ollama integration with live model switching
2. Add MP4/MPEG media generation pipeline
3. Build meeting minutes export functionality
4. Add budget alerts and CFO approval thresholds
5. Implement agent lifecycle management (HR controls)

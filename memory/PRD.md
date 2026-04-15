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
- Artifact generation (HTML, JSON, code)
- Orchestration engine: goal → plan → meeting → delegation → execution → artifacts
- Ollama integration with intelligent simulation fallback
- Stats API for dashboard metrics

### Frontend (React)
- Dashboard: Stats grid, Agent Team display, Projects list, New Project dialog
- Boardroom: 4-panel layout (Participants, Dialogue Transcript, Agenda/Approvals/Tasks, Execution Bar)
- Dialogue: Thread list with search, message view with agent-colored bubbles
- Delegation: Kanban-style board grouped by agent, status/agent filters
- Approvals: Decision cards with voting, status filtering
- Projects: Project list, detail view with Tasks/Artifacts/Meetings tabs, artifact preview/download

## Prioritized Backlog
### P0 (Critical - Next)
- PNG rendering pipeline (Playwright screenshot of HTML artifacts)
- PDF export pipeline (ReportLab or wkhtmltopdf)
- Real Ollama integration testing (when user has Ollama running locally)

### P1 (Important)
- MP4/MPEG media generation pipeline
- Real-time WebSocket updates for meeting dialogue
- Direct agent messaging from UI (user sends messages to agents)
- Meeting minutes auto-generation and export
- Budget tracking (CFO financial controls)

### P2 (Nice to Have)
- Agent activation/deactivation (HR controls)
- Override and kill-switch controls
- Audit trail and decision log views
- Boardroom analytics and decision insights
- Advanced task dependency graph visualization
- Meeting scheduling and calendar integration

## Next Tasks
1. Add PNG/PDF artifact generation using Python libraries
2. Implement WebSocket for real-time dialogue updates
3. Add user-to-agent messaging interface
4. Build meeting minutes export
5. Add CFO budget tracking dashboard

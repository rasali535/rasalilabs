# 🌌 Ras Ali Labs — Autonomous Agentic Ecosystem

Welcome to **Ras Ali Labs**, a state-of-the-art multi-agent collaboration platform and workflow engine designed to model, simulate, and automate complex team dynamics.

---

## 🚀 Key Features

* **Multi-Agent Boardroom & Workflows**: Run multi-agent simulations with specialised roles including CEO, CFO, HR, UX, DevOps, and developers (Frontend/Backend) working together on product requirements, budgets, designs, and code.
* **Cognitive Memory Dashboard**: Integrated with **Cognee Cloud**, enabling agents to automatically recall relevant history, capture details from their discussions, and store them directly into a persistent semantic knowledge graph.
* **Intelligent Model Router (AI/ML Mix)**: 
  * **Reasoning**: Powered by **GPT-4o-Mini** (via AI/ML API) for fast, low-latency strategic decision-making.
  * **Coding**: Powered by **Qwen 2.5 Coder 32B** (via AI/ML API) for high-fidelity code synthesis and implementation.
* **Interactive APIs**: Full OpenAPI/Swagger interactive developer documentation hosted locally.

---

## 🛠️ Tech Stack & Ports

* **Frontend**: React (Create React App + Tailwind UI styled custom dashboard) — **Port 3000**
* **Backend**: FastAPI Python Backend (Uvicorn web server) — **Port 4001**
* **Graph Memory**: Cognee Cloud SDK & REST APIs

---

## 📁 Repository Structure

* `backend/` — FastAPI application, agents definition, and database models.
* `frontend/` — React SPA with the Dashboard, Boardroom, Dialogue, and Cognitive Memory views.
* `.agents/` — Workspace customizations, global rules, and Cognee Memory skills.

---

## ⚡ Getting Started

### 1. Prerequisites
Ensure you have **Python 3.10+** and **Node.js 18+** installed on your machine.

### 2. Environment Setup
Configure your environment variables in `backend/.env`:
```env
PORT=4001
MONGO_URL=mongodb://localhost:27017
DB_NAME=rasalilabs

# AI/ML API (LLMs)
AIML_API_KEY=your-aiml-api-key
AIML_BASE_URL=https://api.aimlapi.com/v1
LLAMA_MODEL=gpt-4o-mini
QWEN_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct

# Cognee Graph Memory
COGNEE_API_URL=https://tenant-yourtenant.aws.cognee.ai
COGNEE_API_KEY=your-cognee-api-key
COGNEE_TENANT_ID=your-tenant-id
COGNEE_DATASET=rasalilabs
```

### 3. Run Backend
```bash
cd backend
pip install -r requirements.txt
python server.py
```
*Interactive Swagger docs will be available at: [http://localhost:4001/docs](http://localhost:4001/docs)*

### 4. Run Frontend
```bash
cd frontend
npm install
npm start
```
*Open your browser and navigate to: [http://localhost:3000](http://localhost:3000)*

---

## 🤝 Contributing
For feature requests or changes, please submit a pull request or open an issue in the repository.

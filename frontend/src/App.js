import "@/index.css";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import Sidebar from "@/components/Sidebar";
import Dashboard from "@/pages/Dashboard";
import Boardroom from "@/pages/Boardroom";
import Dialogue from "@/pages/Dialogue";
import Delegation from "@/pages/Delegation";
import Approvals from "@/pages/Approvals";
import Projects from "@/pages/Projects";

function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen w-screen overflow-hidden bg-[#0A0A0A]" data-testid="app-container">
        <Sidebar />
        <main className="flex-1 overflow-hidden">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/boardroom/:meetingId?" element={<Boardroom />} />
            <Route path="/dialogue" element={<Dialogue />} />
            <Route path="/delegation" element={<Delegation />} />
            <Route path="/approvals" element={<Approvals />} />
            <Route path="/projects" element={<Projects />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: '#111111',
              border: '1px solid #222222',
              color: '#FFFFFF',
              fontFamily: 'IBM Plex Sans, sans-serif',
            },
          }}
        />
      </div>
    </BrowserRouter>
  );
}

export default App;

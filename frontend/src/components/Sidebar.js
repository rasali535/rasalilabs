import { NavLink, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Users,
  MessageSquare,
  ListTodo,
  ShieldCheck,
  FolderOpen,
  DollarSign,
  Cpu,
  Zap,
  MessageCircle,
  Mail
} from "lucide-react";
import { getLogoUrl } from "@/lib/api";

const NAV_ITEMS = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard, testId: "nav-dashboard" },
  { path: "/boardroom", label: "Boardroom", icon: Users, testId: "nav-boardroom" },
  { path: "/dialogue", label: "Dialogue", icon: MessageSquare, testId: "nav-dialogue" },
  { path: "/delegation", label: "Delegation", icon: ListTodo, testId: "nav-delegation" },
  { path: "/approvals", label: "Approvals", icon: ShieldCheck, testId: "nav-approvals" },
  { path: "/projects", label: "Projects", icon: FolderOpen, testId: "nav-projects" },
  { path: "/budget", label: "Budget", icon: DollarSign, testId: "nav-budget" },
  { path: "/models", label: "Models", icon: Cpu, testId: "nav-models" },
];

export default function Sidebar() {
  const location = useLocation();

  return (
    <aside
      data-testid="sidebar"
      className="w-[200px] h-screen flex flex-col bg-[#0A0A0A] border-r border-[#222222] shrink-0"
    >
      {/* Logo */}
      <div className="px-4 py-4 border-b border-[#222222] flex items-center gap-3">
        <img 
          src={getLogoUrl()} 
          alt="Ras Ali Labs" 
          className="w-8 h-8 object-contain"
          onError={(e) => {
            e.target.style.display = 'none';
            e.target.nextSibling.style.display = 'flex';
          }}
        />
        <div className="w-8 h-8 rounded-sm bg-[#0030FF] hidden items-center justify-center shrink-0">
          <Zap className="w-5 h-5 text-white" />
        </div>
        <span
          className="font-['Chivo'] text-[13px] font-bold tracking-tight text-white"
          data-testid="app-logo-text"
        >
          Ras Ali Labs
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-3 px-2 space-y-0.5" data-testid="sidebar-nav">
        {NAV_ITEMS.map((item) => {
          const isActive =
            item.path === "/"
              ? location.pathname === "/"
              : location.pathname.startsWith(item.path);
          return (
            <NavLink
              key={item.path}
              to={item.path}
              data-testid={item.testId}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-sm text-[13px] font-medium transition-colors ${
                isActive
                  ? "bg-[#1A1A1A] text-white"
                  : "text-zinc-500 hover:text-zinc-200 hover:bg-[#141414]"
              }`}
            >
              <item.icon className="w-4 h-4" strokeWidth={1.5} />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Status & Contact footer */}
      <div className="px-4 py-4 border-t border-[#222222] flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <span className="status-dot status-active pulse-dot" />
          <span
            className="font-mono text-[10px] uppercase tracking-wider text-zinc-500"
            data-testid="system-status"
          >
            System Active
          </span>
        </div>
        
        <div className="bg-[#111111] border border-[#222222] rounded-sm p-3">
          <p className="text-[10px] text-zinc-400 font-mono uppercase mb-2">Need Clarity?</p>
          <div className="flex flex-col gap-2">
            <a 
              href="https://wa.me/26777150423" 
              target="_blank" 
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-xs text-zinc-300 hover:text-white transition-colors"
            >
              <MessageCircle className="w-3.5 h-3.5 text-[#25D366]" />
              WhatsApp Me
            </a>
            <a 
              href="mailto:rasali@themaplin.com" 
              className="flex items-center gap-2 text-xs text-zinc-300 hover:text-white transition-colors"
            >
              <Mail className="w-3.5 h-3.5 text-zinc-400" />
              Email Me
            </a>
          </div>
        </div>
      </div>
    </aside>
  );
}

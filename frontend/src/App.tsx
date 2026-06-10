import { useState } from 'react';
import { MessageSquare, BarChart3 } from 'lucide-react';
import ChatPage from './components/ChatPage';
import DashboardPage from './components/DashboardPage';
import './App.css';

type Page = 'chat' | 'dashboard';



/* Minimal geometric spark logo */
function LogoMark() {
  return (
    <svg viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M18 2L21.5 14.5L34 18L21.5 21.5L18 34L14.5 21.5L2 18L14.5 14.5L18 2Z"
        fill="url(#logo-grad)"
        opacity="0.9"
      />
      <path
        d="M18 8L20 15L27 18L20 21L18 28L16 21L9 18L16 15L18 8Z"
        fill="white"
        opacity="0.5"
      />
      <defs>
        <linearGradient id="logo-grad" x1="2" y1="2" x2="34" y2="34">
          <stop stopColor="#fb923c" />
          <stop offset="1" stopColor="#ea580c" />
        </linearGradient>
      </defs>
    </svg>
  );
}

export default function App() {
  const [activePage, setActivePage] = useState<Page>('chat');

  return (
    <div className="app-layout">
      {/* Floating Sidebar */}
      <nav className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-mark">
            <LogoMark />
          </div>
          <div className="logo-text">
            <h1>Xeno AI</h1>
            <span>Campaign Agent</span>
          </div>
        </div>

        <button
          className={`nav-item ${activePage === 'chat' ? 'active' : ''}`}
          onClick={() => setActivePage('chat')}
        >
          <MessageSquare className="nav-icon" />
          AI Agent
        </button>

        <button
          className={`nav-item ${activePage === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActivePage('dashboard')}
        >
          <BarChart3 className="nav-icon" />
          Dashboard
        </button>

        {/* Footer */}
        <div className="sidebar-footer">
          <div className="sidebar-footer-card">
            <div className="footer-label">Orchestration Engine</div>
            <div className="footer-sub">Dual LLM &middot; LangGraph</div>
            <div className="footer-badges">
              <span className="badge badge-completed">Gemini</span>
              <span className="badge badge-sending">Groq</span>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="main-content">
        <header className="page-header">
          <div style={{ display: 'flex', alignItems: 'baseline' }}>
            <h2>{activePage === 'chat' ? 'AI Campaign Agent' : 'Campaign Dashboard'}</h2>
            <span className="header-subtitle">
              {activePage === 'chat' ? 'Natural language \u2192 campaigns' : 'Analytics & performance'}
            </span>
          </div>
        </header>

        <div className="page-body">
          {/* Use display:none to keep both mounted but hidden, preserving state */}
          <div style={{ display: activePage === 'chat' ? 'contents' : 'none' }}>
            <ChatPage />
          </div>
          <div style={{ display: activePage === 'dashboard' ? 'contents' : 'none' }}>
            <DashboardPage />
          </div>
        </div>
      </main>
    </div>
  );
}

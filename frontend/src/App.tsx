import { useState } from 'react';
import { MessageSquare, BarChart3, Sparkles } from 'lucide-react';
import ChatPage from './components/ChatPage';
import DashboardPage from './components/DashboardPage';
import './App.css';

type Page = 'chat' | 'dashboard';

export default function App() {
  const [activePage, setActivePage] = useState<Page>('chat');

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <nav className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-icon">
            <Sparkles size={20} />
          </div>
          <h1>Xeno AI</h1>
        </div>

        <button
          className={`nav-item ${activePage === 'chat' ? 'active' : ''}`}
          onClick={() => setActivePage('chat')}
        >
          <MessageSquare size={20} className="nav-icon" />
          AI Agent
        </button>

        <button
          className={`nav-item ${activePage === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActivePage('dashboard')}
        >
          <BarChart3 size={20} className="nav-icon" />
          Dashboard
        </button>

        {/* Bottom section */}
        <div style={{ marginTop: 'auto', padding: '16px 0' }}>
          <div className="glass-subtle" style={{ padding: '12px 14px', fontSize: 12, color: '#737373' }}>
            <div style={{ fontWeight: 600, marginBottom: 4, color: '#525252' }}>Xeno AI CRM</div>
            <div>AI-native Mini CRM</div>
            <div style={{ marginTop: 6, display: 'flex', gap: 6 }}>
              <span className="badge badge-completed" style={{ fontSize: 10 }}>Gemini</span>
              <span className="badge badge-sending" style={{ fontSize: 10 }}>Groq</span>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="main-content">
        <header className="page-header">
          <h2>{activePage === 'chat' ? 'AI Campaign Agent' : 'Campaign Dashboard'}</h2>
        </header>

        <div className="page-body">
          {activePage === 'chat' && <ChatPage />}
          {activePage === 'dashboard' && <DashboardPage />}
        </div>
      </main>
    </div>
  );
}

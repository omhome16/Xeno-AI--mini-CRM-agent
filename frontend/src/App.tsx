import { useState } from 'react';
import { MessageSquare, BarChart3, Store, Database } from 'lucide-react';
import ChatPage from './components/ChatPage';
import DashboardPage from './components/DashboardPage';
import BrandProfilePage from './components/BrandProfilePage';
import DataIngestionPage from './components/DataIngestionPage';
import './App.css';

type Page = 'chat' | 'dashboard' | 'brand' | 'ingest';



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
  const [activePage, setActivePage] = useState<Page>('brand');

  const getHeaderInfo = () => {
    switch (activePage) {
      case 'chat':
        return { title: 'AI Campaign Agent', subtitle: 'Natural language \u2192 campaigns' };
      case 'dashboard':
        return { title: 'Campaign Dashboard', subtitle: 'Analytics & performance' };
      case 'brand':
        return { title: 'Brand Profile Hub', subtitle: 'Configure brand niche, catalogs, and tone' };
      case 'ingest':
        return { title: 'Data Ingestion Portal', subtitle: 'Ingest customer books and purchase history' };
      default:
        return { title: 'Xeno CRM', subtitle: '' };
    }
  };

  const header = getHeaderInfo();

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
          className={`nav-item ${activePage === 'brand' ? 'active' : ''}`}
          onClick={() => setActivePage('brand')}
        >
          <Store className="nav-icon" />
          Brand Profile
        </button>

        <button
          className={`nav-item ${activePage === 'ingest' ? 'active' : ''}`}
          onClick={() => setActivePage('ingest')}
        >
          <Database className="nav-icon" />
          Data Ingestion
        </button>

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
            <div className="footer-sub">Gemini &middot; LangGraph</div>
            <div className="footer-badges">
              <span className="badge badge-sending">Gemini</span>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="main-content">
        <header className="page-header">
          <div style={{ display: 'flex', alignItems: 'baseline' }}>
            <h2>{header.title}</h2>
            <span className="header-subtitle">{header.subtitle}</span>
          </div>
          {activePage === 'chat' && (
            <div id="header-copilot-portal" style={{ position: 'relative', flexGrow: 1, display: 'flex', justifyContent: 'flex-end', maxWidth: '420px', marginLeft: '1.5rem' }}></div>
          )}
        </header>

        <div className="page-body">
          {/* Use display:none to keep all mounted but hidden, preserving state */}
          <div style={{ display: activePage === 'chat' ? 'contents' : 'none' }}>
            <ChatPage isActive={activePage === 'chat'} />
          </div>
          <div style={{ display: activePage === 'dashboard' ? 'contents' : 'none' }}>
            <DashboardPage isActive={activePage === 'dashboard'} />
          </div>
          <div style={{ display: activePage === 'brand' ? 'contents' : 'none' }}>
            <BrandProfilePage />
          </div>
          <div style={{ display: activePage === 'ingest' ? 'contents' : 'none' }}>
            <DataIngestionPage />
          </div>
        </div>
      </main>
    </div>
  );
}

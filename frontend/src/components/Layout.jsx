import { useState, useEffect } from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import {
  Upload, Database, MessageSquare, Bug, BarChart2,
  ChevronLeft, ChevronRight, Settings
} from 'lucide-react';
import { Toaster } from 'react-hot-toast';
import { checkHealth } from '../services/api';

const NAV_ITEMS = [
  { name: 'Upload', path: '/upload', icon: Upload, emoji: '☁' },
  { name: 'Schema', path: '/schema', icon: Database, emoji: '📋' },
  { name: 'Query', path: '/query', icon: MessageSquare, emoji: '💬' },
  { name: 'Results', path: '/results', icon: BarChart2, emoji: '📊' },
  { name: 'Debug', path: '/debug', icon: Bug, emoji: '🔬' },
];

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false);
  const [health, setHealth] = useState(null);
  const location = useLocation();

  useEffect(() => {
    const fetchHealth = async () => {
      const data = await checkHealth();
      setHealth(data);
    };
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  // Re-fetch health on navigation
  useEffect(() => {
    checkHealth().then(setHealth);
  }, [location.pathname]);

  const duckdbOk = health?.duckdb?.status === 'healthy';
  const apiOk = health?.anthropic_api?.status === 'configured';
  const fileCount = health?.files_loaded || 0;

  const currentPage = NAV_ITEMS.find(n => location.pathname.startsWith(n.path))?.name || 'Query';

  return (
    <div className="flex h-screen bg-gray-950 text-white font-sans overflow-hidden">
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: '#1f2937',
            color: '#f9fafb',
            border: '1px solid #374151',
            borderRadius: '12px',
            fontSize: '14px',
          },
          success: { iconTheme: { primary: '#10b981', secondary: '#f9fafb' } },
          error: { iconTheme: { primary: '#ef4444', secondary: '#f9fafb' } },
        }}
      />

      {/* ═══ Sidebar ═══ */}
      <aside
        className={`${collapsed ? 'w-16' : 'w-60'} bg-gray-900 border-r border-gray-800 flex flex-col flex-shrink-0 transition-all duration-300 relative`}
      >
        {/* Logo */}
        <div className={`p-4 border-b border-gray-800 flex items-center ${collapsed ? 'justify-center' : 'gap-3'}`}>
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center flex-shrink-0 shadow-lg shadow-blue-500/20">
            <Database size={16} className="text-white" />
          </div>
          {!collapsed && (
            <h1 className="text-lg font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent whitespace-nowrap">
              Parquet AI
            </h1>
          )}
        </div>

        {/* Collapse Toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="absolute -right-3 top-20 w-6 h-6 bg-gray-800 border border-gray-700 rounded-full flex items-center justify-center text-gray-400 hover:text-white hover:bg-gray-700 transition-colors z-10"
        >
          {collapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
        </button>

        {/* Navigation */}
        <nav className="flex-1 py-4">
          <ul className="space-y-1 px-2">
            {NAV_ITEMS.map((item) => (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  title={collapsed ? item.name : undefined}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 group ${
                      isActive
                        ? 'bg-blue-600/15 text-blue-400 border border-blue-500/20 shadow-sm shadow-blue-500/5'
                        : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200 border border-transparent'
                    } ${collapsed ? 'justify-center' : ''}`
                  }
                >
                  <item.icon size={18} className="flex-shrink-0" />
                  {!collapsed && <span className="font-medium text-sm">{item.name}</span>}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        {/* Bottom Status */}
        <div className="p-3 border-t border-gray-800 space-y-2">
          {!collapsed ? (
            <>
              <StatusRow label="DuckDB" ok={duckdbOk} />
              <StatusRow label="Claude API" ok={apiOk} />
              <div className="mt-3 px-2 py-1.5 bg-gray-800/60 rounded-lg">
                <span className="text-xs text-gray-400">
                  <span className="font-semibold text-gray-300">{fileCount}</span> files indexed
                </span>
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <div className={`w-2.5 h-2.5 rounded-full ${duckdbOk ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]' : 'bg-red-500'}`} title="DuckDB" />
              <div className={`w-2.5 h-2.5 rounded-full ${apiOk ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]' : 'bg-yellow-500'}`} title="Claude API" />
            </div>
          )}
        </div>
      </aside>

      {/* ═══ Main Content ═══ */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Bar */}
        <header className="h-14 bg-gray-950/80 backdrop-blur-sm border-b border-gray-800/60 flex items-center justify-between px-6 flex-shrink-0">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-gray-500">Parquet AI</span>
            <span className="text-gray-600">/</span>
            <span className="text-gray-300 font-medium">{currentPage}</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 bg-gray-900/80 px-3 py-1.5 rounded-full border border-gray-800">
              <Database size={13} className="text-blue-400" />
              <span className="text-xs font-medium text-gray-300">{fileCount} Files</span>
            </div>
            <button className="p-2 text-gray-500 hover:text-gray-300 hover:bg-gray-800 rounded-lg transition-colors">
              <Settings size={16} />
            </button>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function StatusRow({ label, ok }) {
  return (
    <div className="flex items-center justify-between px-2 py-1">
      <span className="text-xs text-gray-500">{label}</span>
      <div className="flex items-center gap-1.5">
        <div className={`w-2 h-2 rounded-full transition-colors ${
          ok ? 'bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.5)]' : ok === false ? 'bg-red-500' : 'bg-yellow-500'
        }`} />
        <span className={`text-[10px] font-medium ${ok ? 'text-green-400' : 'text-gray-500'}`}>
          {ok ? 'Ready' : 'Off'}
        </span>
      </div>
    </div>
  );
}

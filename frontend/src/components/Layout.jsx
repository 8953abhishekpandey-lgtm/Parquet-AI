import { useState, useEffect } from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { Upload, Database, MessageSquare, Bug, BarChart2, CheckCircle2, XCircle } from 'lucide-react';

export default function Layout() {
  const [health, setHealth] = useState({ qdrant: true, duckdb: true });
  const [fileCount, setFileCount] = useState(0);
  const location = useLocation();
  const [credits, setCredits] = useState(15000); // placeholder or from context

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await fetch('http://localhost:8000/api/health');
        if (res.ok) {
          const data = await res.json();
          setHealth(data);
        }
      } catch (err) {
        console.error(err);
        setHealth({ qdrant: false, duckdb: false });
      }
    };
    const fetchFiles = async () => {
      try {
        const res = await fetch('http://localhost:8000/api/files');
        if (res.ok) {
          const data = await res.json();
          setFileCount(data.length);
        }
      } catch (err) {
        console.error(err);
      }
    };
    fetchHealth();
    fetchFiles();
  }, [location.pathname]);

  const navItems = [
    { name: 'Upload Files', path: '/upload', icon: Upload },
    { name: 'Schema Explorer', path: '/schema', icon: Database },
    { name: 'AI Query', path: '/query', icon: MessageSquare },
    { name: 'Debug Panel', path: '/debug', icon: Bug },
    { name: 'Results', path: '/results', icon: BarChart2 },
  ];

  return (
    <div className="flex h-screen bg-gray-950 text-white font-sans overflow-hidden">
      {/* Sidebar */}
      <aside className="w-60 bg-gray-900 border-r border-gray-800 flex flex-col flex-shrink-0">
        <div className="p-6 border-b border-gray-800">
          <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-blue-600 bg-clip-text text-transparent">
            DataRAG Enterprise
          </h1>
        </div>
        
        <nav className="flex-1 py-4">
          <ul className="space-y-1 px-3">
            {navItems.map((item) => (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2 rounded-md transition-colors ${
                      isActive ? 'bg-blue-600 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                    }`
                  }
                >
                  <item.icon size={18} />
                  <span className="font-medium">{item.name}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <div className="p-4 border-t border-gray-800 bg-gray-900">
          <div className="flex flex-col space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Qdrant Vector DB</span>
              {health.qdrant ? (
                <div className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]"></div>
              ) : (
                <div className="w-2 h-2 rounded-full bg-red-500"></div>
              )}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-400">DuckDB Engine</span>
              {health.duckdb ? (
                <div className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]"></div>
              ) : (
                <div className="w-2 h-2 rounded-full bg-red-500"></div>
              )}
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
        {/* Top Header */}
        <header className="h-16 bg-gray-950 border-b border-gray-800 flex items-center justify-between px-6 flex-shrink-0">
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <span className="capitalize">{location.pathname.replace('/', '') || 'Upload'}</span>
            <span>/</span>
            <span className="text-gray-300">Workspace</span>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 bg-gray-800 px-3 py-1.5 rounded-full border border-gray-700">
              <Database size={14} className="text-blue-400" />
              <span className="text-sm font-medium">{fileCount} Files Indexed</span>
            </div>
            <div className="flex items-center gap-2 bg-gray-800 px-3 py-1.5 rounded-full border border-gray-700">
              <span className="text-sm font-medium">{credits} Tokens</span>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto p-6 relative">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

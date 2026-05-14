import {
  Upload, Columns3, MessageSquare, Bug, Database, HardDrive
} from "lucide-react";

const NAV_ITEMS = [
  { id: "upload", icon: Upload, label: "Upload" },
  { id: "explorer", icon: Columns3, label: "Explorer" },
  { id: "chat", icon: MessageSquare, label: "Chat" },
  { id: "debug", icon: Bug, label: "Debug" },
];

export default function Sidebar({ activeTab, onTabChange, datasetCount }) {
  return (
    <aside className="sidebar" id="sidebar-nav">
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">
          <Database className="h-5 w-5" />
        </div>
        <span className="sidebar-logo-text">Parquet AI</span>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              id={`nav-${item.id}`}
              type="button"
              className={`sidebar-nav-item ${isActive ? "active" : ""}`}
              onClick={() => onTabChange(item.id)}
              title={item.label}
            >
              <Icon className="h-5 w-5" />
              <span>{item.label}</span>
              {item.id === "upload" && datasetCount > 0 && (
                <span className="sidebar-badge">{datasetCount}</span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Bottom info */}
      <div className="sidebar-footer">
        <div className="sidebar-footer-item">
          <HardDrive className="h-3.5 w-3.5" />
          <span>Local Processing</span>
        </div>
      </div>
    </aside>
  );
}

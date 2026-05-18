import { useState, useEffect, useMemo } from 'react';
import {
  Database, Search, Link as LinkIcon, Hash, AlignLeft,
  Calendar, ToggleLeft, ChevronDown, ChevronRight, FileText, Layers
} from 'lucide-react';
import { getAllSchemas } from '../services/api';

export default function SchemaPage() {
  const [schemasData, setSchemasData] = useState(null);
  const [activeFile, setActiveFile] = useState(null);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState(null);
  const [sortDir, setSortDir] = useState('asc');
  const [joinExpanded, setJoinExpanded] = useState(true);

  useEffect(() => {
    const fetchSchemas = async () => {
      try {
        const data = await getAllSchemas();
        setSchemasData(data);
        if (data.schemas?.length > 0) {
          setActiveFile(data.schemas[0].filename);
        }
      } catch (e) {
        console.error('Failed to fetch schemas:', e);
      }
    };
    fetchSchemas();
  }, []);

  const activeSchema = useMemo(() => {
    if (!schemasData?.schemas || !activeFile) return null;
    return schemasData.schemas.find(s => s.filename === activeFile);
  }, [schemasData, activeFile]);

  const filteredColumns = useMemo(() => {
    if (!activeSchema?.columns) return [];
    let cols = activeSchema.columns.filter(c =>
      c.name.toLowerCase().includes(search.toLowerCase())
    );
    if (sortBy) {
      cols = [...cols].sort((a, b) => {
        const valA = a[sortBy] || '';
        const valB = b[sortBy] || '';
        if (sortDir === 'asc') return String(valA).localeCompare(String(valB));
        return String(valB).localeCompare(String(valA));
      });
    }
    return cols;
  }, [activeSchema, search, sortBy, sortDir]);

  const handleSort = (col) => {
    if (sortBy === col) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(col);
      setSortDir('asc');
    }
  };

  const getTypeColor = (type) => {
    const t = (type || '').toLowerCase();
    if (t.includes('int') || t.includes('bigint')) return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
    if (t.includes('double') || t.includes('float') || t.includes('decimal')) return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
    if (t.includes('varchar') || t.includes('string')) return 'bg-green-500/10 text-green-400 border-green-500/20';
    if (t.includes('date') || t.includes('timestamp')) return 'bg-purple-500/10 text-purple-400 border-purple-500/20';
    if (t.includes('bool')) return 'bg-orange-500/10 text-orange-400 border-orange-500/20';
    return 'bg-gray-500/10 text-gray-400 border-gray-500/20';
  };

  const getTypeIcon = (type) => {
    const t = (type || '').toLowerCase();
    if (t.includes('int') || t.includes('double') || t.includes('float') || t.includes('decimal') || t.includes('bigint')) return <Hash size={12} />;
    if (t.includes('varchar') || t.includes('string')) return <AlignLeft size={12} />;
    if (t.includes('date') || t.includes('timestamp')) return <Calendar size={12} />;
    if (t.includes('bool')) return <ToggleLeft size={12} />;
    return <Database size={12} />;
  };

  const joinMap = schemasData?.join_map || {};
  const totalRows = schemasData?.total_rows || 0;
  const totalCols = schemasData?.total_columns || 0;
  const totalFiles = schemasData?.total_files || 0;

  return (
    <div className="space-y-6 p-6 animate-fade-in max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Schema Explorer</h1>
        <p className="text-gray-400 mt-1 text-sm">Browse column structures of all uploaded files.</p>
      </div>

      {/* File Tabs */}
      <div className="flex border-b border-gray-800 gap-1 overflow-x-auto">
        {(schemasData?.schemas || []).map((s) => (
          <button
            key={s.filename}
            onClick={() => setActiveFile(s.filename)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-all whitespace-nowrap ${
              activeFile === s.filename
                ? 'border-blue-500 text-blue-400 bg-blue-500/5'
                : 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
            }`}
          >
            <FileText size={14} />
            {s.filename}
            <span className={`text-xs px-1.5 py-0.5 rounded-full ${
              activeFile === s.filename ? 'bg-blue-500/15 text-blue-300' : 'bg-gray-800 text-gray-500'
            }`}>
              {(s.row_count || 0).toLocaleString()}
            </span>
          </button>
        ))}
        {(!schemasData?.schemas || schemasData.schemas.length === 0) && (
          <span className="text-gray-500 py-3 px-4 text-sm">No files available. Upload parquet files first.</span>
        )}
      </div>

      {/* Stats Bar */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Total Rows', value: totalRows.toLocaleString(), icon: Layers },
          { label: 'Total Columns', value: totalCols, icon: Database },
          { label: 'Files Loaded', value: totalFiles, icon: FileText },
          { label: 'Join Columns', value: Object.keys(joinMap).length, icon: LinkIcon },
        ].map((stat) => (
          <div key={stat.label} className="bg-gray-900 border border-gray-800 p-4 rounded-xl">
            <div className="flex items-center gap-2 mb-2">
              <stat.icon size={14} className="text-gray-500" />
              <p className="text-xs text-gray-400 font-medium">{stat.label}</p>
            </div>
            <p className="text-2xl font-bold text-white">{stat.value}</p>
          </div>
        ))}
      </div>

      {activeSchema && (
        <>
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              type="text"
              placeholder="Search columns..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full bg-gray-900 border border-gray-800 rounded-xl py-3 pl-10 pr-4 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30 transition-all text-sm placeholder-gray-500"
            />
          </div>

          {/* Column Table */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden shadow-lg">
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-gray-400 bg-gray-800/50 uppercase border-b border-gray-800">
                  <tr>
                    <th className="px-5 py-3.5 font-medium cursor-pointer hover:text-gray-200" onClick={() => handleSort('name')}>
                      Name {sortBy === 'name' && (sortDir === 'asc' ? '↑' : '↓')}
                    </th>
                    <th className="px-5 py-3.5 font-medium cursor-pointer hover:text-gray-200" onClick={() => handleSort('dtype')}>
                      Type {sortBy === 'dtype' && (sortDir === 'asc' ? '↑' : '↓')}
                    </th>
                    <th className="px-5 py-3.5 font-medium">Null %</th>
                    <th className="px-5 py-3.5 font-medium">Unique</th>
                    <th className="px-5 py-3.5 font-medium">Min / Max</th>
                    <th className="px-5 py-3.5 font-medium">Sample Values</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/60">
                  {filteredColumns.map((col) => (
                    <tr key={col.name} className="hover:bg-gray-800/30 transition-colors">
                      <td className="px-5 py-3.5 font-medium text-gray-200">{col.name}</td>
                      <td className="px-5 py-3.5">
                        <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md border text-xs font-medium ${getTypeColor(col.dtype)}`}>
                          {getTypeIcon(col.dtype)}
                          {col.dtype}
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-2">
                          <div className="w-14 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                            <div className="h-full bg-red-500/80 rounded-full" style={{ width: `${Math.min(col.null_pct || 0, 100)}%` }} />
                          </div>
                          <span className="text-xs text-gray-500">{(col.null_pct || 0).toFixed(1)}%</span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-xs text-gray-400">
                        {(col.unique_count || 0).toLocaleString()}
                      </td>
                      <td className="px-5 py-3.5 text-xs text-gray-400">
                        {col.min != null ? (
                          <div className="flex flex-col gap-0.5">
                            <span>{String(col.min)}</span>
                            <span className="text-gray-600">to</span>
                            <span>{String(col.max)}</span>
                          </div>
                        ) : (
                          <span className="text-gray-600">—</span>
                        )}
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex flex-wrap gap-1.5">
                          {(col.sample_values || []).slice(0, 5).map((v, i) => (
                            <span key={i} className="px-2 py-0.5 bg-gray-800 text-gray-300 rounded border border-gray-700 text-xs truncate max-w-[120px]">
                              {String(v)}
                            </span>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                  {filteredColumns.length === 0 && (
                    <tr>
                      <td colSpan="6" className="px-5 py-10 text-center text-gray-500">
                        No columns found{search ? ` matching "${search}"` : ''}.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* ═══ Join Map ═══ */}
      {Object.keys(joinMap).length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <button
            onClick={() => setJoinExpanded(!joinExpanded)}
            className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-800/30 transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-blue-500/10 flex items-center justify-center">
                <LinkIcon className="w-4 h-4 text-blue-400" />
              </div>
              <div className="text-left">
                <h3 className="text-sm font-semibold text-white">Cross-File Join Opportunities</h3>
                <p className="text-xs text-gray-400">{Object.keys(joinMap).length} shared columns detected</p>
              </div>
            </div>
            {joinExpanded ? <ChevronDown size={16} className="text-gray-400" /> : <ChevronRight size={16} className="text-gray-400" />}
          </button>

          {joinExpanded && (
            <div className="px-6 pb-5 space-y-3">
              {Object.entries(joinMap).map(([col, fileList]) => (
                <div key={col} className="bg-gray-950 border border-gray-800 rounded-lg p-4 flex items-center gap-4">
                  <div className="min-w-[140px]">
                    <span className="font-medium text-blue-400 text-sm">{col}</span>
                  </div>
                  <span className="text-gray-600 text-xs">shared in</span>
                  <div className="flex flex-wrap gap-2">
                    {fileList.map((f, i) => (
                      <span key={i} className="px-3 py-1.5 bg-gray-800 border border-gray-700 text-gray-300 text-xs rounded-lg font-medium">
                        {f}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {Object.keys(joinMap).length === 0 && schemasData?.schemas?.length > 1 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 text-center text-gray-500 text-sm">
          <LinkIcon className="w-8 h-8 mx-auto mb-2 text-gray-700" />
          No shared columns detected across files.
        </div>
      )}
    </div>
  );
}

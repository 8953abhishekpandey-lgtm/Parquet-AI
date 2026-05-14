import { useState, useEffect } from 'react';
import { Database, Search, Link as LinkIcon, CheckCircle2, ChevronRight, Hash, AlignLeft, Calendar, ToggleLeft } from 'lucide-react';

export default function SchemaPage() {
  const [files, setFiles] = useState([]);
  const [activeFile, setActiveFile] = useState(null);
  const [schema, setSchema] = useState(null);
  const [search, setSearch] = useState('');
  const [joinMap, setJoinMap] = useState({});

  useEffect(() => {
    const fetchFiles = async () => {
      try {
        const res = await fetch('http://localhost:8000/api/files');
        if (res.ok) {
          const data = await res.json();
          setFiles(data);
          if (data.length > 0) setActiveFile(data[0].dataset_id);
          
          // Compute simple join map locally for visual
          const jm = {};
          data.forEach(f => {
            f.columns.forEach(c => {
              if (!jm[c.name]) jm[c.name] = [];
              jm[c.name].push(f.filename);
            });
          });
          const filteredJm = {};
          for (const k in jm) {
            if (jm[k].length > 1) filteredJm[k] = jm[k];
          }
          setJoinMap(filteredJm);
        }
      } catch (e) { console.error(e); }
    };
    fetchFiles();
  }, []);

  useEffect(() => {
    if (!activeFile) return;
    const fetchSchema = async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/schema/${activeFile}`);
        if (res.ok) {
          const data = await res.json();
          setSchema(data);
        }
      } catch (e) { console.error(e); }
    };
    fetchSchema();
  }, [activeFile]);

  const getTypeColor = (type) => {
    const t = type.toLowerCase();
    if (t.includes('int') || t.includes('float') || t.includes('double')) return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
    if (t.includes('string') || t.includes('varchar')) return 'bg-green-500/10 text-green-400 border-green-500/20';
    if (t.includes('date') || t.includes('time')) return 'bg-purple-500/10 text-purple-400 border-purple-500/20';
    if (t.includes('bool')) return 'bg-orange-500/10 text-orange-400 border-orange-500/20';
    return 'bg-gray-500/10 text-gray-400 border-gray-500/20';
  };

  const getTypeIcon = (type) => {
    const t = type.toLowerCase();
    if (t.includes('int') || t.includes('float') || t.includes('double')) return <Hash size={14} />;
    if (t.includes('string') || t.includes('varchar')) return <AlignLeft size={14} />;
    if (t.includes('date') || t.includes('time')) return <Calendar size={14} />;
    if (t.includes('bool')) return <ToggleLeft size={14} />;
    return <Database size={14} />;
  };

  const filteredColumns = schema?.columns?.filter(c => c.name.toLowerCase().includes(search.toLowerCase())) || [];

  return (
    <div className="space-y-6 animate-fade-in max-w-6xl mx-auto pb-12">
      {/* File Tabs */}
      <div className="flex border-b border-gray-800 space-x-2">
        {files.map(f => (
          <button
            key={f.dataset_id}
            onClick={() => setActiveFile(f.dataset_id)}
            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeFile === f.dataset_id 
                ? 'border-blue-500 text-blue-400 bg-blue-500/5 rounded-t-lg' 
                : 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-gray-800/50 rounded-t-lg'
            }`}
          >
            {f.filename}
          </button>
        ))}
        {files.length === 0 && <span className="text-gray-500 py-3">No files available</span>}
      </div>

      {schema && (
        <>
          {/* Stats Bar */}
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-gray-900 border border-gray-800 p-4 rounded-xl flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Total Rows</p>
                <p className="text-xl font-semibold mt-1">{schema.row_count.toLocaleString()}</p>
              </div>
            </div>
            <div className="bg-gray-900 border border-gray-800 p-4 rounded-xl flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Total Columns</p>
                <p className="text-xl font-semibold mt-1">{schema.columns.length}</p>
              </div>
            </div>
            <div className="bg-gray-900 border border-gray-800 p-4 rounded-xl flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Indexed Vectors</p>
                <p className="text-xl font-semibold mt-1">{schema.metadata_count || 0}</p>
              </div>
            </div>
            <div className="bg-gray-900 border border-gray-800 p-4 rounded-xl flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Status</p>
                <div className="flex items-center gap-2 mt-1">
                  <div className="w-2 h-2 bg-green-500 rounded-full shadow-[0_0_8px_rgba(34,197,94,0.6)]"></div>
                  <span className="font-medium text-green-400 text-sm">Ready</span>
                </div>
              </div>
            </div>
          </div>

          {/* Search Bar */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500" />
            <input 
              type="text" 
              placeholder="Filter columns..." 
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full bg-gray-900 border border-gray-800 rounded-xl py-3 pl-10 pr-4 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all text-sm placeholder-gray-500"
            />
          </div>

          {/* Schema Table */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden shadow-lg">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-gray-400 bg-gray-800/50 uppercase border-b border-gray-800">
                <tr>
                  <th className="px-6 py-4 font-medium">Column Name</th>
                  <th className="px-6 py-4 font-medium">Data Type</th>
                  <th className="px-6 py-4 font-medium">Null %</th>
                  <th className="px-6 py-4 font-medium">Min / Max</th>
                  <th className="px-6 py-4 font-medium max-w-xs">Sample Values</th>
                  <th className="px-6 py-4 font-medium text-center">Vectors</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {filteredColumns.map(col => {
                  const nullCount = col.stats?.null_count || 0;
                  const total = (col.stats?.distinct_count || 0) + nullCount;
                  const nullPct = total > 0 ? (nullCount / total) * 100 : 0;

                  return (
                    <tr key={col.name} className="hover:bg-gray-800/30 transition-colors">
                      <td className="px-6 py-4 font-medium text-gray-200">{col.name}</td>
                      <td className="px-6 py-4">
                        <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-xs font-medium ${getTypeColor(col.dtype)}`}>
                          {getTypeIcon(col.dtype)}
                          {col.dtype}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-16 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                            <div className="h-full bg-red-500" style={{ width: `${nullPct}%` }}></div>
                          </div>
                          <span className="text-gray-500 text-xs">{nullPct.toFixed(1)}%</span>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-xs text-gray-400">
                        {col.stats?.min_value != null && (
                          <div className="flex flex-col">
                            <span>Min: {col.stats.min_value}</span>
                            <span>Max: {col.stats.max_value}</span>
                          </div>
                        )}
                        {col.stats?.min_value == null && <span className="text-gray-600">-</span>}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex flex-wrap gap-1.5">
                          {col.sample_values?.slice(0, 3).map((v, i) => (
                            <span key={i} className="px-2 py-0.5 bg-gray-800 text-gray-300 rounded border border-gray-700 text-xs truncate max-w-[100px]">
                              {String(v)}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <CheckCircle2 size={18} className="text-green-500 mx-auto" />
                      </td>
                    </tr>
                  );
                })}
                {filteredColumns.length === 0 && (
                  <tr><td colSpan="6" className="px-6 py-8 text-center text-gray-500">No columns found.</td></tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Join Map Section */}
          {Object.keys(joinMap).length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mt-8">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
                  <LinkIcon className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold">Join Map (Cross-File Relationships)</h3>
                  <p className="text-sm text-gray-400">Automatically detected columns shared across multiple files.</p>
                </div>
              </div>
              
              <div className="grid gap-4">
                {Object.entries(joinMap).map(([col, files]) => (
                  <div key={col} className="bg-gray-950 border border-gray-800 rounded-lg p-4 flex items-center">
                    <div className="w-48 font-medium text-blue-400 truncate pr-4">{col}</div>
                    <div className="flex-1 flex flex-wrap items-center gap-2">
                      {files.map((f, i) => (
                        <div key={i} className="flex items-center gap-2">
                          {i > 0 && <ChevronRight size={14} className="text-gray-600" />}
                          <span className="px-3 py-1.5 bg-gray-800 border border-gray-700 text-gray-300 text-xs rounded-md font-medium">
                            {f}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

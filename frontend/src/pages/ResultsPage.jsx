import { useState, useEffect, useMemo } from 'react';
import {
  BarChart2, Clock, Zap, CheckCircle2, XCircle,
  ChevronDown, ChevronRight, Download, Database, FileText, Hash
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import toast from 'react-hot-toast';
import { getQueryHistory } from '../services/api';

const CHART_COLORS = ['#3b82f6', '#06b6d4', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#6366f1'];

export default function ResultsPage() {
  const [historyData, setHistoryData] = useState(null);
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const data = await getQueryHistory();
        setHistoryData(data);
      } catch (e) {
        console.error('Failed to load history:', e);
      }
    };
    fetchHistory();
  }, []);

  const queries = historyData?.queries || [];
  const stats = historyData?.stats || {};

  // Check if last query can be auto-charted
  const lastQuery = queries[0];
  const chartData = useMemo(() => {
    if (!lastQuery?.raw_results?.length || !lastQuery?.columns?.length) return null;
    if (lastQuery.raw_results.length > 30) return null;

    const cols = lastQuery.columns;
    // Find one string/categorical column and one numeric column
    const catCol = cols.find(c => {
      const first = lastQuery.raw_results[0]?.[c];
      return typeof first === 'string';
    });
    const numCol = cols.find(c => {
      const first = lastQuery.raw_results[0]?.[c];
      return typeof first === 'number';
    });

    if (!catCol || !numCol) return null;

    return {
      data: lastQuery.raw_results.map(row => ({
        name: String(row[catCol] || '').substring(0, 20),
        value: Number(row[numCol]) || 0,
      })),
      catCol,
      numCol,
      title: lastQuery.question,
    };
  }, [lastQuery]);

  const exportAllCSV = () => {
    if (!queries.length) return;
    const header = 'ID,Timestamp,Question,SQL,Rows,Tokens,Time_ms,Files,Attempts,Success';
    const rows = queries.map(q =>
      [
        q.id,
        q.timestamp,
        `"${(q.question || '').replace(/"/g, '""')}"`,
        `"${(q.sql || '').replace(/"/g, '""')}"`,
        q.row_count || 0,
        q.tokens_used || 0,
        q.execution_time_ms || 0,
        `"${(q.files_queried || []).join(', ')}"`,
        q.sql_attempts || 1,
        q.success ? 'Yes' : 'No',
      ].join(',')
    );
    const csv = [header, ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'query_history.csv';
    a.click();
    URL.revokeObjectURL(url);
    toast.success('History exported as CSV');
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6 p-6 animate-fade-in pb-12">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Query History</h1>
          <p className="text-gray-400 mt-1 text-sm">Review past queries, results, and performance metrics.</p>
        </div>
        {queries.length > 0 && (
          <button
            onClick={exportAllCSV}
            className="flex items-center gap-2 px-4 py-2 bg-gray-900 border border-gray-800 rounded-xl text-sm text-gray-300 hover:text-white hover:border-gray-700 transition-colors"
          >
            <Download size={14} /> Export CSV
          </button>
        )}
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Total Queries', value: stats.total_queries || 0, icon: Hash, color: 'text-blue-400' },
          { label: 'Avg Response', value: `${stats.avg_response_time_ms || 0}ms`, icon: Clock, color: 'text-cyan-400' },
          { label: 'Total Tokens', value: (stats.total_tokens || 0).toLocaleString(), icon: Zap, color: 'text-yellow-400' },
          { label: 'Success Rate', value: `${stats.success_rate || 0}%`, icon: CheckCircle2, color: 'text-green-400' },
        ].map((s) => (
          <div key={s.label} className="bg-gray-900 border border-gray-800 p-4 rounded-xl">
            <div className="flex items-center gap-2 mb-2">
              <s.icon size={14} className={s.color} />
              <p className="text-xs text-gray-400 font-medium">{s.label}</p>
            </div>
            <p className="text-2xl font-bold text-white">{s.value}</p>
          </div>
        ))}
      </div>

      {/* Auto Chart */}
      {chartData && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h3 className="text-sm font-semibold text-white mb-1">Latest Query Chart</h3>
          <p className="text-xs text-gray-400 mb-4 truncate">{chartData.title}</p>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData.data} layout="vertical" margin={{ left: 10, right: 30 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis type="number" stroke="#6b7280" fontSize={11} />
                <YAxis type="category" dataKey="name" stroke="#6b7280" fontSize={11} width={100} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#111827',
                    border: '1px solid #374151',
                    borderRadius: '8px',
                    fontSize: '12px',
                    color: '#e5e7eb',
                  }}
                />
                <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                  {chartData.data.map((_, i) => (
                    <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* History Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-gray-400 bg-gray-800/50 uppercase border-b border-gray-800">
              <tr>
                <th className="px-4 py-3 font-medium w-10">#</th>
                <th className="px-4 py-3 font-medium">Timestamp</th>
                <th className="px-4 py-3 font-medium">Question</th>
                <th className="px-4 py-3 font-medium">Files</th>
                <th className="px-4 py-3 font-medium text-right">Rows</th>
                <th className="px-4 py-3 font-medium text-right">Tokens</th>
                <th className="px-4 py-3 font-medium text-right">Time</th>
                <th className="px-4 py-3 font-medium text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {queries.map((q) => (
                <QueryRow
                  key={q.id}
                  query={q}
                  expanded={expandedId === q.id}
                  onToggle={() => setExpandedId(expandedId === q.id ? null : q.id)}
                />
              ))}
              {queries.length === 0 && (
                <tr>
                  <td colSpan="8" className="px-4 py-16 text-center text-gray-500">
                    <BarChart2 className="w-10 h-10 mx-auto mb-3 text-gray-700" />
                    <p className="font-medium">No queries yet</p>
                    <p className="text-sm text-gray-600 mt-1">Run a query from the Query page to see it here.</p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function QueryRow({ query, expanded, onToggle }) {
  const ts = query.timestamp ? new Date(query.timestamp) : null;
  const filesQueried = query.files_queried || [];

  return (
    <>
      <tr
        onClick={onToggle}
        className="hover:bg-gray-800/30 cursor-pointer transition-colors"
      >
        <td className="px-4 py-3 text-gray-500 font-mono text-xs">{query.id}</td>
        <td className="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">
          {ts ? ts.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}
        </td>
        <td className="px-4 py-3 text-gray-200 max-w-[300px] truncate text-xs">{query.question}</td>
        <td className="px-4 py-3">
          <div className="flex flex-wrap items-center gap-1 max-w-[280px]">
            {filesQueried.length > 0 && (
              <span className="text-[10px] bg-blue-500/10 text-blue-300 border border-blue-500/20 px-1.5 py-0.5 rounded">
                {filesQueried.length} files
              </span>
            )}
            {filesQueried.slice(0, 3).map((f, i) => (
              <span key={i} className="text-[10px] bg-gray-800 text-gray-400 px-1.5 py-0.5 rounded">{f}</span>
            ))}
            {filesQueried.length > 3 && (
              <span className="text-[10px] text-gray-500">+{filesQueried.length - 3} more</span>
            )}
          </div>
        </td>
        <td className="px-4 py-3 text-right text-xs text-gray-400">{query.row_count || 0}</td>
        <td className="px-4 py-3 text-right text-xs text-gray-400">{query.tokens_used || 0}</td>
        <td className="px-4 py-3 text-right text-xs text-gray-400 font-mono">{query.execution_time_ms || 0}ms</td>
        <td className="px-4 py-3 text-center">
          {query.success ? (
            <CheckCircle2 size={14} className="text-green-500 mx-auto" />
          ) : (
            <XCircle size={14} className="text-red-500 mx-auto" />
          )}
        </td>
      </tr>

      {/* Expanded Detail */}
      {expanded && (
        <tr>
          <td colSpan="8" className="bg-gray-950 px-6 py-5 border-t border-gray-800">
            <div className="grid grid-cols-2 gap-6 max-w-4xl">
              {/* Question */}
              <div>
                <h4 className="text-xs font-semibold text-gray-400 uppercase mb-2">Question</h4>
                <p className="text-sm text-gray-200">{query.question}</p>
              </div>

              {/* Files */}
              <div>
                <h4 className="text-xs font-semibold text-gray-400 uppercase mb-2">Files Queried</h4>
                <div className="flex flex-wrap gap-1.5">
                  {filesQueried.length > 0 ? filesQueried.map((f, i) => (
                    <span key={i} className="inline-flex items-center gap-1 text-[11px] bg-gray-900 border border-gray-800 text-gray-300 px-2 py-1 rounded">
                      <FileText size={11} /> {f}
                    </span>
                  )) : (
                    <span className="text-sm text-gray-500">-</span>
                  )}
                </div>
              </div>

              {/* Answer */}
              <div className="col-span-2">
                <h4 className="text-xs font-semibold text-gray-400 uppercase mb-2">Answer</h4>
                <p className="text-sm text-gray-300">{query.natural_language_answer || '—'}</p>
              </div>

              {/* SQL */}
              {query.sql && (
                <div className="col-span-2">
                  <h4 className="text-xs font-semibold text-gray-400 uppercase mb-2">SQL</h4>
                  <pre className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-xs text-green-400 font-mono overflow-x-auto">
                    {query.sql}
                  </pre>
                </div>
              )}

              {/* Results Table */}
              {query.raw_results?.length > 0 && (
                <div className="col-span-2">
                  <h4 className="text-xs font-semibold text-gray-400 uppercase mb-2">
                    Results ({query.raw_results.length} rows)
                  </h4>
                  <div className="overflow-x-auto border border-gray-800 rounded-lg">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="bg-gray-800/50">
                          {(query.columns || []).map(c => (
                            <th key={c} className="px-3 py-2 text-left text-gray-400 font-medium whitespace-nowrap">{c}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-800/40">
                        {query.raw_results.slice(0, 10).map((row, i) => (
                          <tr key={i} className={i % 2 === 0 ? 'bg-gray-900/30' : ''}>
                            {(query.columns || []).map(c => (
                              <td key={c} className="px-3 py-2 text-gray-300 whitespace-nowrap">{row[c] != null ? String(row[c]) : '—'}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Error */}
              {query.error && (
                <div className="col-span-2">
                  <h4 className="text-xs font-semibold text-red-400 uppercase mb-2">Error</h4>
                  <p className="text-sm text-red-300 bg-red-500/10 border border-red-500/20 rounded-lg p-3">{query.error}</p>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

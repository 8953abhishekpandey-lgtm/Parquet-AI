import { useState, useEffect, useMemo } from 'react';
import {
  Bug, Code2, Database, Clock, Zap, FileText,
  ChevronDown, ChevronRight, Shield, AlertTriangle
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { getQueryHistory } from '../services/api';

export default function DebugPage() {
  const [historyData, setHistoryData] = useState(null);

  useEffect(() => {
    getQueryHistory().then(setHistoryData).catch(console.error);
  }, []);

  const lastQuery = (historyData?.queries || [])[0];

  // Latency breakdown
  const latencyData = useMemo(() => {
    if (!lastQuery?.pipeline_steps?.length) return [];
    return lastQuery.pipeline_steps
      .filter(s => s.time_ms != null && s.time_ms > 0)
      .map(s => ({
        name: s.label?.replace(/\(.*\)/, '').trim() || `Step ${s.step_number || s.step}`,
        time: s.time_ms,
      }));
  }, [lastQuery]);

  // Token breakdown (estimated)
  const tokenData = useMemo(() => {
    if (!lastQuery) return null;
    const contextTokens = lastQuery.context_tokens || 0;
    const totalTokens = lastQuery.tokens_used || 0;
    // Rough estimate: split between SQL and answer
    const sqlPrompt = contextTokens;
    const sqlResponse = Math.min(120, totalTokens * 0.1);
    const answerPrompt = Math.min(180, totalTokens * 0.15);
    const answerResponse = Math.max(0, totalTokens - sqlPrompt - sqlResponse - answerPrompt);

    return {
      sqlPrompt: Math.round(sqlPrompt),
      sqlResponse: Math.round(sqlResponse),
      answerPrompt: Math.round(answerPrompt),
      answerResponse: Math.round(answerResponse),
      total: totalTokens,
      estimatedCost: (totalTokens * 0.00000025).toFixed(6),
    };
  }, [lastQuery]);

  return (
    <div className="max-w-5xl mx-auto space-y-6 p-6 animate-fade-in pb-12">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Bug size={22} className="text-purple-400" />
          Debug Panel
        </h1>
        <p className="text-gray-400 mt-1 text-sm">Technical details of the last query pipeline execution.</p>
      </div>

      {!lastQuery ? (
        <div className="text-center py-20 text-gray-500">
          <Bug className="w-12 h-12 mx-auto mb-3 text-gray-700" />
          <p className="font-medium">No query data available</p>
          <p className="text-sm text-gray-600 mt-1">Run a query from the Query page to see debug information.</p>
        </div>
      ) : (
        <>
          {/* Section 1: Question & Context */}
          <DebugSection
            title="Question & Context"
            icon={<FileText size={16} className="text-blue-400" />}
            defaultOpen={true}
          >
            <div className="space-y-4">
              <div>
                <label className="text-xs text-gray-500 uppercase font-medium">Question</label>
                <p className="text-sm text-gray-200 mt-1">{lastQuery.question}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase font-medium">Context Tokens Sent</label>
                <p className="text-sm text-gray-300 mt-1 font-mono">{lastQuery.context_tokens || 0} tokens</p>
              </div>
              <div className="flex items-center gap-2 px-3 py-2 bg-green-500/5 border border-green-500/15 rounded-lg">
                <Shield size={14} className="text-green-400" />
                <span className="text-xs text-green-400">Data rows NOT included in this context — only schema metadata</span>
              </div>
            </div>
          </DebugSection>

          {/* Section 2: SQL History */}
          <DebugSection
            title="SQL History"
            icon={<Code2 size={16} className="text-cyan-400" />}
            defaultOpen={true}
          >
            <div className="space-y-3">
              {(lastQuery.attempts_detail || []).map((attempt, i) => (
                <div key={i} className={`p-4 rounded-lg border ${attempt.error ? 'bg-red-500/5 border-red-500/20' : 'bg-gray-800/30 border-gray-800'}`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-gray-400">Attempt {attempt.attempt_number || i + 1}</span>
                    <div className="flex items-center gap-2">
                      {attempt.error ? (
                        <span className="text-xs text-red-400 flex items-center gap-1">
                          <AlertTriangle size={10} /> Failed
                        </span>
                      ) : (
                        <span className="text-xs text-green-400">✓ Success</span>
                      )}
                      <span className="text-[10px] text-gray-500 font-mono">{attempt.time_ms || 0}ms</span>
                    </div>
                  </div>
                  {attempt.sql && (
                    <pre className="bg-gray-950 border border-gray-800 rounded p-3 text-xs text-green-400 font-mono overflow-x-auto mt-2">
                      {attempt.sql}
                    </pre>
                  )}
                  {attempt.error && (
                    <div className="mt-2 px-3 py-2 bg-red-500/10 rounded text-xs text-red-300">
                      {attempt.error}
                    </div>
                  )}
                </div>
              ))}
              {(!lastQuery.attempts_detail || lastQuery.attempts_detail.length === 0) && lastQuery.sql && (
                <div className="p-4 bg-gray-800/30 border border-gray-800 rounded-lg">
                  <span className="text-xs font-semibold text-gray-400">Final SQL</span>
                  <pre className="bg-gray-950 border border-gray-800 rounded p-3 text-xs text-green-400 font-mono overflow-x-auto mt-2">
                    {lastQuery.sql}
                  </pre>
                </div>
              )}
            </div>
          </DebugSection>

          {/* Section 3: DuckDB Execution */}
          <DebugSection
            title="DuckDB Execution"
            icon={<Database size={16} className="text-yellow-400" />}
          >
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="text-xs text-gray-500 uppercase font-medium">Execution Time</label>
                <p className="text-lg font-bold text-white mt-1">{lastQuery.duckdb_time_ms || 0}ms</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase font-medium">Rows Returned</label>
                <p className="text-lg font-bold text-white mt-1">{lastQuery.row_count || 0}</p>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase font-medium">Files Queried</label>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {(lastQuery.files_queried || []).map((f, i) => (
                    <span key={i} className="px-2 py-0.5 bg-gray-800 text-gray-300 rounded text-xs border border-gray-700">{f}</span>
                  ))}
                  {(!lastQuery.files_queried || lastQuery.files_queried.length === 0) && (
                    <span className="text-gray-500 text-xs">—</span>
                  )}
                </div>
              </div>
            </div>
          </DebugSection>

          {/* Section 4: Latency Breakdown */}
          {latencyData.length > 0 && (
            <DebugSection
              title="Latency Breakdown"
              icon={<Clock size={16} className="text-purple-400" />}
              defaultOpen={true}
            >
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={latencyData} layout="vertical" margin={{ left: 5, right: 30 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                    <XAxis type="number" stroke="#6b7280" fontSize={10} tickFormatter={v => `${v}ms`} />
                    <YAxis type="category" dataKey="name" stroke="#6b7280" fontSize={10} width={130} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: '8px', fontSize: '11px', color: '#e5e7eb' }}
                      formatter={v => [`${v}ms`, 'Time']}
                    />
                    <Bar dataKey="time" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-3 px-3 py-2 bg-gray-800/30 rounded-lg text-xs text-gray-400">
                Total: <span className="font-semibold text-white">{lastQuery.execution_time_ms || 0}ms</span>
              </div>
            </DebugSection>
          )}

          {/* Section 5: Tokens */}
          {tokenData && (
            <DebugSection
              title="Tokens Used"
              icon={<Zap size={16} className="text-yellow-400" />}
            >
              <div className="space-y-2">
                <TokenRow label="SQL prompt" value={tokenData.sqlPrompt} />
                <TokenRow label="SQL response" value={tokenData.sqlResponse} />
                <TokenRow label="Answer prompt" value={tokenData.answerPrompt} />
                <TokenRow label="Answer response" value={tokenData.answerResponse} />
                <div className="border-t border-gray-800 pt-2 mt-3 flex items-center justify-between">
                  <span className="text-xs font-semibold text-gray-300">Total</span>
                  <span className="text-sm font-bold text-white">{tokenData.total} tokens</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500">Estimated cost</span>
                  <span className="text-xs text-yellow-400 font-mono">${tokenData.estimatedCost}</span>
                </div>
              </div>
            </DebugSection>
          )}

          {/* Pipeline Steps Summary */}
          <DebugSection
            title="Pipeline Steps"
            icon={<Zap size={16} className="text-emerald-400" />}
          >
            <div className="space-y-1">
              {(lastQuery.pipeline_steps || []).map((step, i) => (
                <div key={i} className="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-gray-800/30 transition-colors">
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold ${
                    step.status === 'done' ? 'bg-green-500/15 text-green-400' :
                    step.status === 'error' ? 'bg-red-500/15 text-red-400' :
                    'bg-gray-800 text-gray-500'
                  }`}>
                    {step.step_number || step.step || i + 1}
                  </div>
                  <span className="text-xs text-gray-300 flex-1">{step.label}</span>
                  {step.detail && <span className="text-[10px] text-gray-500 truncate max-w-[200px]">{step.detail}</span>}
                  {step.time_ms != null && (
                    <span className="text-[10px] text-gray-600 font-mono bg-gray-800/50 px-1.5 py-0.5 rounded">{step.time_ms}ms</span>
                  )}
                </div>
              ))}
            </div>
          </DebugSection>
        </>
      )}
    </div>
  );
}

function DebugSection({ title, icon, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-5 py-4 flex items-center justify-between hover:bg-gray-800/30 transition-colors"
      >
        <div className="flex items-center gap-2.5">
          {icon}
          <span className="text-sm font-semibold text-white">{title}</span>
        </div>
        {open ? <ChevronDown size={16} className="text-gray-400" /> : <ChevronRight size={16} className="text-gray-400" />}
      </button>
      {open && <div className="px-5 pb-5">{children}</div>}
    </div>
  );
}

function TokenRow({ label, value }) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-xs text-gray-400">{label}</span>
      <span className="text-xs text-gray-300 font-mono">{value} tokens</span>
    </div>
  );
}

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Send, FileText, Copy, ChevronDown, ChevronRight, Check,
  Download, Shield, Loader2, AlertCircle, Sparkles, Clock, Zap,
  Database, CheckCircle2, XCircle, Info
} from 'lucide-react';
import toast from 'react-hot-toast';
import { listFiles, runQuery } from '../services/api';
import { streamQuery } from '../services/sseService';

const PIPELINE_LABELS = [
  'Question Received',
  'Schema Loaded',
  'Joins Detected',
  'Context Built',
  'SQL Generated',
  'SQL Validated',
  'DuckDB Executed',
  'Answer Generated',
  'Complete',
];

export default function QueryPage() {
  const [files, setFiles] = useState([]);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [pipelineSteps, setPipelineSteps] = useState([]);
  const [currentStep, setCurrentStep] = useState('');
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    listFiles().then(data => setFiles(data.files || [])).catch(() => {});
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const suggestedQuestions = [
    'Show total rows in each file',
    'What columns are available?',
    'Show the top 10 rows',
    'What is the average value?',
  ];

  const handleSend = useCallback(async () => {
    const question = input.trim();
    if (!question || loading) return;

    // Add user message
    setMessages(prev => [...prev, { role: 'user', content: question, timestamp: new Date() }]);
    setInput('');
    setLoading(true);
    setPipelineSteps([]);
    setCurrentStep('Processing...');

    try {
      // Use SSE streaming
      const abort = streamQuery(question, null, {
        onStep: (stepData) => {
          setPipelineSteps(prev => {
            const exists = prev.find(s => s.step_number === stepData.step_number || s.step === stepData.step);
            if (exists) {
              return prev.map(s => (s.step_number === stepData.step_number || s.step === stepData.step) ? { ...s, ...stepData, status: stepData.status || 'done' } : s);
            }
            return [...prev, { ...stepData, status: stepData.status || 'done' }];
          });
          setCurrentStep(stepData.label || stepData.detail || '');
        },
        onComplete: (result) => {
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: result.natural_language_answer || 'Query executed successfully.',
            sql: result.sql,
            results: result.raw_results || [],
            columns: result.columns || [],
            rowCount: result.row_count || 0,
            filesQueried: result.files_queried || [],
            executionTime: result.execution_time_ms || 0,
            duckdbTime: result.duckdb_time_ms || 0,
            tokens: result.tokens_used || 0,
            attempts: result.sql_attempts || 1,
            truncated: result.truncated || false,
            pipelineSteps: result.pipeline_steps || [],
            error: result.error,
            timestamp: new Date(),
          }]);
          // Update pipeline steps with final data
          if (result.pipeline_steps) {
            setPipelineSteps(result.pipeline_steps.map(s => ({
              ...s,
              step: s.step_number || s.step,
              status: s.status || 'done',
            })));
          }
          setLoading(false);
          setCurrentStep('');
        },
        onError: (error) => {
          // Fallback to synchronous query
          handleSyncQuery(question);
        },
      });
    } catch {
      handleSyncQuery(question);
    }
  }, [input, loading]);

  const handleSyncQuery = async (question) => {
    try {
      const result = await runQuery(question);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: result.natural_language_answer || 'Query executed.',
        sql: result.sql,
        results: result.raw_results || [],
        columns: result.columns || [],
        rowCount: result.row_count || 0,
        filesQueried: result.files_queried || [],
        executionTime: result.execution_time_ms || 0,
        duckdbTime: result.duckdb_time_ms || 0,
        tokens: result.tokens_used || 0,
        attempts: result.sql_attempts || 1,
        truncated: result.truncated || false,
        pipelineSteps: result.pipeline_steps || [],
        error: result.error,
        timestamp: new Date(),
      }]);
      if (result.pipeline_steps) {
        setPipelineSteps(result.pipeline_steps.map(s => ({ ...s, step: s.step_number || s.step, status: s.status || 'done' })));
      }
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${e.message}`,
        error: e.message,
        timestamp: new Date(),
      }]);
    }
    setLoading(false);
    setCurrentStep('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const noFiles = files.length === 0;

  return (
    <div className="flex h-full">
      {/* ═══ LEFT: Chat Panel (60%) ═══ */}
      <div className="flex-[3] flex flex-col min-w-0 border-r border-gray-800/60">
        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {messages.length === 0 && !loading && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500/15 to-cyan-500/10 flex items-center justify-center mb-4">
                <Sparkles className="w-7 h-7 text-blue-400" />
              </div>
              <h2 className="text-xl font-semibold text-white mb-2">Ask anything about your data</h2>
              <p className="text-gray-400 text-sm max-w-md mb-6">
                Your questions are converted to SQL and executed locally on DuckDB.
                Only schema metadata is sent to Claude — your data stays private.
              </p>
              {!noFiles && (
                <div className="flex flex-wrap gap-2 justify-center max-w-lg">
                  {suggestedQuestions.map((q) => (
                    <button
                      key={q}
                      onClick={() => { setInput(q); inputRef.current?.focus(); }}
                      className="px-3 py-2 bg-gray-900 border border-gray-800 rounded-xl text-xs text-gray-400 hover:text-blue-400 hover:border-blue-500/30 transition-all"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {messages.map((msg, i) => (
            <MessageBubble key={i} message={msg} />
          ))}

          {loading && (
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center flex-shrink-0">
                <Sparkles size={14} className="text-white" />
              </div>
              <div className="bg-gray-900 rounded-2xl rounded-tl-md p-4 border border-gray-800 max-w-lg">
                <div className="flex items-center gap-2 text-sm text-gray-400">
                  <Loader2 size={14} className="animate-spin text-blue-400" />
                  <span>{currentStep || 'Processing query...'}</span>
                </div>
                <div className="mt-3 space-y-2">
                  {[1, 2, 3].map(n => (
                    <div key={n} className="h-3 bg-gray-800 rounded animate-pulse" style={{ width: `${90 - n * 15}%` }} />
                  ))}
                </div>
              </div>
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        {/* Input Bar */}
        <div className="p-4 border-t border-gray-800/60 bg-gray-950/50">
          <div className="flex gap-3">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={noFiles ? 'Upload files first to start querying...' : 'Ask anything about your data...'}
              disabled={noFiles || loading}
              rows={1}
              className="flex-1 bg-gray-900 border border-gray-800 rounded-xl py-3 px-4 resize-none focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30 transition-all text-sm placeholder-gray-500 disabled:opacity-40 disabled:cursor-not-allowed min-h-[44px] max-h-[120px]"
              style={{ height: 'auto', overflow: 'hidden' }}
              onInput={(e) => { e.target.style.height = 'auto'; e.target.style.height = e.target.scrollHeight + 'px'; }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || loading || noFiles}
              className="px-4 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl transition-colors disabled:opacity-30 disabled:cursor-not-allowed flex items-center gap-2 font-medium text-sm"
            >
              <Send size={16} />
            </button>
          </div>
          {noFiles && (
            <p className="text-xs text-yellow-500/80 mt-2 flex items-center gap-1">
              <AlertCircle size={12} /> Upload parquet files first to enable queries
            </p>
          )}
        </div>
      </div>

      {/* ═══ RIGHT: Pipeline Panel (40%) ═══ */}
      <div className="flex-[2] flex flex-col bg-gray-950/50 overflow-y-auto">
        <div className="p-6">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-sm font-semibold text-white">Query Pipeline</h3>
            <Info size={13} className="text-gray-500" />
          </div>
          <p className="text-xs text-gray-500 mb-6">How your question is processed securely</p>

          {/* Pipeline Steps */}
          <div className="space-y-1">
            {PIPELINE_LABELS.map((label, idx) => {
              const stepNum = idx + 1;
              const step = pipelineSteps.find(s => (s.step_number || s.step) === stepNum);
              const isDone = step?.status === 'done';
              const isError = step?.status === 'error';
              const isRunning = loading && !step && pipelineSteps.length === idx;

              return (
                <div key={stepNum} className="flex items-center gap-3 py-2.5 px-3 rounded-lg transition-colors hover:bg-gray-900/50">
                  {/* Icon */}
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 transition-all duration-500 ${
                    isDone ? 'bg-green-500/15 text-green-400' :
                    isError ? 'bg-red-500/15 text-red-400' :
                    isRunning ? 'bg-blue-500/15 text-blue-400' :
                    'bg-gray-800/50 text-gray-600'
                  }`}>
                    {isDone ? <CheckCircle2 size={14} /> :
                     isError ? <XCircle size={14} /> :
                     isRunning ? <Loader2 size={14} className="animate-spin" /> :
                     <span className="text-[10px] font-bold">{stepNum}</span>}
                  </div>

                  {/* Label + Detail */}
                  <div className="flex-1 min-w-0">
                    <p className={`text-xs font-medium transition-colors ${
                      isDone ? 'text-gray-200' : isError ? 'text-red-400' : isRunning ? 'text-blue-400' : 'text-gray-500'
                    }`}>
                      {stepNum}. {label}
                    </p>
                    {step?.detail && (
                      <p className="text-[10px] text-gray-500 truncate mt-0.5">{step.detail}</p>
                    )}
                  </div>

                  {/* Time badge */}
                  {step?.time_ms != null && (
                    <span className="text-[10px] text-gray-600 bg-gray-800/60 px-1.5 py-0.5 rounded font-mono">
                      {step.time_ms}ms
                    </span>
                  )}
                </div>
              );
            })}
          </div>

          {/* Security Banner */}
          <div className="mt-8 p-4 bg-gray-900/60 border border-gray-800 rounded-xl">
            <div className="flex items-center gap-2 mb-2">
              <Shield size={14} className="text-green-400" />
              <span className="text-xs font-semibold text-green-400">Data Security</span>
            </div>
            <p className="text-[11px] text-gray-400 leading-relaxed">
              Your parquet data stays local. Only schema metadata (column names, types)
              and limited result rows are sent to Claude API for SQL generation and answer formatting.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// Message Bubble Component
// ═══════════════════════════════════════════════════════════
function MessageBubble({ message }) {
  const [sqlExpanded, setSqlExpanded] = useState(false);
  const [dataExpanded, setDataExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showAllRows, setShowAllRows] = useState(false);

  const isUser = message.role === 'user';

  const copySQL = () => {
    if (message.sql) {
      navigator.clipboard.writeText(message.sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const exportCSV = () => {
    if (!message.results?.length || !message.columns?.length) return;
    const header = message.columns.join(',');
    const rows = message.results.map(r => message.columns.map(c => JSON.stringify(r[c] ?? '')).join(','));
    const csv = [header, ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'query_results.csv';
    a.click();
    URL.revokeObjectURL(url);
    toast.success('CSV downloaded');
  };

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="bg-blue-600 text-white rounded-2xl rounded-tr-md px-5 py-3 max-w-lg shadow-lg shadow-blue-500/10">
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
          <p className="text-[10px] text-blue-200/60 mt-1.5 text-right">
            {message.timestamp?.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3">
      <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center flex-shrink-0 shadow-md">
        <Sparkles size={14} className="text-white" />
      </div>

      <div className="bg-gray-900 rounded-2xl rounded-tl-md border border-gray-800 shadow-lg max-w-2xl flex-1 overflow-hidden">
        {/* Answer */}
        <div className="p-5">
          {message.error && !message.content?.startsWith('Error') ? (
            <div className="flex items-start gap-2 text-red-400 text-sm">
              <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
              <p>{message.error}</p>
            </div>
          ) : (
            <div className="text-sm text-gray-200 leading-relaxed whitespace-pre-wrap"
              dangerouslySetInnerHTML={{
                __html: (message.content || '')
                  .replace(/\*\*(.+?)\*\*/g, '<strong class="text-white font-semibold">$1</strong>')
                  .replace(/\n- /g, '\n• ')
              }}
            />
          )}
        </div>

        {/* Files Queried */}
        {message.filesQueried?.length > 0 && (
          <div className="px-5 pb-3 flex flex-wrap gap-2">
            {message.filesQueried.map((f, i) => (
              <span key={i} className="inline-flex items-center gap-1 px-2 py-1 bg-gray-800 border border-gray-700 rounded-lg text-xs text-gray-400">
                <FileText size={11} /> {f}
              </span>
            ))}
          </div>
        )}

        {/* SQL Section */}
        {message.sql && (
          <div className="border-t border-gray-800">
            <button
              onClick={() => setSqlExpanded(!sqlExpanded)}
              className="w-full px-5 py-3 flex items-center justify-between hover:bg-gray-800/30 transition-colors text-xs text-gray-400"
            >
              <span className="flex items-center gap-1.5 font-medium">
                <Database size={12} />
                SQL Query
              </span>
              <div className="flex items-center gap-2">
                {message.duckdbTime > 0 && (
                  <span className="text-gray-500">Executed in {message.duckdbTime}ms</span>
                )}
                {sqlExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </div>
            </button>
            {sqlExpanded && (
              <div className="relative mx-4 mb-4">
                <pre className="bg-gray-950 border border-gray-800 rounded-lg p-4 overflow-x-auto text-xs text-green-400 font-mono leading-relaxed">
                  {message.sql}
                </pre>
                <button
                  onClick={copySQL}
                  className="absolute top-2 right-2 p-1.5 bg-gray-800 hover:bg-gray-700 rounded-md text-gray-400 hover:text-white transition-colors"
                  title="Copy SQL"
                >
                  {copied ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Results Section */}
        {message.results?.length > 0 && (
          <div className="border-t border-gray-800">
            <button
              onClick={() => setDataExpanded(!dataExpanded)}
              className="w-full px-5 py-3 flex items-center justify-between hover:bg-gray-800/30 transition-colors text-xs text-gray-400"
            >
              <span className="flex items-center gap-1.5 font-medium">
                <Zap size={12} />
                Result Data ({message.rowCount} rows)
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={(e) => { e.stopPropagation(); exportCSV(); }}
                  className="flex items-center gap-1 px-2 py-1 bg-gray-800 hover:bg-gray-700 rounded text-gray-400 hover:text-white transition-colors"
                >
                  <Download size={10} /> CSV
                </button>
                {dataExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </div>
            </button>
            {dataExpanded && (
              <div className="mx-4 mb-4 overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-gray-800/50">
                      {(message.columns || []).map(col => (
                        <th key={col} className="px-3 py-2 text-left text-gray-400 font-medium whitespace-nowrap">{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800/40">
                    {(showAllRows ? message.results : message.results.slice(0, 10)).map((row, i) => (
                      <tr key={i} className={i % 2 === 0 ? 'bg-gray-900/30' : ''}>
                        {(message.columns || []).map(col => (
                          <td key={col} className="px-3 py-2 text-gray-300 whitespace-nowrap max-w-[200px] truncate">
                            {row[col] != null ? String(row[col]) : '—'}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {message.results.length > 10 && !showAllRows && (
                  <button
                    onClick={() => setShowAllRows(true)}
                    className="w-full py-2 text-xs text-blue-400 hover:text-blue-300 transition-colors"
                  >
                    Show all {message.results.length} rows
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        {(message.tokens > 0 || message.executionTime > 0) && (
          <div className="px-5 py-2.5 bg-gray-800/20 border-t border-gray-800/60 flex items-center gap-4 text-[10px] text-gray-500">
            {message.tokens > 0 && <span>~{message.tokens} tokens</span>}
            {message.rowCount > 0 && <span>{message.rowCount} rows</span>}
            {message.attempts > 1 && <span>{message.attempts} attempts</span>}
            {message.executionTime > 0 && <span>{message.executionTime}ms total</span>}
            <span className="ml-auto">
              {message.timestamp?.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

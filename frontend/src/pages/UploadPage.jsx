import { useState, useRef, useEffect, useCallback } from 'react';
import {
  UploadCloud, FileText, Trash2, RefreshCw, CheckCircle2,
  Loader2, XCircle, AlertCircle, HardDrive
} from 'lucide-react';
import toast from 'react-hot-toast';
import { uploadFile, listFiles, deleteFile, reindexFile } from '../services/api';

const PIPELINE_STEPS = [
  { num: 1, label: 'Upload', icon: '📥' },
  { num: 2, label: 'Schema', icon: '🔍' },
  { num: 3, label: 'Stats', icon: '📊' },
  { num: 4, label: 'Join Scan', icon: '🔗' },
  { num: 5, label: 'Ready', icon: '✅' },
];

export default function UploadPage() {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [pipelineSteps, setPipelineSteps] = useState([]);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);

  const fetchFiles = useCallback(async () => {
    try {
      const data = await listFiles();
      setFiles(data.files || []);
    } catch (e) {
      console.error('Failed to fetch files:', e);
    }
  }, []);

  useEffect(() => { fetchFiles(); }, [fetchFiles]);

  const handleUpload = async (fileList) => {
    const parquetFiles = Array.from(fileList).filter(f => f.name.endsWith('.parquet'));
    if (!parquetFiles.length) {
      toast.error('Only .parquet files are accepted');
      return;
    }

    setUploading(true);

    for (const file of parquetFiles) {
      setUploadProgress(0);
      setPipelineSteps([]);

      try {
        const result = await uploadFile(file, (pct) => setUploadProgress(pct));

        // Show pipeline steps from response
        if (result.pipeline_steps) {
          setPipelineSteps(result.pipeline_steps);
        }

        toast.success(`${file.name} uploaded and indexed successfully`);
      } catch (e) {
        toast.error(`Failed to upload ${file.name}: ${e.message}`);
        setPipelineSteps(prev => [...prev, { step: 0, label: 'Error', status: 'error', detail: e.message }]);
      }
    }

    await fetchFiles();
    setTimeout(() => {
      setUploading(false);
      setPipelineSteps([]);
      setUploadProgress(0);
    }, 2500);

    // Reset file input
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDelete = async (filename) => {
    if (!confirm(`Delete "${filename}" and its metadata?`)) return;
    try {
      await deleteFile(filename);
      toast.success(`${filename} deleted`);
      await fetchFiles();
    } catch (e) {
      toast.error(`Delete failed: ${e.message}`);
    }
  };

  const handleReindex = async (filename) => {
    try {
      await reindexFile(filename);
      toast.success(`${filename} re-indexed`);
      await fetchFiles();
    } catch (e) {
      toast.error(`Re-index failed: ${e.message}`);
    }
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files);
  };

  const maxStep = pipelineSteps.length > 0
    ? Math.max(...pipelineSteps.map(s => s.step))
    : 0;

  return (
    <div className="max-w-4xl mx-auto space-y-8 p-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Upload Data Files</h1>
        <p className="text-gray-400 mt-1 text-sm">Upload .parquet files. Your data never leaves this system.</p>
      </div>

      {/* ═══ Drop Zone ═══ */}
      <div
        className={`relative border-2 border-dashed rounded-2xl p-16 text-center cursor-pointer transition-all duration-300 group
          ${dragActive
            ? 'border-blue-400 bg-blue-500/10 shadow-[0_0_40px_rgba(59,130,246,0.15)]'
            : 'border-gray-700 bg-gray-900/50 hover:border-blue-500/50 hover:bg-gray-900'
          } ${uploading ? 'pointer-events-none opacity-60' : ''}`}
        onClick={() => !uploading && fileInputRef.current?.click()}
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
      >
        <input
          type="file"
          multiple
          accept=".parquet"
          className="hidden"
          ref={fileInputRef}
          onChange={(e) => handleUpload(e.target.files)}
        />

        <div className={`w-16 h-16 mx-auto mb-5 rounded-2xl flex items-center justify-center transition-all duration-300
          ${dragActive ? 'bg-blue-500/20 scale-110' : 'bg-gray-800 group-hover:bg-blue-500/10 group-hover:scale-105'}`}>
          <UploadCloud className={`w-8 h-8 transition-colors ${dragActive ? 'text-blue-400' : 'text-gray-400 group-hover:text-blue-400'}`} />
        </div>

        <h3 className="text-xl font-semibold mb-2">
          {dragActive ? 'Drop files here' : 'Drag & drop .parquet files here'}
        </h3>
        <p className="text-gray-500 text-sm mb-1">or click to browse</p>
        <p className="text-gray-600 text-xs">Supports multiple files · Max 500MB per file</p>

        {/* Upload Progress Bar */}
        {uploading && uploadProgress > 0 && (
          <div className="mt-6 max-w-sm mx-auto">
            <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
            <p className="text-xs text-gray-400 mt-2">{uploadProgress}% uploaded</p>
          </div>
        )}
      </div>

      {/* ═══ Pipeline Stepper ═══ */}
      {(uploading || pipelineSteps.length > 0) && (
        <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 shadow-lg animate-slide-up">
          <h4 className="text-sm font-semibold text-gray-400 mb-5 uppercase tracking-wider">Processing Pipeline</h4>
          <div className="flex items-start justify-between">
            {PIPELINE_STEPS.map((step, idx) => {
              const done = maxStep >= step.num;
              const current = maxStep === step.num - 1 && uploading;
              const matchedStep = pipelineSteps.find(s => s.step === step.num);

              return (
                <div key={step.num} className="flex flex-col items-center flex-1 relative">
                  {/* Connector */}
                  {idx > 0 && (
                    <div className={`absolute top-4 -left-1/2 w-full h-0.5 transition-colors duration-500 ${
                      done ? 'bg-green-500/40' : 'bg-gray-800'
                    }`} />
                  )}

                  {/* Step Circle */}
                  <div className={`relative z-10 w-9 h-9 rounded-full flex items-center justify-center mb-2.5 transition-all duration-500
                    ${done
                      ? 'bg-green-500/15 border-2 border-green-500/50 text-green-400'
                      : current
                        ? 'bg-blue-500/15 border-2 border-blue-500/50 text-blue-400'
                        : 'bg-gray-800 border-2 border-gray-700 text-gray-500'
                    }`}>
                    {done ? <CheckCircle2 size={16} /> : current ? <Loader2 size={16} className="animate-spin" /> : <span className="text-xs font-bold">{step.num}</span>}
                  </div>

                  <span className={`text-xs font-medium text-center transition-colors ${
                    done ? 'text-green-400' : current ? 'text-blue-400' : 'text-gray-500'
                  }`}>
                    {step.label}
                  </span>

                  {matchedStep?.detail && (
                    <span className="text-[10px] text-gray-500 text-center mt-1 max-w-[100px] truncate">
                      {matchedStep.detail}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ═══ Uploaded Files List ═══ */}
      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
          <HardDrive size={18} className="text-gray-400" />
          Indexed Files
          {files.length > 0 && (
            <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded-full">{files.length}</span>
          )}
        </h3>

        <div className="grid gap-3">
          {files.map((f) => (
            <div
              key={f.filename}
              className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-center justify-between hover:border-gray-700 transition-all duration-200 group"
            >
              <div className="flex items-center gap-4">
                {/* File Icon */}
                <div className="w-11 h-11 bg-gradient-to-br from-orange-500/15 to-amber-500/10 rounded-xl flex items-center justify-center border border-orange-500/20">
                  <FileText className="w-5 h-5 text-orange-400" />
                </div>

                <div>
                  <h4 className="font-medium text-white group-hover:text-blue-400 transition-colors">{f.filename}</h4>
                  <div className="flex gap-3 text-xs text-gray-400 mt-1">
                    <span>{(f.row_count || 0).toLocaleString()} rows</span>
                    <span>·</span>
                    <span>{f.col_count || 0} columns</span>
                    <span>·</span>
                    <span>{f.file_size_mb || 0} MB</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs text-green-400 bg-green-500/10 px-2.5 py-1 rounded-full border border-green-500/20 font-medium">
                  Indexed
                </span>
                <button
                  onClick={() => handleReindex(f.filename)}
                  className="p-2 text-gray-500 hover:text-blue-400 hover:bg-gray-800 rounded-lg transition-colors"
                  title="Re-index"
                >
                  <RefreshCw size={16} />
                </button>
                <button
                  onClick={() => handleDelete(f.filename)}
                  className="p-2 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                  title="Delete"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))}

          {files.length === 0 && (
            <div className="text-center py-16 text-gray-500">
              <UploadCloud className="w-12 h-12 mx-auto mb-3 text-gray-700" />
              <p className="font-medium">No files uploaded yet</p>
              <p className="text-sm text-gray-600 mt-1">Upload a .parquet file to begin.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

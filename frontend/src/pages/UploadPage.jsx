import { useState, useRef, useEffect } from 'react';
import { UploadCloud, File as FileIcon, Trash2, RefreshCw, CheckCircle2, Loader2 } from 'lucide-react';

export default function UploadPage() {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0); // 0 to 5
  const fileInputRef = useRef(null);

  const fetchFiles = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/files');
      if (res.ok) {
        const data = await res.json();
        setFiles(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchFiles();
  }, []);

  const handleUpload = async (fileList) => {
    if (!fileList.length) return;
    setUploading(true);
    setProgress(1); // Received

    const formData = new FormData();
    for (let i = 0; i < fileList.length; i++) {
      formData.append('files', fileList[i]);
    }

    // Simulate pipeline steps for demo effect since upload is synchronous
    const interval = setInterval(() => {
      setProgress(p => (p < 4 ? p + 1 : p));
    }, 800);

    try {
      const res = await fetch('http://localhost:8000/api/upload-multiple', {
        method: 'POST',
        body: formData,
      });
      if (res.ok) {
        clearInterval(interval);
        setProgress(5);
        await fetchFiles();
        setTimeout(() => { setUploading(false); setProgress(0); }, 2000);
      } else {
        clearInterval(interval);
        setUploading(false);
        setProgress(0);
        alert('Upload failed');
      }
    } catch (e) {
      clearInterval(interval);
      setUploading(false);
      setProgress(0);
      alert('Upload failed');
    }
  };

  const handleDelete = async (dataset_id) => {
    if (!confirm('Delete file and vectors?')) return;
    try {
      await fetch(`http://localhost:8000/api/files/${dataset_id}`, { method: 'DELETE' });
      await fetchFiles();
    } catch (e) {
      console.error(e);
    }
  };

  const steps = [
    { num: 1, label: "Received" },
    { num: 2, label: "Schema Extracted" },
    { num: 3, label: "Embeddings Generated" },
    { num: 4, label: "Vectors Indexed" },
    { num: 5, label: "Ready" }
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-fade-in">
      <div 
        className="border-2 border-dashed border-gray-700 rounded-xl p-12 text-center hover:border-blue-500 hover:bg-gray-800/50 transition-all cursor-pointer group bg-gray-900 shadow-lg"
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); handleUpload(e.dataTransfer.files); }}
      >
        <input 
          type="file" 
          multiple 
          accept=".parquet" 
          className="hidden" 
          ref={fileInputRef}
          onChange={(e) => handleUpload(e.target.files)}
        />
        <div className="w-16 h-16 bg-blue-500/10 rounded-full flex items-center justify-center mx-auto mb-4 group-hover:scale-110 group-hover:bg-blue-500/20 transition-transform">
          <UploadCloud className="w-8 h-8 text-blue-400" />
        </div>
        <h3 className="text-xl font-semibold mb-2">Drop .parquet files here or click to browse</h3>
        <p className="text-gray-400 text-sm">Secure local processing. Data never leaves your machine.</p>
      </div>

      {uploading && (
        <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 shadow-lg">
          <h4 className="text-sm font-semibold text-gray-400 mb-4 uppercase tracking-wider">Processing Pipeline</h4>
          <div className="flex items-center justify-between">
            {steps.map((step, idx) => {
              const isPast = progress > step.num;
              const isCurrent = progress === step.num;
              
              return (
                <div key={step.num} className="flex flex-col items-center flex-1">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center mb-2 
                    ${isPast ? 'bg-green-500/20 text-green-400 border border-green-500/50' : 
                      isCurrent ? 'bg-blue-500/20 text-blue-400 border border-blue-500/50' : 
                      'bg-gray-800 text-gray-500 border border-gray-700'}`}>
                    {isPast ? <CheckCircle2 size={16} /> : isCurrent ? <Loader2 size={16} className="animate-spin" /> : step.num}
                  </div>
                  <span className={`text-xs text-center font-medium ${isCurrent ? 'text-blue-400' : isPast ? 'text-green-400' : 'text-gray-500'}`}>
                    {step.label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-white">Indexed Files</h3>
        <div className="grid gap-4">
          {files.map(f => (
            <div key={f.dataset_id} className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-center justify-between hover:border-gray-700 transition-colors shadow-sm">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-gray-800 rounded-lg flex items-center justify-center">
                  <FileIcon className="w-5 h-5 text-gray-400" />
                </div>
                <div>
                  <h4 className="font-medium text-white">{f.filename}</h4>
                  <div className="flex gap-4 text-xs text-gray-400 mt-1">
                    <span>{f.row_count.toLocaleString()} rows</span>
                    <span>{f.columns?.length || 0} columns</span>
                    <span className="text-green-400 bg-green-400/10 px-2 py-0.5 rounded-full">Indexed</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button className="p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors" title="Re-index">
                  <RefreshCw size={18} />
                </button>
                <button 
                  onClick={() => handleDelete(f.dataset_id)}
                  className="p-2 text-red-400 hover:text-red-300 hover:bg-red-400/10 rounded-lg transition-colors" title="Delete">
                  <Trash2 size={18} />
                </button>
              </div>
            </div>
          ))}
          {files.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              No files uploaded yet.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

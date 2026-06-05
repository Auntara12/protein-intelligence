import { useState, useRef } from "react";
import { motion } from "framer-motion";
import { Upload, Download, CheckCircle, XCircle, Loader } from "lucide-react";
import { uploadBatch } from "../lib/api";
import { Link } from "react-router-dom";
import { Card } from "./ProteinPage";

const EXAMPLE_CSV = `gene,mutation
TP53,R175H
BRCA1,M1775R
EGFR,L858R
KRAS,G12D`;

export default function BatchPage() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const data = await uploadBatch(file);
      setResult(data);
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || "Upload failed");
    } finally {
      setLoading(false);
    }
  };

  const downloadExample = () => {
    const blob = new Blob([EXAMPLE_CSV], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "example_mutations.csv";
    a.click();
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-3xl font-bold text-white">Batch Mutation Analysis</h1>
        <p className="text-white/40 text-sm mt-1">
          Upload a CSV with gene and mutation columns to analyze multiple variants at once.
        </p>
      </div>

      {/* Upload zone */}
      <div
        onClick={() => fileRef.current?.click()}
        className="border-2 border-dashed border-[#0f2a1a] hover:border-[#00ffaa]/30 rounded-xl p-10 text-center cursor-pointer transition-all group"
      >
        <Upload className="w-8 h-8 text-white/20 group-hover:text-[#00ffaa]/50 mx-auto mb-3 transition-colors" />
        <p className="text-sm text-white/40 group-hover:text-white/60 transition-colors">
          {file ? file.name : "Click to upload CSV file"}
        </p>
        <p className="text-xs text-white/20 mt-1">Max 50 rows</p>
        <input
          ref={fileRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) setFile(f);
          }}
        />
      </div>

      <div className="flex gap-3">
        <button
          onClick={handleUpload}
          disabled={!file || loading}
          className="flex items-center gap-2 px-5 py-2.5 bg-[#00ffaa] hover:bg-[#00ffaa]/90 disabled:opacity-30 disabled:cursor-not-allowed text-black text-sm font-bold rounded-lg transition-all"
        >
          {loading ? <Loader className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
          {loading ? "Analyzing..." : "Run Analysis"}
        </button>
        <button
          onClick={downloadExample}
          className="flex items-center gap-2 px-4 py-2.5 border border-[#0f2a1a] hover:border-white/20 text-white/40 hover:text-white/60 text-sm rounded-lg transition-all"
        >
          <Download className="w-4 h-4" />
          Example CSV
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-red-400 text-sm p-3 rounded border border-red-500/20 bg-red-500/5">
          <XCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-4">
          {/* Summary stats */}
          <div className="grid grid-cols-3 gap-3">
            <div className="p-4 rounded-lg border border-[#0f2a1a] bg-[#0d1b12]/40">
              <div className="text-xs text-white/30 mb-1">Total</div>
              <div className="text-2xl font-bold text-white">{result.total}</div>
            </div>
            <div className="p-4 rounded-lg border border-green-500/20 bg-green-500/5">
              <div className="text-xs text-white/30 mb-1">Successful</div>
              <div className="text-2xl font-bold text-green-400">{result.successful}</div>
            </div>
            <div className="p-4 rounded-lg border border-red-500/20 bg-red-500/5">
              <div className="text-xs text-white/30 mb-1">Failed</div>
              <div className="text-2xl font-bold text-red-400">{result.failed}</div>
            </div>
          </div>

          <Card title={`Results (${result.results.length})`}>
            <div className="space-y-2">
              {result.results.map((r: any, i: number) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: i * 0.03 }}
                  className="flex items-start gap-3 p-3 rounded border border-white/5"
                >
                  {r.status === "success" ? (
                    <CheckCircle className="w-4 h-4 text-green-400 shrink-0 mt-0.5" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-bold text-[#00ffaa]">{r.gene}</span>
                      <span className="text-sm text-white/60">{r.mutation}</span>
                      {r.analysis?.is_known_pathogenic && (
                        <span className="text-xs px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/20">
                          Pathogenic
                        </span>
                      )}
                    </div>
                    {r.status === "success" && r.analysis && (
                      <>
                        <p className="text-xs text-white/40 mb-1">{r.analysis.predicted_effect}</p>
                        {r.analysis.domain && (
                          <p className="text-xs text-[#00ffaa]/50">Domain: {r.analysis.domain}</p>
                        )}
                      </>
                    )}
                    {r.status === "error" && (
                      <p className="text-xs text-red-400">{r.error}</p>
                    )}
                  </div>
                  {r.status === "success" && (
                    <Link
                      to={`/mutation/${r.gene}/${r.mutation}`}
                      className="text-xs text-[#00ffaa]/40 hover:text-[#00ffaa] transition-colors shrink-0"
                    >
                      View →
                    </Link>
                  )}
                </motion.div>
              ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Search, Zap, Database, Atom, GitBranch, ChevronRight } from "lucide-react";

const EXAMPLE_QUERIES = [
  { gene: "TP53", mutation: "R175H", label: "TP53 R175H", desc: "Classic oncogenic hotspot" },
  { gene: "BRCA1", mutation: "M1775R", label: "BRCA1 M1775R", desc: "BRCA1 pathogenic variant" },
  { gene: "EGFR", mutation: "L858R", label: "EGFR L858R", desc: "Lung cancer driver mutation" },
  { gene: "KRAS", mutation: "G12D", label: "KRAS G12D", desc: "Pancreatic cancer hotspot" },
];

const FEATURES = [
  { icon: Database, label: "UniProt + AlphaFold", desc: "Real-time protein metadata and 3D structures" },
  { icon: Atom, label: "ESM2 Embeddings", desc: "Protein language model similarity search" },
  { icon: GitBranch, label: "Mutation Analysis", desc: "Biochemical property changes + ClinVar annotations" },
  { icon: Zap, label: "FAISS Vector Search", desc: "Find functionally similar proteins instantly" },
];

export default function HomePage() {
  const [query, setQuery] = useState("");
  const navigate = useNavigate();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;

    const parts = trimmed.split(/\s+/);
    const gene = parts[0].toUpperCase();
    const mutation = parts[1]?.toUpperCase();

    if (mutation) {
      navigate(`/mutation/${gene}/${mutation}`);
    } else {
      navigate(`/protein/${gene}`);
    }
  };

  return (
    <div className="space-y-16">
      {/* Hero */}
      <div className="text-center pt-8 space-y-6">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-[#00ffaa]/20 bg-[#00ffaa]/5 text-[#00ffaa] text-xs mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-[#00ffaa] animate-pulse" />
            BioAI Research Platform
          </div>
          <h1 className="text-5xl font-bold tracking-tight leading-tight">
            <span className="text-white">Protein</span>
            <span className="text-[#00ffaa]"> Intelligence</span>
            <br />
            <span className="text-white/40 text-3xl font-normal">Search, Structure, Mutation Analysis</span>
          </h1>
        </motion.div>

        {/* Search */}
        <motion.form
          onSubmit={handleSearch}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, duration: 0.4 }}
          className="max-w-2xl mx-auto"
        >
          <div className="relative">
            <div className="absolute left-4 top-1/2 -translate-y-1/2">
              <Search className="w-4 h-4 text-[#00ffaa]/60" />
            </div>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter gene (TP53) or gene + mutation (TP53 R175H)"
              className="w-full bg-[#0d1b12] border border-[#0f2a1a] hover:border-[#00ffaa]/30 focus:border-[#00ffaa]/60 rounded-lg pl-11 pr-32 py-4 text-sm text-white placeholder-white/20 outline-none transition-all"
            />
            <button
              type="submit"
              className="absolute right-2 top-1/2 -translate-y-1/2 bg-[#00ffaa] hover:bg-[#00ffaa]/90 text-black text-xs font-bold px-4 py-2 rounded-md transition-colors"
            >
              ANALYZE
            </button>
          </div>
          <p className="text-xs text-white/20 mt-2">
            Examples: <span className="text-white/40">TP53</span> · <span className="text-white/40">TP53 R175H</span> · <span className="text-white/40">BRCA1 M1775R</span>
          </p>
        </motion.form>
      </div>

      {/* Quick examples */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
      >
        <p className="text-xs text-white/30 uppercase tracking-widest mb-4">Quick Examples</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {EXAMPLE_QUERIES.map((q) => (
            <button
              key={q.label}
              onClick={() => navigate(`/mutation/${q.gene}/${q.mutation}`)}
              className="text-left p-4 rounded-lg border border-[#0f2a1a] bg-[#0d1b12]/50 hover:border-[#00ffaa]/30 hover:bg-[#0d1b12] transition-all group"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-[#00ffaa] text-sm font-bold">{q.label}</span>
                <ChevronRight className="w-3 h-3 text-white/20 group-hover:text-[#00ffaa] transition-colors" />
              </div>
              <span className="text-white/40 text-xs">{q.desc}</span>
            </button>
          ))}
        </div>
      </motion.div>

      {/* Feature grid */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35 }}
        className="grid grid-cols-2 md:grid-cols-4 gap-4"
      >
        {FEATURES.map((f) => {
          const Icon = f.icon;
          return (
            <div
              key={f.label}
              className="p-4 rounded-lg border border-[#0f2a1a] bg-[#0d1b12]/30"
            >
              <Icon className="w-5 h-5 text-[#00ffaa]/60 mb-3" />
              <div className="text-xs font-bold text-white/70 mb-1">{f.label}</div>
              <div className="text-xs text-white/30">{f.desc}</div>
            </div>
          );
        })}
      </motion.div>
    </div>
  );
}

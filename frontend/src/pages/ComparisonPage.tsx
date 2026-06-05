import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { compareProteins, downloadPDF } from "../lib/api";
import { LoadingState, ErrorState, Card, Breadcrumb } from "./ProteinPage";
import { GitMerge, Download, ArrowRight } from "lucide-react";

export default function ComparisonPage() {
  const { gene1: paramGene1, gene2: paramGene2 } = useParams<{ gene1: string; gene2: string }>();
  const navigate = useNavigate();
  const [inputGene1, setInputGene1] = useState(paramGene1 || "TP53");
  const [inputGene2, setInputGene2] = useState(paramGene2 || "TP63");
  const [pdfLoading, setPdfLoading] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["compare", paramGene1, paramGene2],
    queryFn: () => compareProteins(paramGene1!, paramGene2!),
    enabled: !!(paramGene1 && paramGene2),
  });

  const handleCompare = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputGene1.trim() && inputGene2.trim()) {
      navigate(`/compare/${inputGene1.trim().toUpperCase()}/${inputGene2.trim().toUpperCase()}`);
    }
  };

  const handleDownloadPDF = async () => {
    if (!paramGene1) return;
    setPdfLoading(true);
    try {
      await downloadPDF(paramGene1);
    } finally {
      setPdfLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: "Search", href: "/" }, { label: "Compare" }]} />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <GitMerge className="w-7 h-7 text-[#00ffaa]" />
            Protein Comparison
          </h1>
          <p className="text-white/40 text-sm mt-1">
            Side-by-side analysis with Smith-Waterman alignment and ESM2 similarity
          </p>
        </div>
      </div>

      {/* Search form */}
      <form onSubmit={handleCompare} className="flex items-center gap-3">
        <input
          value={inputGene1}
          onChange={(e) => setInputGene1(e.target.value.toUpperCase())}
          placeholder="Gene 1 (e.g. TP53)"
          className="flex-1 bg-[#0d1b12] border border-[#0f2a1a] focus:border-[#00ffaa]/40 rounded-lg px-4 py-3 text-sm text-white placeholder-white/20 outline-none transition-all"
        />
        <ArrowRight className="w-5 h-5 text-white/20 shrink-0" />
        <input
          value={inputGene2}
          onChange={(e) => setInputGene2(e.target.value.toUpperCase())}
          placeholder="Gene 2 (e.g. TP63)"
          className="flex-1 bg-[#0d1b12] border border-[#0f2a1a] focus:border-[#00ffaa]/40 rounded-lg px-4 py-3 text-sm text-white placeholder-white/20 outline-none transition-all"
        />
        <button
          type="submit"
          className="bg-[#00ffaa] hover:bg-[#00ffaa]/90 text-black text-xs font-bold px-5 py-3 rounded-lg transition-all"
        >
          COMPARE
        </button>
      </form>

      {/* Quick presets */}
      <div className="flex gap-2 flex-wrap">
        {[
          ["TP53", "TP63"],
          ["TP53", "TP73"],
          ["BRCA1", "BRCA2"],
          ["EGFR", "ERBB2"],
          ["KRAS", "NRAS"],
        ].map(([g1, g2]) => (
          <button
            key={`${g1}-${g2}`}
            onClick={() => navigate(`/compare/${g1}/${g2}`)}
            className="text-xs px-3 py-1.5 border border-[#0f2a1a] hover:border-[#00ffaa]/30 text-white/40 hover:text-white/70 rounded transition-all"
          >
            {g1} vs {g2}
          </button>
        ))}
      </div>

      {isLoading && <LoadingState label={`Comparing ${paramGene1} and ${paramGene2}...`} />}
      {error && <ErrorState message={(error as Error).message} />}

      {data && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
          {/* Summary banner */}
          <div className="p-4 rounded-lg border border-[#00ffaa]/15 bg-[#00ffaa]/5">
            <p className="text-sm text-white/70 leading-relaxed">{data.summary}</p>
          </div>

          {/* Scores row */}
          <div className="grid grid-cols-3 gap-4">
            <ScoreCard
              label="Sequence identity"
              value={data.alignment ? `${data.alignment.identity_pct?.toFixed(1)}%` : "N/A"}
              subValue={data.alignment ? `Smith-Waterman score: ${data.alignment.score}` : ""}
              color={
                data.alignment?.identity_pct >= 50 ? "green" :
                data.alignment?.identity_pct >= 25 ? "yellow" : "red"
              }
            />
            <ScoreCard
              label="ESM2 similarity"
              value={data.esm2_similarity != null ? `${(data.esm2_similarity * 100).toFixed(1)}%` : "Not indexed"}
              subValue="Embedding cosine similarity"
              color={
                data.esm2_similarity != null && data.esm2_similarity >= 0.7 ? "green" :
                data.esm2_similarity != null && data.esm2_similarity >= 0.4 ? "yellow" : "neutral"
              }
            />
            <ScoreCard
              label="Shared domains"
              value={String(data.domain_comparison.shared.length)}
              subValue={data.domain_comparison.shared.slice(0, 2).join(", ") || "None"}
              color="neutral"
            />
          </div>

          {/* Split protein panels */}
          <div className="grid grid-cols-2 gap-4">
            <ProteinPanel gene={data.gene1} protein={data.protein1} />
            <ProteinPanel gene={data.gene2} protein={data.protein2} />
          </div>

          {/* Alignment */}
          {data.alignment && (
            <Card title="Smith-Waterman Local Alignment">
              <div className="grid grid-cols-4 gap-3 mb-4">
                <AlignStat label="Score" value={String(data.alignment.score)} />
                <AlignStat label="Identity" value={`${data.alignment.identity_pct?.toFixed(1)}%`} />
                <AlignStat label="Similarity" value={`${data.alignment.similarity_pct?.toFixed(1)}%`} />
                <AlignStat label="Gaps" value={String(data.alignment.gaps)} />
              </div>
              {data.alignment.query_aligned && (
                <div className="bg-[#080b14] rounded p-3 space-y-1 overflow-x-auto">
                  <p className="text-xs text-white/30 mb-2">
                    {data.gene1} pos {data.alignment.query_start}–{data.alignment.query_end} vs{" "}
                    {data.gene2} pos {data.alignment.target_start}–{data.alignment.target_end}
                  </p>
                  <pre className="text-xs text-[#00ffaa]/80 font-mono whitespace-pre">{data.alignment.query_aligned?.slice(0, 80)}</pre>
                  <pre className="text-xs text-white/30 font-mono whitespace-pre">{data.alignment.match_line?.slice(0, 80)}</pre>
                  <pre className="text-xs text-blue-400/80 font-mono whitespace-pre">{data.alignment.target_aligned?.slice(0, 80)}</pre>
                </div>
              )}
              <p className="text-xs text-white/40 mt-3 leading-relaxed italic">{data.alignment.interpretation}</p>
            </Card>
          )}

          {/* Domain comparison */}
          <Card title="Domain Comparison">
            <div className="grid grid-cols-3 gap-4">
              <DomainGroup
                label="Shared domains"
                items={data.domain_comparison.shared}
                color="green"
              />
              <DomainGroup
                label={`Only in ${data.gene1}`}
                items={data.domain_comparison.unique_to_gene1}
                color="teal"
              />
              <DomainGroup
                label={`Only in ${data.gene2}`}
                items={data.domain_comparison.unique_to_gene2}
                color="blue"
              />
            </div>
          </Card>

          {/* Shared diseases */}
          {data.shared_diseases.length > 0 && (
            <Card title="Shared Disease Associations">
              <div className="flex flex-wrap gap-2">
                {data.shared_diseases.map((d, i) => (
                  <span key={i} className="text-xs px-2 py-1 rounded border border-red-500/20 bg-red-500/5 text-red-400">
                    {d}
                  </span>
                ))}
              </div>
            </Card>
          )}

          {/* Download PDF */}
          <div className="flex justify-end">
            <button
              onClick={handleDownloadPDF}
              disabled={pdfLoading}
              className="flex items-center gap-2 px-5 py-2.5 bg-[#00ffaa]/10 hover:bg-[#00ffaa]/20 border border-[#00ffaa]/20 hover:border-[#00ffaa]/40 text-[#00ffaa] text-sm rounded-lg transition-all disabled:opacity-50"
            >
              <Download className="w-4 h-4" />
              {pdfLoading ? "Generating PDF..." : `Download ${data.gene1} Report PDF`}
            </button>
          </div>
        </motion.div>
      )}
    </div>
  );
}

function ProteinPanel({ gene, protein }: { gene: string; protein: any }) {
  return (
    <div className="p-4 rounded-lg border border-[#0f2a1a] bg-[#0d1b12]/40 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-lg font-bold text-[#00ffaa]">{gene}</span>
        <span className="text-xs text-white/30">{protein?.uniprot_id}</span>
      </div>
      <p className="text-xs text-white/50 leading-relaxed line-clamp-2">{protein?.protein_name}</p>
      <div className="grid grid-cols-2 gap-2 pt-1">
        <div className="text-center">
          <div className="text-sm font-bold text-white">{protein?.sequence_length?.toLocaleString()}</div>
          <div className="text-xs text-white/30">amino acids</div>
        </div>
        <div className="text-center">
          <div className="text-sm font-bold text-white">{protein?.domains?.length || 0}</div>
          <div className="text-xs text-white/30">domains</div>
        </div>
      </div>
      {protein?.subcellular_location && (
        <p className="text-xs text-white/30">📍 {protein.subcellular_location}</p>
      )}
    </div>
  );
}

function ScoreCard({ label, value, subValue, color }: {
  label: string; value: string; subValue: string;
  color: "green" | "yellow" | "red" | "neutral";
}) {
  const colorMap = {
    green: "border-green-500/20 bg-green-500/5 text-green-400",
    yellow: "border-yellow-500/20 bg-yellow-500/5 text-yellow-400",
    red: "border-red-500/20 bg-red-500/5 text-red-400",
    neutral: "border-[#0f2a1a] bg-[#0d1b12]/40 text-white",
  };
  return (
    <div className={`p-4 rounded-lg border ${colorMap[color]}`}>
      <div className="text-xs text-white/30 mb-1">{label}</div>
      <div className="text-2xl font-bold">{value}</div>
      {subValue && <div className="text-xs text-white/30 mt-1 truncate">{subValue}</div>}
    </div>
  );
}

function AlignStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center p-2 rounded bg-[#080b14]">
      <div className="text-xs text-white/30 mb-0.5">{label}</div>
      <div className="text-sm font-bold text-white">{value}</div>
    </div>
  );
}

function DomainGroup({ label, items, color }: {
  label: string; items: string[]; color: "green" | "teal" | "blue";
}) {
  const colorMap = {
    green: "text-green-400",
    teal: "text-[#00ffaa]",
    blue: "text-blue-400",
  };
  return (
    <div>
      <p className={`text-xs font-bold mb-2 ${colorMap[color]}`}>{label} ({items.length})</p>
      {items.length === 0 ? (
        <p className="text-xs text-white/20">None</p>
      ) : (
        <ul className="space-y-1">
          {items.slice(0, 5).map((d, i) => (
            <li key={i} className="text-xs text-white/50 flex items-start gap-1">
              <span className={`mt-0.5 shrink-0 ${colorMap[color]}`}>·</span>
              {d}
            </li>
          ))}
          {items.length > 5 && (
            <li className="text-xs text-white/25">+{items.length - 5} more</li>
          )}
        </ul>
      )}
    </div>
  );
}

// SimilarityPage.tsx
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getSimilarProteins } from "../lib/api";
import { LoadingState, ErrorState, Breadcrumb } from "./ProteinPage";
import { motion } from "framer-motion";

export default function SimilarityPage() {
  const { gene } = useParams<{ gene: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["similar", gene],
    queryFn: () => getSimilarProteins(gene!, 8),
    enabled: !!gene,
  });

  if (isLoading) return <LoadingState label={`Computing ESM2 embeddings for ${gene}...`} />;
  if (error) return <ErrorState message={(error as Error).message} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <Breadcrumb items={[
        { label: "Search", href: "/" },
        { label: gene!, href: `/protein/${gene}` },
        { label: "Similar Proteins" },
      ]} />

      <div>
        <h1 className="text-3xl font-bold text-[#00ffaa]">{gene}</h1>
        <p className="text-white/40 text-sm mt-1">
          Functionally similar proteins via ESM2 embeddings + FAISS cosine similarity
        </p>
        <p className="text-white/20 text-xs mt-1">
          {data.total_indexed} proteins indexed · Model: {data.model_used}
        </p>
      </div>

      <div className="space-y-3">
        {data.results.map((protein, i) => (
          <motion.div
            key={protein.gene_name}
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.05 }}
          >
            <Link to={`/protein/${protein.gene_name}`}>
              <div className="flex items-center gap-4 p-4 rounded-lg border border-[#0f2a1a] bg-[#0d1b12]/40 hover:border-[#00ffaa]/30 hover:bg-[#0d1b12] transition-all group">
                <div className="text-2xl font-bold text-white/10 w-8 text-right shrink-0">
                  {i + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-[#00ffaa] group-hover:text-[#00ffaa]">{protein.gene_name}</span>
                    {protein.uniprot_id && (
                      <span className="text-xs text-white/20">{protein.uniprot_id}</span>
                    )}
                  </div>
                  {protein.protein_name && (
                    <p className="text-xs text-white/40 truncate mt-0.5">{protein.protein_name}</p>
                  )}
                  {protein.organism && (
                    <p className="text-xs text-white/20">{protein.organism}</p>
                  )}
                </div>
                <div className="text-right shrink-0">
                  <div className="text-sm font-bold text-white">
                    {(protein.similarity_score * 100).toFixed(1)}%
                  </div>
                  <div className="text-xs text-white/30">similarity</div>
                  {/* Similarity bar */}
                  <div className="mt-1 w-24 h-1 bg-white/5 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-[#00ffaa] rounded-full transition-all"
                      style={{ width: `${protein.similarity_score * 100}%` }}
                    />
                  </div>
                </div>
              </div>
            </Link>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

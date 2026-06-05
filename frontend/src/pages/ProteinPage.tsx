// ProteinPage.tsx
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { getProtein } from "../lib/api";
import { ChevronRight, AlertCircle, Loader } from "lucide-react";

export default function ProteinPage() {
  const { gene } = useParams<{ gene: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["protein", gene],
    queryFn: () => getProtein(gene!),
    enabled: !!gene,
  });

  if (isLoading) return <LoadingState label={`Fetching ${gene} from UniProt...`} />;
  if (error) return <ErrorState message={(error as Error).message} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: "Search", href: "/" }, { label: data.gene_name }]} />

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-[#00ffaa]">{data.gene_name}</h1>
          <p className="text-white/50 text-sm mt-1">{data.protein_name}</p>
          <p className="text-white/30 text-xs">{data.organism} · UniProt: {data.uniprot_id}</p>
        </div>
        <div className="flex gap-2">
          <Link
            to={`/mutation/${data.gene_name}/R175H`}
            className="text-xs px-3 py-1.5 border border-[#0f2a1a] hover:border-[#00ffaa]/30 rounded text-white/40 hover:text-white/70 transition-all"
          >
            Analyze Mutation →
          </Link>
          <Link
            to={`/similar/${data.gene_name}`}
            className="text-xs px-3 py-1.5 border border-[#0f2a1a] hover:border-[#00ffaa]/30 rounded text-white/40 hover:text-white/70 transition-all"
          >
            Similar Proteins →
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <Stat label="Sequence Length" value={`${data.sequence_length?.toLocaleString()} aa`} />
        <Stat label="Mass" value={data.mass_da ? `${(data.mass_da / 1000).toFixed(1)} kDa` : "N/A"} />
        <Stat label="Domains" value={`${data.domains?.length || 0}`} />
      </div>

      {data.function_summary && (
        <Card title="Function">
          <p className="text-sm text-white/60 leading-relaxed">{data.function_summary}</p>
        </Card>
      )}

      {data.domains && data.domains.length > 0 && (
        <Card title={`Domains & Features (${data.domains.length})`}>
          <div className="space-y-2">
            {data.domains.slice(0, 10).map((d, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
                <div>
                  <span className="text-xs text-[#00ffaa]/80">{d.type}</span>
                  <span className="text-xs text-white/60 ml-2">{d.name}</span>
                </div>
                {d.start && d.end && (
                  <span className="text-xs text-white/30">{d.start}–{d.end}</span>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {data.disease_annotations && data.disease_annotations.length > 0 && (
        <Card title={`Disease Associations (${data.disease_annotations.length})`}>
          <div className="space-y-2">
            {data.disease_annotations.map((d, i) => (
              <div key={i} className="p-3 rounded bg-red-500/5 border border-red-500/10">
                <div className="text-xs font-bold text-red-400">{d.name}</div>
                {d.description && <div className="text-xs text-white/40 mt-1">{d.description}</div>}
              </div>
            ))}
          </div>
        </Card>
      )}

      {data.sequence && (
        <Card title="Amino Acid Sequence">
          <pre className="text-xs text-white/30 font-mono break-all whitespace-pre-wrap leading-relaxed max-h-32 overflow-y-auto">
            {data.sequence}
          </pre>
        </Card>
      )}
    </div>
  );
}

// ─── Shared components ────────────────────────────────────────────────────────

export function LoadingState({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center py-32">
      <div className="text-center space-y-3">
        <Loader className="w-6 h-6 text-[#00ffaa] animate-spin mx-auto" />
        <p className="text-xs text-white/40">{label}</p>
      </div>
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-3 p-4 rounded-lg border border-red-500/20 bg-red-500/5 text-red-400 text-sm">
      <AlertCircle className="w-4 h-4 shrink-0" />
      {message}
    </div>
  );
}

export function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="p-5 rounded-lg border border-[#0f2a1a] bg-[#0d1b12]/40"
    >
      <h3 className="text-xs text-[#00ffaa]/60 uppercase tracking-widest mb-4">{title}</h3>
      {children}
    </motion.div>
  );
}

export function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-4 rounded-lg border border-[#0f2a1a] bg-[#0d1b12]/40">
      <div className="text-xs text-white/30 mb-1">{label}</div>
      <div className="text-xl font-bold text-white">{value}</div>
    </div>
  );
}

export function Breadcrumb({ items }: { items: { label: string; href?: string }[] }) {
  return (
    <div className="flex items-center gap-1 text-xs text-white/30">
      {items.map((item, i) => (
        <span key={i} className="flex items-center gap-1">
          {i > 0 && <ChevronRight className="w-3 h-3" />}
          {item.href ? (
            <Link to={item.href} className="hover:text-white/60 transition-colors">{item.label}</Link>
          ) : (
            <span className="text-white/60">{item.label}</span>
          )}
        </span>
      ))}
    </div>
  );
}

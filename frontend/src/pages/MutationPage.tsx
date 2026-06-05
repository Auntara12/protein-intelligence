import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getMutationAnalysis, getStructure, downloadPDF } from "../lib/api";
import { LoadingState, ErrorState, Card, Breadcrumb } from "./ProteinPage";
import { AlertTriangle, CheckCircle, Info, Download } from "lucide-react";
import ProteinViewer from "../components/structure/ProteinViewer";

export default function MutationPage() {
  const { gene, mutation } = useParams<{ gene: string; mutation: string }>();

  const { data: mutData, isLoading: mutLoading, error: mutError } = useQuery({
    queryKey: ["mutation", gene, mutation],
    queryFn: () => getMutationAnalysis(gene!, mutation!),
    enabled: !!gene && !!mutation,
  });

  const [pdfLoading, setPdfLoading] = useState(false);
  const handleDownloadPDF = async () => {
    setPdfLoading(true);
    try { await downloadPDF(gene!, mutation!); } finally { setPdfLoading(false); }
  };

  const { data: structData } = useQuery({
    queryKey: ["structure", gene, mutData?.parse?.position],
    queryFn: () => getStructure(gene!, mutData?.parse?.position),
    enabled: !!gene && !!mutData?.parse?.position,
  });

  if (mutLoading) return <LoadingState label={`Analyzing ${gene} ${mutation}...`} />;
  if (mutError) return <ErrorState message={(mutError as Error).message} />;
  if (!mutData) return null;

  const { parse, is_known_pathogenic, clinvar_data } = mutData;

  return (
    <div className="space-y-6">
      <Breadcrumb items={[
        { label: "Search", href: "/" },
        { label: gene!, href: `/protein/${gene}` },
        { label: mutation! },
      ]} />

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold">
            <span className="text-[#00ffaa]">{gene}</span>
            <span className="text-white/40 mx-2">·</span>
            <span className="text-white">{mutation}</span>
          </h1>
          <p className="text-white/40 text-sm mt-1">
            {parse.original_aa_full} → {parse.mutated_aa_full} at position {parse.position}
          </p>
        </div>
        <PathogenicBadge isPathogenic={is_known_pathogenic} />
      </div>

      {/* Predicted effect */}
      {mutData.predicted_effect && (
        <div className="p-4 rounded-lg border border-[#00ffaa]/15 bg-[#00ffaa]/5">
          <div className="flex gap-3">
            <Info className="w-4 h-4 text-[#00ffaa] shrink-0 mt-0.5" />
            <p className="text-sm text-white/70 leading-relaxed">{mutData.predicted_effect}</p>
          </div>
        </div>
      )}

      {/* Property grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <PropertyCard label="Charge" value={mutData.charge_change} />
        <PropertyCard label="Polarity" value={mutData.polarity_change} />
        <PropertyCard label="Size" value={mutData.size_change} />
        <PropertyCard label="Hydrophobicity" value={mutData.hydrophobicity_change} />
      </div>

      {/* Domain */}
      {mutData.domain && (
        <Card title="Domain Context">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-[#00ffaa]" />
            <span className="text-sm text-white/70">
              Residue {parse.position} lies within the <strong className="text-[#00ffaa]">{mutData.domain}</strong>
            </span>
          </div>
        </Card>
      )}

      {/* 3D Viewer */}
      {structData && (
        <Card title="3D Structure Viewer">
          <ProteinViewer
            structureUrl={structData.alphafold_pdb_url || structData.pdb_url || ""}
            mutationPosition={parse.position}
            confidenceScore={structData.confidence_score}
            method={structData.method}
          />
        </Card>
      )}

      {/* ClinVar */}
      {clinvar_data && clinvar_data.length > 0 && (
        <Card title={`ClinVar Variants (${clinvar_data.length})`}>
          <div className="space-y-2">
            {clinvar_data.map((cv, i) => (
              <div key={i} className="p-3 rounded border border-white/5 bg-white/2">
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-xs font-bold ${
                    cv.clinical_significance?.toLowerCase().includes("pathogenic")
                      ? "text-red-400"
                      : cv.clinical_significance?.toLowerCase().includes("benign")
                      ? "text-green-400"
                      : "text-yellow-400"
                  }`}>
                    {cv.clinical_significance}
                  </span>
                  {cv.variant_id && (
                    <a
                      href={`https://www.ncbi.nlm.nih.gov/clinvar/variation/${cv.variant_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-[#00ffaa]/50 hover:text-[#00ffaa] transition-colors"
                    >
                      VCV{cv.variant_id} ↗
                    </a>
                  )}
                </div>
                {cv.disease_name && (
                  <p className="text-xs text-white/50">{cv.disease_name}</p>
                )}
                {cv.review_status && (
                  <p className="text-xs text-white/25 mt-1">{cv.review_status}</p>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Navigation */}
      <div className="flex gap-3 pt-4 flex-wrap">
        <Link
          to={`/similar/${gene}`}
          className="text-xs px-4 py-2 border border-[#00ffaa]/20 hover:border-[#00ffaa]/50 bg-[#00ffaa]/5 hover:bg-[#00ffaa]/10 text-[#00ffaa] rounded transition-all"
        >
          Find Similar Proteins →
        </Link>
        <Link
          to={`/compare/${gene}/TP63`}
          className="text-xs px-4 py-2 border border-[#0f2a1a] hover:border-[#00ffaa]/30 text-white/40 hover:text-white/70 rounded transition-all"
        >
          Compare Proteins →
        </Link>
        <Link
          to={`/protein/${gene}`}
          className="text-xs px-4 py-2 border border-[#0f2a1a] hover:border-white/20 text-white/40 hover:text-white/60 rounded transition-all"
        >
          Full Protein Data →
        </Link>
        <button
          onClick={handleDownloadPDF}
          disabled={pdfLoading}
          className="flex items-center gap-1.5 text-xs px-4 py-2 border border-[#00ffaa]/20 hover:border-[#00ffaa]/40 bg-[#00ffaa]/5 text-[#00ffaa] rounded transition-all disabled:opacity-50 ml-auto"
        >
          <Download className="w-3.5 h-3.5" />
          {pdfLoading ? "Generating..." : "Download PDF Report"}
        </button>
      </div>
    </div>
  );
}

function PathogenicBadge({ isPathogenic }: { isPathogenic: boolean }) {
  return (
    <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold border ${
      isPathogenic
        ? "border-red-500/30 bg-red-500/10 text-red-400"
        : "border-green-500/20 bg-green-500/5 text-green-400"
    }`}>
      {isPathogenic ? (
        <><AlertTriangle className="w-3 h-3" /> Pathogenic</>
      ) : (
        <><CheckCircle className="w-3 h-3" /> No known pathogenicity</>
      )}
    </div>
  );
}

function PropertyCard({ label, value }: { label: string; value: string | null }) {
  const isChange = value && !value.toLowerCase().includes("no change");
  return (
    <div className={`p-3 rounded-lg border ${
      isChange ? "border-yellow-500/20 bg-yellow-500/5" : "border-[#0f2a1a] bg-[#0d1b12]/40"
    }`}>
      <div className="text-xs text-white/30 mb-1">{label}</div>
      <div className={`text-xs leading-relaxed ${isChange ? "text-yellow-300/80" : "text-white/50"}`}>
        {value || "N/A"}
      </div>
    </div>
  );
}

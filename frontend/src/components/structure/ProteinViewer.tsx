import { useEffect, useRef, useState } from "react";

interface ProteinViewerProps {
  structureUrl: string;
  mutationPosition?: number | null;
  confidenceScore?: number | null;
  method?: string | null;
}

export default function ProteinViewer({
  structureUrl,
  mutationPosition,
  confidenceScore,
  method,
}: ProteinViewerProps) {
  const viewerRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!structureUrl || !viewerRef.current) return;

    let viewer: any = null;

    const init = async () => {
      try {
        // Dynamically import 3Dmol (it uses window globals)
        const $3Dmol = await import("3dmol" as any);
        setLoading(true);
        setError(null);

        viewer = $3Dmol.createViewer(viewerRef.current, {
          backgroundColor: "0x0d1b12",
          antialias: true,
        });

        // Fetch structure file
        const response = await fetch(structureUrl);
        if (!response.ok) throw new Error("Failed to load structure file");
        const pdbData = await response.text();

        const format = structureUrl.endsWith(".cif") ? "mmcif" : "pdb";
        viewer.addModel(pdbData, format);

        // Default: color by pLDDT confidence (AlphaFold specific)
        viewer.setStyle({}, {
          cartoon: {
            colorfunc: (atom: any) => {
              // pLDDT coloring: bfactor = confidence
              const b = atom.b || 50;
              if (b >= 90) return "#0053d6";       // very high (blue)
              if (b >= 70) return "#65cbf3";        // confident (light blue)
              if (b >= 50) return "#ffdb13";        // low (yellow)
              return "#ff7d45";                     // very low (orange)
            },
          },
        });

        // Highlight mutation site
        if (mutationPosition) {
          viewer.addStyle(
            { resi: mutationPosition },
            {
              stick: { colorscheme: "redCarbon", radius: 0.35 },
              sphere: { color: "#ff4444", radius: 0.6, opacity: 0.8 },
            }
          );

          // Add label
          viewer.addLabel(`${mutationPosition}`, {
            position: { resi: mutationPosition },
            backgroundColor: "#ff4444",
            fontColor: "white",
            fontSize: 12,
            backgroundOpacity: 0.8,
            borderThickness: 0,
          });
        }

        viewer.zoomTo();
        viewer.render();
        viewer.zoom(1.2, 500);
        setLoading(false);
      } catch (e) {
        console.error("3Dmol error:", e);
        setError("Could not load 3D structure. Try viewing directly via AlphaFold DB.");
        setLoading(false);
      }
    };

    init();

    return () => {
      if (viewer) {
        try { viewer.clear(); } catch (_) {}
      }
    };
  }, [structureUrl, mutationPosition]);

  return (
    <div className="space-y-3">
      {/* Metadata bar */}
      <div className="flex items-center gap-4 text-xs text-white/30">
        {method && <span>Method: <span className="text-white/50">{method}</span></span>}
        {confidenceScore && (
          <span>
            Avg pLDDT:{" "}
            <span className={`font-bold ${
              confidenceScore >= 90 ? "text-blue-400" :
              confidenceScore >= 70 ? "text-[#00ffaa]" :
              confidenceScore >= 50 ? "text-yellow-400" : "text-orange-400"
            }`}>
              {confidenceScore.toFixed(1)}
            </span>
          </span>
        )}
        {mutationPosition && (
          <span>Highlighting: <span className="text-red-400">residue {mutationPosition}</span></span>
        )}
      </div>

      {/* Viewer container */}
      <div className="relative rounded-lg overflow-hidden border border-[#0f2a1a]" style={{ height: 400 }}>
        <div ref={viewerRef} className="w-full h-full" />

        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#0d1b12]">
            <div className="text-center space-y-2">
              <div className="w-6 h-6 border-2 border-[#00ffaa]/30 border-t-[#00ffaa] rounded-full animate-spin mx-auto" />
              <p className="text-xs text-white/30">Loading 3D structure...</p>
            </div>
          </div>
        )}

        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#0d1b12]">
            <div className="text-center space-y-2 p-6">
              <p className="text-xs text-red-400">{error}</p>
              {structureUrl && (
                <a
                  href={structureUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-[#00ffaa]/60 hover:text-[#00ffaa] underline"
                >
                  Download structure file ↗
                </a>
              )}
            </div>
          </div>
        )}
      </div>

      {/* pLDDT legend */}
      <div className="flex items-center gap-4 text-xs text-white/30">
        <span>pLDDT:</span>
        {[
          { color: "#0053d6", label: ">90 Very high" },
          { color: "#65cbf3", label: "70-90 Confident" },
          { color: "#ffdb13", label: "50-70 Low" },
          { color: "#ff7d45", label: "<50 Very low" },
        ].map((l) => (
          <span key={l.color} className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-sm inline-block" style={{ backgroundColor: l.color }} />
            {l.label}
          </span>
        ))}
      </div>
    </div>
  );
}

import { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { Dna, Upload, GitMerge } from "lucide-react";

const NAV_ITEMS = [
  { label: "Search", href: "/", icon: Dna },
  { label: "Compare", href: "/compare", icon: GitMerge },
  { label: "Batch", href: "/batch", icon: Upload },
];

export default function Layout({ children }: { children: ReactNode }) {
  const location = useLocation();

  return (
    <div className="min-h-screen bg-[#080b14] text-white font-mono">
      {/* Grid background */}
      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          backgroundImage: `
            linear-gradient(rgba(0,255,170,0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0,255,170,0.03) 1px, transparent 1px)
          `,
          backgroundSize: "40px 40px",
        }}
      />

      {/* Header */}
      <header className="relative z-10 border-b border-[#0f2a1a] bg-[#080b14]/90 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3 group">
            <div className="relative">
              <div className="w-8 h-8 rounded border border-[#00ffaa]/40 flex items-center justify-center group-hover:border-[#00ffaa] transition-colors">
                <Dna className="w-4 h-4 text-[#00ffaa]" />
              </div>
              <div className="absolute inset-0 rounded bg-[#00ffaa]/5 blur-sm" />
            </div>
            <div>
              <span className="text-[#00ffaa] font-bold tracking-wider text-sm">PROTEIN</span>
              <span className="text-white/60 text-sm"> INTELLIGENCE</span>
            </div>
          </Link>

          <nav className="flex items-center gap-1">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const active = location.pathname === item.href;
              return (
                <Link
                  key={item.href}
                  to={item.href}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded text-xs transition-all ${
                    active
                      ? "bg-[#00ffaa]/10 text-[#00ffaa] border border-[#00ffaa]/20"
                      : "text-white/40 hover:text-white/70 hover:bg-white/5"
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>

      {/* Main */}
      <main className="relative z-10 max-w-7xl mx-auto px-6 py-10">
        <motion.div
          key={location.pathname}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          {children}
        </motion.div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 border-t border-[#0f2a1a] mt-20 py-6">
        <div className="max-w-7xl mx-auto px-6 flex items-center justify-between text-xs text-white/20">
          <span>Protein Intelligence Platform v1.0.0</span>
          <span>ESM2 · FAISS · AlphaFold · UniProt · ClinVar</span>
        </div>
      </footer>
    </div>
  );
}

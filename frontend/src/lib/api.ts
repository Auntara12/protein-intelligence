import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const apiClient = axios.create({
  baseURL: `${API_URL}/api/v1`,
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

// ── Types ────────────────────────────────────────────────────────────────────

export interface ProteinData {
  gene_name: string;
  uniprot_id: string | null;
  protein_name: string | null;
  organism: string | null;
  sequence: string | null;
  sequence_length: number | null;
  function_summary: string | null;
  domains: Domain[];
  disease_annotations: DiseaseAnnotation[];
  go_terms: GoTerm[];
  subcellular_location: string | null;
  mass_da: number | null;
  cached: boolean;
}

export interface Domain {
  type: string;
  name: string;
  start: number | null;
  end: number | null;
}

export interface DiseaseAnnotation {
  name: string;
  description: string | null;
  mim_id: string | null;
}

export interface GoTerm {
  id: string;
  term: string;
  aspect: string;
}

export interface MutationParseResult {
  raw: string;
  gene: string;
  original_aa: string;
  original_aa_full: string;
  position: number;
  mutated_aa: string;
  mutated_aa_full: string;
  valid: boolean;
  error: string | null;
}

export interface MutationAnalysis {
  gene_name: string;
  mutation_str: string;
  parse: MutationParseResult;
  charge_change: string | null;
  polarity_change: string | null;
  size_change: string | null;
  hydrophobicity_change: string | null;
  domain: string | null;
  structural_location: string | null;
  predicted_effect: string | null;
  conservation_score: number | null;
  is_known_pathogenic: boolean;
  clinvar_data: ClinVarEntry[];
  cached: boolean;
}

export interface ClinVarEntry {
  variant_id: string | null;
  clinical_significance: string | null;
  disease_name: string | null;
  review_status: string | null;
  hgvs_expression: string | null;
  last_evaluated: string | null;
}

export interface StructureData {
  gene_name: string;
  uniprot_id: string | null;
  alphafold_url: string | null;
  alphafold_pdb_url: string | null;
  pdb_id: string | null;
  pdb_url: string | null;
  confidence_score: number | null;
  resolution_angstrom: number | null;
  method: string | null;
  viewer_config: ViewerConfig;
  cached: boolean;
}

export interface ViewerConfig {
  url: string;
  format: string;
  defaultStyle: object;
  backgroundColor: string;
  mutations: MutationHighlight[];
  domains: DomainHighlight[];
}

export interface MutationHighlight {
  resi: number;
  style: object;
  label: string;
}

export interface DomainHighlight {
  resi: string;
  color: string;
  label: string;
}

export interface SimilarProtein {
  gene_name: string;
  uniprot_id: string | null;
  protein_name: string | null;
  distance: number;
  similarity_score: number;
  organism: string | null;
}

export interface SimilarityResult {
  query_gene: string;
  results: SimilarProtein[];
  model_used: string;
  total_indexed: number;
}

export interface HealthStatus {
  status: string;
  database: string;
  redis: string;
  faiss_index: string;
  version: string;
}

// ── API Functions ─────────────────────────────────────────────────────────────

export const getProtein = async (gene: string): Promise<ProteinData> => {
  const { data } = await apiClient.get(`/protein/${gene.toUpperCase()}`);
  return data;
};

export const getMutationAnalysis = async (
  gene: string,
  mutation: string
): Promise<MutationAnalysis> => {
  const { data } = await apiClient.get(
    `/mutation/${gene.toUpperCase()}/${mutation.toUpperCase()}`
  );
  return data;
};

export const getStructure = async (
  gene: string,
  mutationPosition?: number
): Promise<StructureData> => {
  const params = mutationPosition ? { mutation_position: mutationPosition } : {};
  const { data } = await apiClient.get(`/structure/${gene.toUpperCase()}`, { params });
  return data;
};

export const getSimilarProteins = async (
  gene: string,
  topK: number = 5
): Promise<SimilarityResult> => {
  const { data } = await apiClient.get(`/similar/${gene.toUpperCase()}`, {
    params: { top_k: topK },
  });
  return data;
};

export const getHealth = async (): Promise<HealthStatus> => {
  const { data } = await apiClient.get("/health");
  return data;
};

export const uploadBatch = async (file: File) => {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post("/batch-analyze", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
};

// ── Comparison ────────────────────────────────────────────────────────────────

export interface DomainComparison {
  shared: string[];
  unique_to_gene1: string[];
  unique_to_gene2: string[];
}

export interface ComparisonResult {
  gene1: string;
  gene2: string;
  protein1: ProteinData;
  protein2: ProteinData;
  alignment: any | null;
  esm2_similarity: number | null;
  domain_comparison: DomainComparison;
  shared_diseases: string[];
  summary: string;
}

export const compareProteins = async (gene1: string, gene2: string): Promise<ComparisonResult> => {
  const { data } = await apiClient.get(`/compare/${gene1.toUpperCase()}/${gene2.toUpperCase()}`);
  return data;
};

export const downloadPDF = async (gene: string, mutation?: string): Promise<void> => {
  const params = mutation ? `?mutation_str=${mutation.toUpperCase()}` : "";
  const response = await apiClient.get(`/report/${gene.toUpperCase()}/pdf${params}`, {
    responseType: "blob",
  });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", `${gene}${mutation ? `_${mutation}` : ""}_report.pdf`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

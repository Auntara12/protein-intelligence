import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/ui/Layout";
import HomePage from "./pages/HomePage";
import ProteinPage from "./pages/ProteinPage";
import MutationPage from "./pages/MutationPage";
import SimilarityPage from "./pages/SimilarityPage";
import BatchPage from "./pages/BatchPage";
import ComparisonPage from "./pages/ComparisonPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 1,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/protein/:gene" element={<ProteinPage />} />
            <Route path="/mutation/:gene/:mutation" element={<MutationPage />} />
            <Route path="/similar/:gene" element={<SimilarityPage />} />
            <Route path="/batch" element={<BatchPage />} />
            <Route path="/compare" element={<ComparisonPage />} />
            <Route path="/compare/:gene1/:gene2" element={<ComparisonPage />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

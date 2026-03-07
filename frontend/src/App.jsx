import { useState } from "react";
import GridBg from "./components/layout/GridBg";
import Navbar from "./components/layout/Navbar";
import HomePage from "./pages/HomePage";
import ResultsPage from "./pages/ResultsPage";
import AnalyticsPage from "./components/analytics/AnalyticsPage";
import { useSearch } from "./hooks/useSearch";
import { useAutocomplete } from "./hooks/useAutocomplete";
import { triggerReindex } from "./services/api";
import "./styles/global.css";

export default function App() {
  const [view, setView] = useState("home");
  const [query, setQuery] = useState("");
  const [reindexing, setReindexing] = useState(false);
  const [reindexMsg, setReindexMsg] = useState("");

  const {
    results,
    loading,
    error,
    page,
    totalPages,
    total,
    displayedQ,
    search,
    handlePageChange,
  } = useSearch();

  const { suggestions, showSuggestions, fetchSuggestions, clearSuggestions } =
    useAutocomplete();

  const handleQueryChange = (e) => {
    setQuery(e.target.value);
    fetchSuggestions(e.target.value);
  };

  const handleSearch = () => {
    if (!query.trim()) return;
    clearSuggestions();
    search(query, 1);
    setView("results");
  };

  const handleSuggestionSelect = (s) => {
    setQuery(s);
    clearSuggestions();
    search(s, 1);
    setView("results");
  };

  const handleHome = () => {
    setView("home");
    setQuery("");
  };

  const handleReindex = async () => {
    setReindexing(true);
    setReindexMsg("");
    try {
      const data = await triggerReindex();
      setReindexMsg(data.message || "Reindexing started!");
    } catch {
      setReindexMsg("Failed to connect.");
    }
    setReindexing(false);
    setTimeout(() => setReindexMsg(""), 4000);
  };

  return (
    <>
      <GridBg />
      <div
        style={{
          position: "relative",
          zIndex: 1,
          minHeight: "100vh",
          paddingBottom: 60,
        }}
      >
        <Navbar
          onHome={handleHome}
          onAnalytics={() => setView("analytics")}
          onReindex={handleReindex}
          reindexing={reindexing}
          reindexMsg={reindexMsg}
        />

        {view === "home" && (
          <HomePage
            query={query}
            onQueryChange={handleQueryChange}
            onSearch={handleSearch}
            onTagClick={(tag) => {
              setQuery(tag);
              search(tag, 1);
              setView("results");
            }}
            suggestions={suggestions}
            showSuggestions={showSuggestions}
            onSuggestionSelect={handleSuggestionSelect}
          />
        )}

        {view === "results" && (
          <ResultsPage
            query={query}
            onQueryChange={handleQueryChange}
            onSearch={handleSearch}
            suggestions={suggestions}
            showSuggestions={showSuggestions}
            onSuggestionSelect={handleSuggestionSelect}
            results={results}
            loading={loading}
            error={error}
            page={page}
            totalPages={totalPages}
            total={total}
            displayedQ={displayedQ}
            onPageChange={(p) => handlePageChange(displayedQ, p)}
          />
        )}

        {view === "analytics" && (
          <AnalyticsPage
            onBack={() => setView(results.length ? "results" : "home")}
          />
        )}
      </div>
    </>
  );
}

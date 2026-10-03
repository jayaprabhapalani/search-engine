import { useState } from "react";
import GridBg from "./components/layout/GridBg";
import Navbar from "./components/layout/Navbar";
import HomePage from "./pages/HomePage";
import ResultsPage from "./pages/ResultsPage";
import AnalyticsPage from "./components/analytics/AnalyticsPage";
import { useSearch } from "./hooks/useSearch";
import { useAutocomplete } from "./hooks/useAutocomplete";
import { triggerReindex, getIndexStatus } from "./services/api";
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
    capped,
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
      await triggerReindex();
      setReindexMsg("Reindexing started…");

      // Capture current version, then poll until it changes
      let baseVersion = null;
      try {
        const status = await getIndexStatus();
        baseVersion = status.snapshot_version;
      } catch {}

      const poll = setInterval(async () => {
        try {
          const status = await getIndexStatus();
          if (baseVersion === null || status.snapshot_version !== baseVersion) {
            clearInterval(poll);
            setReindexMsg("Index updated ✓");
            setReindexing(false);
            setTimeout(() => setReindexMsg(""), 5000);
          }
        } catch {
          // Redis/API blip — keep polling
        }
      }, 3000);

      // Safety timeout: stop polling after 3 minutes
      setTimeout(() => {
        clearInterval(poll);
        setReindexing(false);
        setReindexMsg((m) => m === "Reindexing started…" ? "Reindex triggered — check back shortly." : m);
      }, 180_000);

      return; // don't hit the setReindexing(false) below
    } catch (err) {
      if (err?.status === 429) {
        const secs = err.detail?.match(/(\d+) seconds/)?.[1];
        const mins = secs ? Math.ceil(secs / 60) : null;
        setReindexMsg(mins
          ? `Recently refreshed. Try again in ${mins} minute${mins > 1 ? "s" : ""}.`
          : err.detail || "Recently refreshed. Try again later."
        );
      } else {
        setReindexMsg("Failed to connect.");
      }
      setReindexing(false);
      setTimeout(() => setReindexMsg(""), 6000);
    }
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
            capped={capped}
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

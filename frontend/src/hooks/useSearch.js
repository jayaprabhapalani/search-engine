import { useState, useCallback } from "react";
import { searchStories } from "../services/api";

export const useSearch = () => {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [displayedQ, setDisplayedQ] = useState("");

  const search = useCallback(async (query, p = 1) => {
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    try {
      const data = await searchStories(query, p);
      const results = Array.isArray(data.results)
        ? data.results
        : data.results?.results || [];
      setResults(results);
      setPage(data.page || data.results?.page || 1);
      setTotalPages(data.total_pages || data.results?.total_pages || 1);
      setTotal(data.total || data.results?.total || 0);
      setDisplayedQ(query);
    } catch {
      setError("Could not connect to backend. Is your server running?");
    }
    setLoading(false);
  }, []);

  const handlePageChange = useCallback(
    (q, p) => {
      setPage(p);
      search(q, p);
    },
    [search],
  );

  return {
    results,
    loading,
    error,
    page,
    totalPages,
    total,
    displayedQ,
    search,
    handlePageChange,
  };
};

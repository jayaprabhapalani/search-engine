import { useState, useCallback, useRef } from "react";
import { searchStories } from "../services/api";

export const useSearch = () => {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [capped, setCapped] = useState(false);
  const [displayedQ, setDisplayedQ] = useState("");
  const reqCounter = useRef(0);

  const search = useCallback(async (query, p = 1) => {
    if (!query.trim()) return;
    const reqId = ++reqCounter.current;
    setLoading(true);
    setError("");
    try {
      const data = await searchStories(query, p);
      if (reqId !== reqCounter.current) return; // stale response — discard
      setResults(Array.isArray(data.results) ? data.results : []);
      setPage(data.page ?? 1);
      setTotalPages(data.total_pages ?? 0);
      setTotal(data.total ?? 0);
      setCapped(data.capped ?? false);
      setDisplayedQ(query);
    } catch {
      if (reqId !== reqCounter.current) return;
      setError("Could not connect to backend. Is your server running?");
    }
    setLoading(false);
  }, []);

  const handlePageChange = useCallback(
    (q, p) => {
      setPage(p);
      window.scrollTo({ top: 0, behavior: "smooth" });
      search(q, p);
    },
    [search],
  );

  return {
    results, loading, error, page, totalPages, total, capped, displayedQ,
    search, handlePageChange,
  };
};

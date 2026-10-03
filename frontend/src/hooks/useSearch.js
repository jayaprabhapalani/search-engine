import { useState, useCallback, useRef } from "react";
import { searchStories } from "../services/api";

const errorMessage = (err) => {
  if (err?.status === 429) return "Too many requests, slow down!";
  if (err?.status === 503) return "Index not ready, try again shortly.";
  return "Search failed. Please try again.";
};

export const useSearch = () => {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
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
      if (reqId !== reqCounter.current) return;
      setResults(data.results);
      setPage(data.page);
      setTotalPages(data.total_pages);
      setTotal(data.total);
      setCapped(data.capped);
      setDisplayedQ(query);
    } catch (err) {
      if (reqId !== reqCounter.current) return;
      setError(errorMessage(err));
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

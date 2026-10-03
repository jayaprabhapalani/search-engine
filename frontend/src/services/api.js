const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const searchStories = async (query, page = 1, pageSize = 5) => {
  const res = await fetch(
    `${BASE_URL}/search?q=${encodeURIComponent(query)}&page=${page}&page_size=${pageSize}`,
  );
  if (!res.ok) {
    const err = new Error("Search failed");
    err.status = res.status;
    throw err;
  }
  return res.json();
};

export const getAutocomplete = async (query) => {
  const res = await fetch(
    `${BASE_URL}/autocomplete?q=${encodeURIComponent(query)}`,
  );
  if (!res.ok) throw new Error("Autocomplete failed");
  return res.json();
};

export const getTopSearches = async () => {
  const res = await fetch(`${BASE_URL}/analytics/top-searches`);
  if (!res.ok) throw new Error("Failed");
  return res.json();
};

export const getZeroResults = async () => {
  const res = await fetch(`${BASE_URL}/analytics/zero-searches`);
  if (!res.ok) throw new Error("Failed");
  return res.json();
};

export const getIndexStatus = async () => {
  const res = await fetch(`${BASE_URL}/index/status`);
  if (!res.ok) throw new Error("Status check failed");
  return res.json();
};

export const triggerReindex = async () => {
  const res = await fetch(`${BASE_URL}/reindex`, { method: "POST" });
  if (!res.ok) {
    const err = new Error("Reindex failed");
    err.status = res.status;
    try { err.detail = (await res.json()).detail; } catch {}
    throw err;
  }
  return res.json();
};

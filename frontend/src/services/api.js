const BASE_URL = "http://localhost:8000";

export const searchStories = async (query, page = 1, pageSize = 5) => {
  const res = await fetch(
    `${BASE_URL}/search?q=${encodeURIComponent(query)}&page=${page}&page_size=${pageSize}`,
  );
  if (!res.ok) throw new Error("Search failed");
  const data = await res.json(); // call once, store in variable
  console.log(data); // log the variable
  return data; // return the variable
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

export const triggerReindex = async () => {
  const res = await fetch(`${BASE_URL}/reindex`, { method: "POST" });
  if (!res.ok) throw new Error("Failed");
  return res.json();
};

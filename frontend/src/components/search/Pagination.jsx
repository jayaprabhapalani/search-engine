const Pagination = ({ page, totalPages, onPage }) => {
  if (totalPages <= 1) return null;

  const BtnStyle = (active, disabled) => ({
    width: 36,
    height: 36,
    border: "2px solid #1a1a2e",
    background: active ? "#e63946" : disabled ? "#e8e3d8" : "#fff8f0",
    color: active ? "#fff8f0" : "#1a1a2e",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontFamily: "'Press Start 2P'",
    fontSize: "8px",
    cursor: disabled ? "not-allowed" : "pointer",
    boxShadow: "2px 2px 0 #1a1a2e",
    transition: "all 0.1s",
  });

  // Build the page number sequence with ellipsis markers
  const buildPages = () => {
    const pages = [];
    const addPage = (n) => { if (!pages.includes(n)) pages.push(n); };

    addPage(1);
    for (let i = Math.max(2, page - 2); i <= Math.min(totalPages - 1, page + 2); i++) {
      addPage(i);
    }
    addPage(totalPages);

    // Insert "..." where there are gaps
    const result = [];
    for (let i = 0; i < pages.length; i++) {
      if (i > 0 && pages[i] - pages[i - 1] > 1) result.push("...");
      result.push(pages[i]);
    }
    return result;
  };

  return (
    <div style={{ display: "flex", gap: 8, marginTop: 28, justifyContent: "center", flexWrap: "wrap" }}>
      <div onClick={() => page > 1 && onPage(page - 1)} style={BtnStyle(false, page === 1)}>
        ‹
      </div>

      {buildPages().map((p, i) =>
        p === "..." ? (
          <div key={`ellipsis-${i}`} style={BtnStyle(false, true)}>...</div>
        ) : (
          <div
            key={p}
            onClick={() => p !== page && onPage(p)}
            style={BtnStyle(p === page, false)}
          >
            {p}
          </div>
        )
      )}

      <div onClick={() => page < totalPages && onPage(page + 1)} style={BtnStyle(false, page === totalPages)}>
        ›
      </div>
    </div>
  );
};

export default Pagination;

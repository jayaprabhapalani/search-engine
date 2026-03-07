const Pagination = ({ page, totalPages, onPage }) => {
  if (totalPages <= 1) return null;

  const pages = [];
  for (let i = 1; i <= Math.min(totalPages, 5); i++) pages.push(i);

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

  return (
    <div
      style={{
        display: "flex",
        gap: 8,
        marginTop: 28,
        justifyContent: "center",
        flexWrap: "wrap",
      }}
    >
      <div
        onClick={() => page > 1 && onPage(page - 1)}
        style={BtnStyle(false, page === 1)}
      >
        ‹
      </div>

      {pages.map((p) => (
        <div
          key={p}
          onClick={() => onPage(p)}
          style={BtnStyle(p === page, false)}
        >
          {p}
        </div>
      ))}

      {totalPages > 5 && <div style={BtnStyle(false, true)}>...</div>}

      <div
        onClick={() => page < totalPages && onPage(page + 1)}
        style={BtnStyle(false, page === totalPages)}
      >
        ›
      </div>
    </div>
  );
};

export default Pagination;

const AutocompleteDropdown = ({ suggestions, onSelect }) => {
  if (!suggestions.length) return null;
  return (
    <div
      style={{
        position: "absolute",
        top: "100%",
        left: 0,
        right: 0,
        zIndex: 100,
        background: "#fff8f0",
        border: "3px solid #1a1a2e",
        borderTop: "none",
        boxShadow: "4px 4px 0 #1a1a2e",
        maxHeight: 220,
        overflowY: "auto",
      }}
    >
      {suggestions.map((s, i) => (
        <div
          key={i}
          onClick={() => onSelect(s)}
          style={{
            fontFamily: "'Press Start 2P'",
            fontSize: "8px",
            padding: "10px 14px",
            cursor: "pointer",
            borderBottom:
              i < suggestions.length - 1 ? "1px dashed #e8e3d8" : "none",
            color: "#1a1a2e",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "#ffd166")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "")}
        >
          <span style={{ color: "#e63946" }}>› </span>
          {s}
        </div>
      ))}
    </div>
  );
};

export default AutocompleteDropdown;

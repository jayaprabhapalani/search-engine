const PixelButton = ({
  onClick,
  color = "#e63946",
  children,
  small,
  loading,
  style = {},
}) => (
  <button
    onClick={onClick}
    disabled={loading}
    style={{
      fontFamily: "'Press Start 2P'",
      fontSize: small ? "8px" : "10px",
      background: loading ? "#888" : color,
      color: "#fff8f0",
      border: "3px solid #1a1a2e",
      padding: small ? "8px 14px" : "14px 22px",
      cursor: loading ? "not-allowed" : "pointer",
      boxShadow: "4px 4px 0 #1a1a2e",
      whiteSpace: "nowrap",
      transition: "transform 0.1s, box-shadow 0.1s",
      ...style,
    }}
    onMouseDown={(e) => {
      if (!loading) {
        e.currentTarget.style.transform = "translate(2px,2px)";
        e.currentTarget.style.boxShadow = "2px 2px 0 #1a1a2e";
      }
    }}
    onMouseUp={(e) => {
      e.currentTarget.style.transform = "";
      e.currentTarget.style.boxShadow = "4px 4px 0 #1a1a2e";
    }}
  >
    {loading ? "..." : children}
  </button>
);

export default PixelButton;

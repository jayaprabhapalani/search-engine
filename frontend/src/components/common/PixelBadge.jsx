const PixelBadge = ({ color = "#ffd166", children, onClick, active }) => (
  <span
    onClick={onClick}
    style={{
      background: active ? "#1a1a2e" : color,
      color: active ? "#fff8f0" : "#1a1a2e",
      fontFamily: "'Press Start 2P'",
      fontSize: "7px",
      padding: "5px 10px",
      border: "2px solid #1a1a2e",
      boxShadow: "2px 2px 0 #1a1a2e",
      display: "inline-block",
      cursor: onClick ? "pointer" : "default",
    }}
  >
    {children}
  </span>
);

export default PixelBadge;

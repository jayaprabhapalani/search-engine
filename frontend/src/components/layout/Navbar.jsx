import PixelButton from "../common/PixelButton";

const Navbar = ({ onHome, onAnalytics, onReindex, reindexing, reindexMsg }) => (
  <div
    style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "14px 28px",
      borderBottom: "3px solid #1a1a2e",
      background: "#fff8f0",
      boxShadow: "0 3px 0 #1a1a2e",
      position: "relative",
      zIndex: 10,
    }}
  >
    {/* Logo */}
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        cursor: "pointer",
      }}
      onClick={onHome}
    >
      {["H", "N"].map((l, i) => (
        <div
          key={i}
          style={{
            width: 32,
            height: 32,
            background: ["#e63946", "#ffd166"][i],
            border: "2px solid #1a1a2e",
            boxShadow: "2px 2px 0 #1a1a2e",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: "'Press Start 2P'",
            fontSize: "13px",
            color: "#1a1a2e",
          }}
        >
          {l}
        </div>
      ))}
      <span
        style={{
          fontFamily: "'Press Start 2P'",
          fontSize: "10px",
          color: "#1a1a2e",
          marginLeft: 6,
        }}
      >
        SEARCH
      </span>
    </div>

    {/* Right side */}
    <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
      {reindexMsg && (
        <span style={{ fontFamily: "'VT323'", fontSize: 16, color: "#2ec4b6" }}>
          {reindexMsg}
        </span>
      )}
      <PixelButton onClick={onAnalytics} small color="#457b9d">
        📊 ANALYTICS
      </PixelButton>
      <PixelButton
        onClick={onReindex}
        small
        color="#2ec4b6"
        loading={reindexing}
      >
        ⟳ REINDEX
      </PixelButton>
    </div>
  </div>
);

export default Navbar;

import PixelBadge from "../common/PixelBadge";

const TAG_COLORS = [
  "#2ec4b6",
  "#ffd166",
  "#e63946",
  "#a8dadc",
  "#457b9d",
  "#f4a261",
];

const TopSearches = ({ data }) => (
  <div
    style={{
      background: "#fff8f0",
      border: "3px solid #1a1a2e",
      boxShadow: "5px 5px 0 #1a1a2e",
      padding: 20,
    }}
  >
    <div
      style={{
        fontFamily: "'Press Start 2P'",
        fontSize: "9px",
        marginBottom: 16,
        color: "#e63946",
      }}
    >
      🔥 TOP SEARCHES
    </div>

    {data.length === 0 ? (
      <div style={{ fontFamily: "'VT323'", fontSize: 16, color: "#888" }}>
        No data yet
      </div>
    ) : (
      data.map((item, i) => (
        <div
          key={i}
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "8px 0",
            borderBottom: "1px dashed #e8e3d8",
          }}
        >
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span
              style={{
                fontFamily: "'Press Start 2P'",
                fontSize: "7px",
                color: "#888",
              }}
            >
              #{i + 1}
            </span>
            <span
              style={{
                fontFamily: "'VT323'",
                fontSize: "18px",
                color: "#1a1a2e",
              }}
            >
              {item.query}
            </span>
          </div>
          <PixelBadge color={TAG_COLORS[i % TAG_COLORS.length]}>
            {item.count}x
          </PixelBadge>
        </div>
      ))
    )}
  </div>
);

export default TopSearches;

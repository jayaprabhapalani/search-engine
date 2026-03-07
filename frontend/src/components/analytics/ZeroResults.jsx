const ZeroResults = ({ data }) => (
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
        color: "#457b9d",
      }}
    >
      🚫 ZERO RESULTS
    </div>

    {data.length === 0 ? (
      <div style={{ fontFamily: "'VT323'", fontSize: 16, color: "#888" }}>
        None yet!
      </div>
    ) : (
      data.map((item, i) => (
        <div
          key={i}
          style={{
            padding: "8px 0",
            borderBottom: "1px dashed #e8e3d8",
          }}
        >
          <div
            style={{
              fontFamily: "'VT323'",
              fontSize: "18px",
              color: "#e63946",
            }}
          >
            {item.query}
          </div>
          <div
            style={{
              fontFamily: "'VT323'",
              fontSize: "13px",
              color: "#aaa",
            }}
          >
            {new Date(item.timestamp).toLocaleDateString()}
          </div>
        </div>
      ))
    )}
  </div>
);

export default ZeroResults;

const GridBg = () => (
  <div
    style={{
      position: "fixed",
      inset: 0,
      zIndex: 0,
      backgroundImage:
        "linear-gradient(#e8e3d8 1px, transparent 1px), linear-gradient(90deg, #e8e3d8 1px, transparent 1px)",
      backgroundSize: "24px 24px",
      pointerEvents: "none",
    }}
  />
);

export default GridBg;

const Spinner = () => (
  <div
    style={{
      width: 24,
      height: 24,
      border: "3px solid #e8e3d8",
      borderTop: "3px solid #1a1a2e",
      borderRadius: "50%",
      animation: "spin 0.8s linear infinite",
      display: "inline-block",
    }}
  />
);

export default Spinner;

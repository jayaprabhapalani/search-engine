const CharSprite = ({ style }) => (
  <div style={style}>
    <svg
      width="40"
      height="40"
      viewBox="0 0 10 10"
      style={{ imageRendering: "pixelated" }}
    >
      <rect x="2" y="0" width="6" height="1" fill="#ffd166" />
      <rect x="1" y="1" width="8" height="1" fill="#ffd166" />
      <rect x="1" y="2" width="8" height="4" fill="#ffd166" />
      <rect x="0" y="3" width="1" height="2" fill="#ffd166" />
      <rect x="9" y="3" width="1" height="2" fill="#ffd166" />
      <rect x="2" y="3" width="1" height="1" fill="#1a1a2e" />
      <rect x="6" y="3" width="1" height="1" fill="#1a1a2e" />
      <rect x="3" y="5" width="3" height="1" fill="#e63946" />
      <rect x="1" y="6" width="8" height="1" fill="#ffd166" />
      <rect x="2" y="7" width="6" height="1" fill="#ffd166" />
      <rect x="3" y="8" width="1" height="2" fill="#457b9d" />
      <rect x="5" y="8" width="1" height="2" fill="#457b9d" />
    </svg>
  </div>
);

export default CharSprite;

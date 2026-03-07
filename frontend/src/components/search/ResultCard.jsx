import PixelBadge from "../common/PixelBadge";

const TAG_COLORS = [
  "#2ec4b6",
  "#ffd166",
  "#e63946",
  "#a8dadc",
  "#457b9d",
  "#f4a261",
];
const getTagColor = (i) => TAG_COLORS[i % TAG_COLORS.length];

const ResultCard = ({ story, index }) => {
  const score = story.score ? (story.score * 100).toFixed(1) : null;

  return (
    <div
      style={{
        background: "#fff8f0",
        border: "3px solid #1a1a2e",
        boxShadow: "5px 5px 0 #1a1a2e",
        padding: "16px 18px",
        marginBottom: "14px",
        cursor: "pointer",
        animation: "fadeSlide 0.3s ease both",
        animationDelay: `${index * 0.05}s`,
        transition: "transform 0.1s, box-shadow 0.1s",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = "translate(-2px,-2px)";
        e.currentTarget.style.boxShadow = "7px 7px 0 #1a1a2e";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = "";
        e.currentTarget.style.boxShadow = "5px 5px 0 #1a1a2e";
      }}
      onClick={() => story.url && window.open(story.url, "_blank")}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 8,
          flexWrap: "wrap",
        }}
      >
        <PixelBadge color={getTagColor(index)}>HN</PixelBadge>
        {score && <PixelBadge color="#ffd166">SCORE {score}%</PixelBadge>}
      </div>
      <div
        style={{
          fontFamily: "'Press Start 2P'",
          fontSize: "9px",
          color: "#457b9d",
          marginBottom: 6,
          lineHeight: 1.7,
        }}
      >
        {story.title}
      </div>
      {story.url && (
        <div
          style={{
            fontFamily: "'VT323'",
            fontSize: "15px",
            color: "#888",
            marginBottom: 6,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {story.url}
        </div>
      )}
      {story.text && story.text !== story.title && (
        <div
          style={{
            fontFamily: "'VT323'",
            fontSize: "16px",
            color: "#1a1a2e",
            lineHeight: 1.5,
            opacity: 0.8,
          }}
        >
          {story.text.slice(0, 160)}
          {story.text.length > 160 ? "..." : ""}
        </div>
      )}
    </div>
  );
};

export default ResultCard;

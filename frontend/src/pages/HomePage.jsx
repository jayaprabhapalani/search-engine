import SearchBar from "../components/search/SearchBar";
import CharSprite from "../components/common/CharSprite";

const TAGS = ["python", "fastapi", "machine learning", "rust", "docker", "llm"];

const HomePage = ({
  query,
  onQueryChange,
  onSearch,
  onTagClick,
  suggestions,
  showSuggestions,
  onSuggestionSelect,
}) => (
  <div
    style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      minHeight: "calc(100vh - 70px)",
      padding: "20px",
    }}
  >
    {/* Logo */}
    <div
      style={{
        display: "flex",
        gap: 10,
        marginBottom: 14,
        animation: "bounce 2s ease-in-out infinite",
      }}
    >
      {["H", "N", "S", "R", "C", "H"].map((l, i) => (
        <div
          key={i}
          style={{
            width: 48,
            height: 48,
            background: [
              "#e63946",
              "#ffd166",
              "#2ec4b6",
              "#457b9d",
              "#f4a261",
              "#a8dadc",
            ][i],
            border: "3px solid #1a1a2e",
            boxShadow: "4px 4px 0 #1a1a2e",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: "'Press Start 2P'",
            fontSize: "18px",
            color: "#fff8f0",
            textShadow: "2px 2px 0 #1a1a2e",
          }}
        >
          {l}
        </div>
      ))}
    </div>

    <div
      style={{
        fontFamily: "'VT323'",
        fontSize: "20px",
        color: "#888",
        marginBottom: 40,
        letterSpacing: 3,
      }}
    >
      HACKER NEWS SEARCH ENGINE
    </div>

    {/* Search */}
    <div style={{ width: "100%", maxWidth: 580 }}>
      <SearchBar
        query={query}
        onChange={onQueryChange}
        onSearch={onSearch}
        suggestions={suggestions}
        showSuggestions={showSuggestions}
        onSelect={onSuggestionSelect}
      />
    </div>

    {/* Quick tags */}
    <div
      style={{
        display: "flex",
        gap: 10,
        marginTop: 24,
        flexWrap: "wrap",
        justifyContent: "center",
      }}
    >
      {TAGS.map((tag) => (
        <span
          key={tag}
          onClick={() => onTagClick(tag)}
          style={{
            fontFamily: "'VT323'",
            fontSize: "17px",
            background: "#fff8f0",
            border: "2px solid #1a1a2e",
            boxShadow: "2px 2px 0 #1a1a2e",
            padding: "5px 14px",
            cursor: "pointer",
            transition: "all 0.1s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "#ffd166";
            e.currentTarget.style.transform = "translateY(-2px)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "#fff8f0";
            e.currentTarget.style.transform = "";
          }}
        >
          #{tag}
        </span>
      ))}
    </div>

    <CharSprite
      style={{ marginTop: 48, animation: "wiggle 2s ease-in-out infinite" }}
    />
    <div
      style={{
        fontFamily: "'VT323'",
        fontSize: 15,
        color: "#bbb",
        marginTop: 8,
      }}
    >
      POWERED BY HYBRID TF-IDF + VECTOR SEARCH
    </div>
  </div>
);

export default HomePage;

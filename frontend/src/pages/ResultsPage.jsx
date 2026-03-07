import SearchBar from "../components/search/SearchBar";
import ResultCard from "../components/search/ResultCard";
import Pagination from "../components/search/Pagination";
import PixelBadge from "../components/common/PixelBadge";
import Spinner from "../components/common/Spinner";
import CharSprite from "../components/common/CharSprite";

const ResultsPage = ({
  query,
  onQueryChange,
  onSearch,
  suggestions,
  showSuggestions,
  onSuggestionSelect,
  results,
  loading,
  error,
  page,
  totalPages,
  total,
  displayedQ,
  onPageChange,
}) => (
  <div style={{ maxWidth: 700, margin: "0 auto", padding: "32px 24px" }}>
    {/* Search bar */}
    <div style={{ marginBottom: 24 }}>
      <SearchBar
        query={query}
        onChange={onQueryChange}
        onSearch={onSearch}
        suggestions={suggestions}
        showSuggestions={showSuggestions}
        onSelect={onSuggestionSelect}
        small
      />
    </div>

    {/* Stats bar */}
    <div
      style={{
        fontFamily: "'VT323'",
        fontSize: "17px",
        color: "#888",
        marginBottom: 20,
        display: "flex",
        alignItems: "center",
        gap: 12,
        borderBottom: "2px dashed #ccc",
        paddingBottom: 12,
        flexWrap: "wrap",
      }}
    >
      <span
        style={{
          color: "#2ec4b6",
          fontFamily: "'Press Start 2P'",
          fontSize: "7px",
        }}
      >
        ✓
      </span>
      <span>
        <span style={{ color: "#1a1a2e" }}>{total}</span> results for "
        <span style={{ color: "#e63946" }}>{displayedQ}</span>"
      </span>
      <PixelBadge color="#ffd166">
        PAGE {page}/{totalPages}
      </PixelBadge>
      <PixelBadge color="#2ec4b6">HYBRID</PixelBadge>
    </div>

    {error && (
      <div
        style={{
          background: "#e63946",
          border: "3px solid #1a1a2e",
          padding: "10px 18px",
          marginBottom: 16,
          fontFamily: "'VT323'",
          fontSize: 16,
          color: "#fff8f0",
        }}
      >
        {error}
      </div>
    )}

    {loading ? (
      <div style={{ textAlign: "center", padding: 60 }}>
        <Spinner />
      </div>
    ) : results.length === 0 ? (
      <div style={{ textAlign: "center", padding: 40 }}>
        <CharSprite
          style={{
            margin: "0 auto 16px",
            animation: "wiggle 1s ease-in-out infinite",
          }}
        />
        <div
          style={{
            fontFamily: "'Press Start 2P'",
            fontSize: "9px",
            color: "#888",
          }}
        >
          NO RESULTS FOUND
        </div>
        <div
          style={{
            fontFamily: "'VT323'",
            fontSize: 16,
            color: "#bbb",
            marginTop: 8,
          }}
        >
          Try a different query
        </div>
      </div>
    ) : (
      <>
        {results.map((story, i) => (
          <ResultCard key={story.id} story={story} index={i} />
        ))}
        <Pagination page={page} totalPages={totalPages} onPage={onPageChange} />
      </>
    )}
  </div>
);

export default ResultsPage;

import { useState, useEffect } from "react";
import PixelButton from "../common/PixelButton";
import Spinner from "../common/Spinner";
import TopSearches from "./TopSearches";
import ZeroResults from "./ZeroResults";
import { getTopSearches, getZeroResults } from "../../services/api";

const AnalyticsPage = ({ onBack }) => {
  const [topSearches, setTopSearches] = useState([]);
  const [zeroResults, setZeroResults] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [top, zero] = await Promise.all([
          getTopSearches(),
          getZeroResults(),
        ]);
        setTopSearches(top);
        setZeroResults(zero);
      } catch {}
      setLoading(false);
    };
    load();
  }, []);

  return (
    <div style={{ maxWidth: 700, margin: "0 auto", padding: "32px 24px" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          marginBottom: 32,
        }}
      >
        <PixelButton onClick={onBack} small color="#457b9d">
          ← BACK
        </PixelButton>
        <span
          style={{
            fontFamily: "'Press Start 2P'",
            fontSize: "12px",
            color: "#1a1a2e",
          }}
        >
          ANALYTICS
        </span>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: 40 }}>
          <Spinner />
        </div>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 24,
          }}
        >
          <TopSearches data={topSearches} />
          <ZeroResults data={zeroResults} />
        </div>
      )}
    </div>
  );
};

export default AnalyticsPage;

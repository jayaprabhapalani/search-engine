import { useRef } from "react";
import PixelInput from "../common/PixelInput";
import PixelButton from "../common/PixelButton";
import AutocompleteDropdown from "./AutocompleteDropdown";

const SearchBar = ({
  query,
  onChange,
  onSearch,
  suggestions,
  showSuggestions,
  onSelect,
  small,
}) => {
  const wrapperRef = useRef(null);

  return (
    <div
      ref={wrapperRef}
      style={{ position: "relative", display: "flex", width: "100%" }}
    >
      <div style={{ flex: 1, position: "relative" }}>
        <PixelInput
          value={query}
          onChange={onChange}
          onKeyDown={(e) => e.key === "Enter" && onSearch()}
          placeholder={small ? "search..." : "search hacker news..."}
          style={{
            borderRight: "none",
            fontSize: small ? "9px" : "10px",
            padding: small ? "12px 14px" : "14px 18px",
          }}
        />
        {showSuggestions && (
          <AutocompleteDropdown suggestions={suggestions} onSelect={onSelect} />
        )}
      </div>
      <PixelButton onClick={onSearch} small={small}>
        {small ? "GO" : "SEARCH →"}
      </PixelButton>
    </div>
  );
};

export default SearchBar;

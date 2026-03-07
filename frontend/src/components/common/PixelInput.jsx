const PixelInput = ({
  value,
  onChange,
  onKeyDown,
  placeholder,
  style = {},
}) => (
  <input
    value={value}
    onChange={onChange}
    onKeyDown={onKeyDown}
    placeholder={placeholder}
    style={{
      fontFamily: "'Press Start 2P'",
      fontSize: "10px",
      padding: "14px 18px",
      border: "3px solid #1a1a2e",
      background: "#fff8f0",
      color: "#1a1a2e",
      outline: "none",
      width: "100%",
      ...style,
    }}
  />
);

export default PixelInput;

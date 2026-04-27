function clampMatchPercentage(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round(numeric)));
}

function getConfidenceBand(matchPercentage) {
  if (matchPercentage >= 75) {
    return { label: "High confidence", cssModifier: "high" };
  }

  if (matchPercentage >= 40) {
    return { label: "Medium confidence", cssModifier: "medium" };
  }

  return { label: "Low confidence", cssModifier: "low" };
}

export function ProductCompareCard({ comparison }) {
  const matchPercentage = clampMatchPercentage(comparison?.matchPercentage);
  const matchedAttributes = Array.isArray(comparison?.matchedAttributes)
    ? comparison.matchedAttributes.filter(Boolean).slice(0, 3)
    : [];
  const confidenceBand = getConfidenceBand(matchPercentage);

  return (
    <div className={`product-compare-card ${confidenceBand.cssModifier}`}>
      <div className="product-compare-score-row">
        <div className="product-compare-score">{matchPercentage}%</div>
        <div className="product-compare-band">{confidenceBand.label}</div>
      </div>
      {matchedAttributes.length > 0 ? (
        <ul className="product-compare-attributes">
          {matchedAttributes.map((attribute) => (
            <li key={attribute}>{attribute}</li>
          ))}
        </ul>
      ) : (
        <div className="product-compare-empty">No reliable attribute match</div>
      )}
    </div>
  );
}

export default ProductCompareCard;

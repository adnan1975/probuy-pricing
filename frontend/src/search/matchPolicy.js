import { SOURCE_MATCH_THRESHOLD_POLICY } from "./constants";

function toSafePercent(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round(numeric)));
}

export function evaluateOfferPolicy(source, comparison = null) {
  const policy = SOURCE_MATCH_THRESHOLD_POLICY[source];
  const matchPercentage = toSafePercent(comparison?.matchPercentage);

  if (!policy) {
    return {
      matchPercentage,
      isBelowThreshold: false,
      shouldExcludeFromSuggestedPriceByDefault: false,
      thresholdText: ""
    };
  }

  const isBelowThreshold = matchPercentage < policy.minAcceptableMatchPercentage;
  const thresholdText = isBelowThreshold
    ? `${policy.belowThresholdStatus} (${matchPercentage}% < ${policy.minAcceptableMatchPercentage}% threshold)`
    : `Within threshold (${matchPercentage}% ≥ ${policy.minAcceptableMatchPercentage}%)`;

  return {
    matchPercentage,
    isBelowThreshold,
    shouldExcludeFromSuggestedPriceByDefault: isBelowThreshold,
    thresholdText
  };
}


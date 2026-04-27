const MAX_MATCHED_ATTRIBUTES = 3;

const ATTRIBUTE_CONFIG = {
  sku: { label: 'SKU/Part Number', weight: 1.0 },
  model: { label: 'Model', weight: 0.95 },
  brand: { label: 'Brand', weight: 0.8 },
  title: { label: 'Title Tokens', weight: 0.7 },
};

function normalizeToTokens(value) {
  if (typeof value !== 'string') {
    return [];
  }

  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter(Boolean);
}

function normalizeJoined(value) {
  return normalizeToTokens(value).join('');
}

function firstDefinedString(...values) {
  const found = values.find((value) => typeof value === 'string' && value.trim().length > 0);
  return found ?? '';
}

function exactIdentifierScore(baseValue, connectorValue) {
  const baseNormalized = normalizeJoined(baseValue);
  const connectorNormalized = normalizeJoined(connectorValue);

  if (!baseNormalized || !connectorNormalized) {
    return null;
  }

  return baseNormalized === connectorNormalized ? 1 : 0;
}

function brandScore(baseValue, connectorValue) {
  const baseTokens = normalizeToTokens(baseValue);
  const connectorTokens = normalizeToTokens(connectorValue);

  if (!baseTokens.length || !connectorTokens.length) {
    return null;
  }

  return baseTokens[0] === connectorTokens[0] ? 1 : 0;
}

function tokenOverlapScore(baseValue, connectorValue, fallbackQuery) {
  const baseTokens = normalizeToTokens(baseValue);
  const connectorTokens = normalizeToTokens(connectorValue);
  const queryTokens = normalizeToTokens(fallbackQuery);

  const baseContext = baseTokens.length ? baseTokens : queryTokens;

  if (!baseContext.length || !connectorTokens.length) {
    return null;
  }

  const baseSet = new Set(baseContext);
  const connectorSet = new Set(connectorTokens);

  let overlap = 0;
  baseSet.forEach((token) => {
    if (connectorSet.has(token)) {
      overlap += 1;
    }
  });

  return overlap / Math.max(baseSet.size, connectorSet.size);
}

function toPercent(score) {
  return Math.round(score * 100);
}

export function compareProducts(baseProduct = {}, connectorProduct = {}, query = '') {
  const baseSku = firstDefinedString(baseProduct.sku, baseProduct.part_number, baseProduct.partNumber);
  const connectorSku = firstDefinedString(
    connectorProduct.sku,
    connectorProduct.part_number,
    connectorProduct.partNumber,
  );

  const baseModel = firstDefinedString(
    baseProduct.model,
    baseProduct.manufacturer_model,
    baseProduct.manufacturerModel,
  );
  const connectorModel = firstDefinedString(
    connectorProduct.model,
    connectorProduct.manufacturer_model,
    connectorProduct.manufacturerModel,
  );

  const baseBrand = firstDefinedString(baseProduct.brand, baseProduct.manufacturer);
  const connectorBrand = firstDefinedString(connectorProduct.brand, connectorProduct.manufacturer);

  const baseTitle = firstDefinedString(baseProduct.title, baseProduct.name);
  const connectorTitle = firstDefinedString(connectorProduct.title, connectorProduct.name);

  const rawAttributeScores = {
    sku: exactIdentifierScore(baseSku, connectorSku),
    model: exactIdentifierScore(baseModel, connectorModel),
    brand: brandScore(baseBrand, connectorBrand),
    title: tokenOverlapScore(baseTitle, connectorTitle, query),
  };

  const validAttributes = Object.entries(rawAttributeScores).filter(([, score]) => score !== null);

  if (!validAttributes.length) {
    return {
      matchPercentage: 0,
      matchedAttributes: [],
      attributeScores: {},
    };
  }

  const weightedTotal = validAttributes.reduce((sum, [attribute, score]) => {
    return sum + (score * ATTRIBUTE_CONFIG[attribute].weight);
  }, 0);

  const totalWeight = validAttributes.reduce((sum, [attribute]) => {
    return sum + ATTRIBUTE_CONFIG[attribute].weight;
  }, 0);

  const scoredAttributes = validAttributes
    .map(([attribute, score]) => ({
      attribute,
      label: ATTRIBUTE_CONFIG[attribute].label,
      score,
      weightedScore: score * ATTRIBUTE_CONFIG[attribute].weight,
    }))
    .sort((left, right) => right.weightedScore - left.weightedScore)
    .slice(0, MAX_MATCHED_ATTRIBUTES)
    .filter((item) => item.score > 0)
    .map((item) => item.label);

  return {
    matchPercentage: toPercent(weightedTotal / totalWeight),
    matchedAttributes: scoredAttributes,
    attributeScores: Object.fromEntries(
      validAttributes.map(([attribute, score]) => [attribute, toPercent(score)]),
    ),
  };
}

export default compareProducts;

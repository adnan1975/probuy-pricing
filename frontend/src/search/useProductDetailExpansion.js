import { useMemo, useState } from "react";
import { activeDetailConnectorConfigs } from "./constants";
import { evaluateOfferPolicy } from "./matchPolicy";
import { fetchDetailResults } from "./searchApi";

function chooseBestCandidate(candidates) {
  return candidates
    .filter((candidate) => candidate?.offer)
    .sort((left, right) => {
      if ((right.matchPercentage || 0) !== (left.matchPercentage || 0)) {
        return (right.matchPercentage || 0) - (left.matchPercentage || 0);
      }
      const leftPrice = typeof left.offer?.price_value === "number" ? left.offer.price_value : Number.POSITIVE_INFINITY;
      const rightPrice = typeof right.offer?.price_value === "number" ? right.offer.price_value : Number.POSITIVE_INFINITY;
      return leftPrice - rightPrice;
    })[0] || null;
}

export function useProductDetailExpansion({ apiUrl, visibleResults, trimmedQuery }) {
  const [detailsState, setDetailsState] = useState({});
  const [expandedRows, setExpandedRows] = useState({});

  const relatedOffersByRow = useMemo(
    () =>
      Object.entries(detailsState).reduce((acc, [rowIndex, rowState]) => {
        const offers = activeDetailConnectorConfigs
          .map((config) => rowState?.offersBySource?.[config.source])
          .filter(Boolean);
        acc[rowIndex] = offers;
        return acc;
      }, {}),
    [detailsState]
  );

  function resetDetailExpansion() {
    setExpandedRows({});
    setDetailsState({});
  }

  function updateConnectorStatus({ rowKey, source, nextState, step }) {
    setDetailsState((prev) => {
      const existing = prev[rowKey] || {};
      const existingStatus = existing.statusBySource?.[source] || { steps: [], state: "idle" };
      return {
        ...prev,
        [rowKey]: {
          ...existing,
          statusBySource: {
            ...(existing.statusBySource || {}),
            [source]: {
              state: nextState || existingStatus.state,
              steps: step ? [...existingStatus.steps, step] : existingStatus.steps
            }
          }
        }
      };
    });
  }

  function buildConnectorQueries(rowItem) {
    const rawCandidates = [
      rowItem?.sku,
      rowItem?.manufacturer_model,
      rowItem?.model,
      rowItem?.title,
      trimmedQuery
    ];
    return Array.from(new Set(rawCandidates.map((item) => String(item || "").trim()).filter(Boolean)));
  }

  async function loadDetailsForRow(rowIndex, { force = false, sources = null } = {}) {
    const rowItem = visibleResults[rowIndex];
    if (!rowItem) {
      return;
    }

    const rowKey = String(rowIndex);
    const detailQuery = String(rowItem.sku || rowItem.manufacturer_model || rowItem.title || trimmedQuery).trim();
    if (!detailQuery) {
      return;
    }

    const sourceSet = Array.isArray(sources) && sources.length > 0 ? new Set(sources) : null;
    const connectorsToLoad = sourceSet
      ? activeDetailConnectorConfigs.filter((connector) => sourceSet.has(connector.source))
      : activeDetailConnectorConfigs;

    if (connectorsToLoad.length === 0) {
      return;
    }

    if (!force && !sourceSet && detailsState[rowKey]?.loaded) {
      return;
    }

    const connectorQueries = buildConnectorQueries(rowItem);

    setDetailsState((prev) => {
      const existing = prev[rowKey] || {};
      return {
        ...prev,
        [rowKey]: {
          ...existing,
          loaded: false,
          loadingAll: true,
          offersBySource: existing.offersBySource || {},
          matchBySource: existing.matchBySource || {},
          errorsBySource: existing.errorsBySource || {},
          statusBySource: connectorsToLoad.reduce(
            (acc, config) => ({
              ...acc,
              [config.source]: {
                state: "loading",
                steps: [
                  "Initializing connector",
                  "Connected to source"
                ]
              }
            }),
            existing.statusBySource || {}
          ),
          loadingBySource: connectorsToLoad.reduce(
            (acc, config) => ({ ...acc, [config.source]: true }),
            existing.loadingBySource || {}
          )
        }
      };
    });

    for (const connector of connectorsToLoad) {
      updateConnectorStatus({
        rowKey,
        source: connector.source,
        nextState: "loading"
      });

      let resolvedOffer = null;
      let resolvedError = null;
      let resolvedMatch = null;
      const evaluatedCandidates = [];

      try {
        for (let idx = 0; idx < connectorQueries.length; idx += 1) {
          const candidate = connectorQueries[idx];
          const nextCandidate = connectorQueries[idx + 1];

          updateConnectorStatus({
            rowKey,
            source: connector.source,
            step: `Searching for SKU ${candidate}`
          });

          const { offer, comparison, comparedResults = [], error } = await fetchDetailResults({
            apiUrl,
            endpoint: connector.endpoint,
            query: candidate,
            comparisonTarget: rowItem,
            preselectBest: true,
            requestPayload: connector.endpoint === "kms_tools" ? {
              query: candidate,
              source_product_id: rowItem?.source_product_id,
              source_code: rowItem?.source_code,
              title: rowItem?.title,
              brand: rowItem?.brand,
              manufacturer: rowItem?.manufacturer,
              model_number: rowItem?.model_number || rowItem?.manufacturer_model || rowItem?.sku,
              category: rowItem?.category
            } : { query: candidate }
          });

          if (Array.isArray(comparedResults) && comparedResults.length > 0) {
            evaluatedCandidates.push(...comparedResults);
            const bestSoFar = chooseBestCandidate(evaluatedCandidates);
            if (bestSoFar) {
              updateConnectorStatus({
                rowKey,
                source: connector.source,
                step: `Evaluated ${evaluatedCandidates.length} products; best match ${bestSoFar.matchPercentage}%`
              });
            }
          }

          if (offer && comparison) {
            const policy = evaluateOfferPolicy(connector.source, comparison);
            resolvedOffer = offer;
            resolvedMatch = {
              matchPercentage: policy.matchPercentage,
              matchedAttributes: comparison.matchedAttributes || [],
              isBelowThreshold: policy.isBelowThreshold,
              shouldExcludeFromSuggestedPriceByDefault: policy.shouldExcludeFromSuggestedPriceByDefault,
              thresholdText: policy.thresholdText
            };
            resolvedError = null;
          }

          const bestEvaluated = chooseBestCandidate(evaluatedCandidates);
          if (bestEvaluated) {
            const policy = evaluateOfferPolicy(connector.source, bestEvaluated);
            resolvedOffer = bestEvaluated.offer;
            resolvedMatch = {
              matchPercentage: policy.matchPercentage,
              matchedAttributes: bestEvaluated.matchedAttributes || [],
              isBelowThreshold: policy.isBelowThreshold,
              shouldExcludeFromSuggestedPriceByDefault: policy.shouldExcludeFromSuggestedPriceByDefault,
              thresholdText: policy.thresholdText
            };
          }

          if (offer) {
            const isDeprioritized = Boolean(resolvedMatch?.isBelowThreshold);
            updateConnectorStatus({
              rowKey,
              source: connector.source,
              nextState: "success",
              step: `Success: evaluated ${evaluatedCandidates.length} products; best match ${resolvedMatch?.matchPercentage || 0}%${isDeprioritized ? " (deprioritized for suggested price)" : ""}`
            });
            break;
          }

          if (error) {
            resolvedError = error;
          }

          if (nextCandidate) {
            updateConnectorStatus({
              rowKey,
              source: connector.source,
              step: `Cannot find any price, moving to model ${nextCandidate}`
            });
            updateConnectorStatus({
              rowKey,
              source: connector.source,
              step: "Iterating through all attributes and retrying"
            });
          }
        }

        if (!resolvedOffer) {
          updateConnectorStatus({
            rowKey,
            source: connector.source,
            nextState: "failed",
            step: "Failure: price not found after checking all attributes"
          });
        }

        setDetailsState((prev) => {
          const existing = prev[rowKey] || {};
          return {
            ...prev,
            [rowKey]: {
              ...existing,
              offersBySource: {
                ...(existing.offersBySource || {}),
                [connector.source]: resolvedOffer
              },
              matchBySource: {
                ...(existing.matchBySource || {}),
                [connector.source]: resolvedMatch
              },
              errorsBySource: {
                ...(existing.errorsBySource || {}),
                [connector.source]: resolvedError
              },
              loadingBySource: {
                ...(existing.loadingBySource || {}),
                [connector.source]: false
              }
            }
          };
        });
      } catch (err) {
        updateConnectorStatus({
          rowKey,
          source: connector.source,
          nextState: "failed",
          step: `Failure: ${err.message || "Connector request failed"}`
        });
        setDetailsState((prev) => ({
          ...prev,
          [rowKey]: {
            ...(prev[rowKey] || {}),
            offersBySource: {
              ...((prev[rowKey] || {}).offersBySource || {}),
              [connector.source]: null
            },
            matchBySource: {
              ...((prev[rowKey] || {}).matchBySource || {}),
              [connector.source]: null
            },
            errorsBySource: {
              ...((prev[rowKey] || {}).errorsBySource || {}),
              [connector.source]: err.message || "Connector request failed"
            },
            loadingBySource: {
              ...((prev[rowKey] || {}).loadingBySource || {}),
              [connector.source]: false
            }
          }
        }));
      }
    }

    setDetailsState((prev) => {
      const rowState = prev[rowKey] || {};
      const hasLoadingSource = Object.values(rowState.loadingBySource || {}).some(Boolean);
      return {
        ...prev,
        [rowKey]: {
          ...rowState,
          loaded: !sourceSet,
          loadingAll: hasLoadingSource
        }
      };
    });
  }

  function toggleDetails(index) {
    setExpandedRows((prev) => {
      const nextExpanded = !prev[index];
      if (nextExpanded && !detailsState[String(index)]?.loaded && !detailsState[String(index)]?.loadingAll) {
        loadDetailsForRow(index);
      }
      return { ...prev, [index]: nextExpanded };
    });
  }

  function retryDetailsForConnector(index, source) {
    return loadDetailsForRow(index, { force: true, sources: [source] });
  }

  return {
    detailsState,
    setDetailsState,
    expandedRows,
    relatedOffersByRow,
    resetDetailExpansion,
    toggleDetails,
    retryDetailsForConnector
  };
}

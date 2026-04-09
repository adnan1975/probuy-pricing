import { useMemo, useState } from "react";
import { detailConnectorConfigs } from "./constants";
import { fetchDetailResults } from "./searchApi";

export function useProductDetailExpansion({ apiUrl, visibleResults, trimmedQuery }) {
  const [detailsState, setDetailsState] = useState({});
  const [expandedRows, setExpandedRows] = useState({});

  const relatedOffersByRow = useMemo(
    () =>
      Object.entries(detailsState).reduce((acc, [rowIndex, rowState]) => {
        const offers = detailConnectorConfigs
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

  async function loadDetailsForRow(rowIndex) {
    const rowItem = visibleResults[rowIndex];
    if (!rowItem) {
      return;
    }

    const rowKey = String(rowIndex);
    const detailQuery = String(rowItem.sku || rowItem.manufacturer_model || rowItem.title || trimmedQuery).trim();
    if (!detailQuery) {
      return;
    }

    setDetailsState((prev) => {
      const existing = prev[rowKey] || {};
      return {
        ...prev,
        [rowKey]: {
          ...existing,
          loaded: false,
          loadingAll: true,
          offersBySource: existing.offersBySource || {},
          errorsBySource: existing.errorsBySource || {},
          loadingBySource: detailConnectorConfigs.reduce(
            (acc, config) => ({ ...acc, [config.source]: true }),
            existing.loadingBySource || {}
          )
        }
      };
    });

    for (const connector of detailConnectorConfigs) {
      try {
        const { offer, error } = await fetchDetailResults({
          apiUrl,
          endpoint: connector.endpoint,
          query: detailQuery
        });

        setDetailsState((prev) => {
          const existing = prev[rowKey] || {};
          return {
            ...prev,
            [rowKey]: {
              ...existing,
              offersBySource: {
                ...(existing.offersBySource || {}),
                [connector.source]: offer
              },
              errorsBySource: {
                ...(existing.errorsBySource || {}),
                [connector.source]: error
              },
              loadingBySource: {
                ...(existing.loadingBySource || {}),
                [connector.source]: false
              }
            }
          };
        });
      } catch (err) {
        setDetailsState((prev) => ({
          ...prev,
          [rowKey]: {
            ...(prev[rowKey] || {}),
            offersBySource: {
              ...((prev[rowKey] || {}).offersBySource || {}),
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

    setDetailsState((prev) => ({
      ...prev,
      [rowKey]: {
        ...(prev[rowKey] || {}),
        loaded: true,
        loadingAll: false
      }
    }));
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

  return {
    detailsState,
    setDetailsState,
    expandedRows,
    relatedOffersByRow,
    resetDetailExpansion,
    toggleDetails
  };
}

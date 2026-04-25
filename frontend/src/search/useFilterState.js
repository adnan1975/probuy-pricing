import { useState } from "react";

const defaultRange = { min: "", max: "" };

const defaultFilters = {
  brand: "",
  manufacturer: "",
  category: "",
  source: "",
  stock_status: "",
  attributes: {},
  price: { ...defaultRange },
  length: { ...defaultRange },
  width: { ...defaultRange },
  height: { ...defaultRange },
  weight: { ...defaultRange }
};

export function useFilterState() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [draftFilters, setDraftFilters] = useState(defaultFilters);
  const [filters, setFilters] = useState(defaultFilters);

  function updatePageSize(value) {
    setPageSize(Number(value));
    setPage(1);
  }

  function updateFilter(field, value) {
    setDraftFilters((prev) => ({ ...prev, [field]: value }));
  }

  function updateRangeFilter(field, bound, value) {
    setDraftFilters((prev) => ({
      ...prev,
      [field]: {
        ...prev[field],
        [bound]: value
      }
    }));
  }

  function updateAttributeFilter(attribute, value) {
    setDraftFilters((prev) => ({
      ...prev,
      attributes: {
        ...prev.attributes,
        [attribute]: value
      }
    }));
  }

  function applyFilters() {
    setFilters(draftFilters);
    setPage(1);
  }

  function resetFilters({ includeQuery = false } = {}) {
    setPage(1);
    if (includeQuery) {
      setPageSize(25);
    }
    setDraftFilters(defaultFilters);
    setFilters(defaultFilters);
  }

  return {
    page,
    setPage,
    pageSize,
    setPageSize: updatePageSize,
    draftFilters,
    filters,
    updateFilter,
    updateRangeFilter,
    updateAttributeFilter,
    applyFilters,
    resetFilters
  };
}

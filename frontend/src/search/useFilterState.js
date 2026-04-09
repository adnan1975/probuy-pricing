import { useState } from "react";

const defaultPriceRange = { min: "", max: "" };

const defaultFilters = {
  model: "",
  manufacturerModel: "",
  listPrice: { ...defaultPriceRange },
  distributorCost: { ...defaultPriceRange },
  warehouseOnly: false,
  unit: "all"
};

export function useFilterState() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [filters, setFilters] = useState(defaultFilters);

  function updatePageSize(value) {
    setPageSize(Number(value));
    setPage(1);
  }

  function updateFilter(field, value) {
    setFilters((prev) => ({ ...prev, [field]: value }));
    setPage(1);
  }

  function updateRangeFilter(field, bound, value) {
    setFilters((prev) => ({
      ...prev,
      [field]: {
        ...prev[field],
        [bound]: value
      }
    }));
    setPage(1);
  }

  function resetFilters({ includeQuery = false } = {}) {
    setPage(1);
    if (includeQuery) {
      setPageSize(25);
    }
    setFilters(defaultFilters);
  }

  return {
    page,
    setPage,
    pageSize,
    setPageSize: updatePageSize,
    filters,
    updateFilter,
    updateRangeFilter,
    resetFilters
  };
}

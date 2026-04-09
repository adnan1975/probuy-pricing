import { useState } from "react";

const defaultPriceRange = { min: "", max: "" };

const defaultFilters = {
  model: "",
  manufacturerModel: "",
  listPrice: { ...defaultPriceRange },
  distributorCost: { ...defaultPriceRange },
  warehouses: [],
  unit: "all"
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

  function toggleWarehouse(warehouseCode) {
    setDraftFilters((prev) => {
      const hasWarehouse = prev.warehouses.includes(warehouseCode);
      const nextWarehouses = hasWarehouse
        ? prev.warehouses.filter((code) => code !== warehouseCode)
        : [...prev.warehouses, warehouseCode];
      return {
        ...prev,
        warehouses: nextWarehouses
      };
    });
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
    toggleWarehouse,
    applyFilters,
    resetFilters
  };
}

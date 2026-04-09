import { useState } from "react";

export function useFilterState() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  function updatePageSize(value) {
    setPageSize(Number(value));
    setPage(1);
  }

  function resetFilters() {
    setPage(1);
  }

  return {
    page,
    setPage,
    pageSize,
    setPageSize: updatePageSize,
    resetFilters
  };
}

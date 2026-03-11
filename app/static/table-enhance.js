(function () {
  const tables = document.querySelectorAll("table[data-enhanced-table]");
  if (!tables.length) {
    return;
  }

  const parseSortableValue = (text) => {
    const trimmed = text.trim();
    if (!trimmed) {
      return "";
    }
    if (/^\d{4}-\d{2}-\d{2}/.test(trimmed)) {
      const ts = Date.parse(trimmed);
      if (!Number.isNaN(ts)) {
        return ts;
      }
    }
    if (/^-?\d+([.,]\d+)?$/.test(trimmed)) {
      return Number(trimmed.replace(",", "."));
    }
    return trimmed.toLowerCase();
  };

  const createCellFilterInput = () => {
    const input = document.createElement("input");
    input.type = "text";
    input.className = "form-control form-control-sm";
    return input;
  };

  tables.forEach((table) => {
    const tbody = table.tBodies[0];
    const thead = table.tHead;
    if (!tbody || !thead || !thead.rows.length) {
      return;
    }

    const headerRow = thead.rows[0];
    const originalRows = Array.from(tbody.rows);
    const columnCount = headerRow.cells.length;
    const sortable = Array.from(headerRow.cells).map(
      (th) => th.dataset.sortable !== "false"
    );
    const filterable = Array.from(headerRow.cells).map(
      (th) => th.dataset.filterable !== "false"
    );
    const state = {
      globalFilter: "",
      columnFilters: new Array(columnCount).fill(""),
      sortIndex: null,
      sortDir: 1,
      page: 1,
      pageSize: 10,
    };

    const controls = document.createElement("div");
    controls.className = "table-enhance-controls d-flex flex-wrap gap-2 mb-2";
    const searchInput = document.createElement("input");
    searchInput.type = "text";
    searchInput.className = "form-control form-control-sm";
    searchInput.style.maxWidth = "240px";
    searchInput.placeholder = "Search";
    const pageSizeSelect = document.createElement("select");
    pageSizeSelect.className = "form-select form-select-sm";
    pageSizeSelect.style.maxWidth = "100px";
    [10, 25, 50].forEach((size) => {
      const option = document.createElement("option");
      option.value = String(size);
      option.textContent = String(size);
      pageSizeSelect.appendChild(option);
    });
    controls.appendChild(searchInput);
    controls.appendChild(pageSizeSelect);
    table.parentElement.insertBefore(controls, table);

    const filterRow = document.createElement("tr");
    filterRow.className = "table-filter-row";
    for (let i = 0; i < columnCount; i += 1) {
      const th = document.createElement("th");
      if (filterable[i]) {
        const input = createCellFilterInput();
        input.addEventListener("input", () => {
          state.columnFilters[i] = input.value.trim().toLowerCase();
          state.page = 1;
          render();
        });
        th.appendChild(input);
      }
      filterRow.appendChild(th);
    }
    thead.appendChild(filterRow);

    const pagination = document.createElement("div");
    pagination.className = "table-pagination d-flex align-items-center gap-2 mt-2";
    const prevButton = document.createElement("button");
    prevButton.type = "button";
    prevButton.className = "btn btn-sm btn-outline-secondary";
    prevButton.textContent = "Prev";
    const nextButton = document.createElement("button");
    nextButton.type = "button";
    nextButton.className = "btn btn-sm btn-outline-secondary";
    nextButton.textContent = "Next";
    const pageInfo = document.createElement("span");
    pageInfo.className = "small text-muted";
    pagination.appendChild(prevButton);
    pagination.appendChild(nextButton);
    pagination.appendChild(pageInfo);
    table.parentElement.appendChild(pagination);

    const applyFiltersAndSort = () => {
      const globalQuery = state.globalFilter.trim().toLowerCase();
      let filtered = originalRows.filter((row) => {
        const cells = Array.from(row.cells).map((cell) =>
          (cell.textContent || "").trim().toLowerCase()
        );
        if (globalQuery && !cells.some((value) => value.includes(globalQuery))) {
          return false;
        }
        for (let i = 0; i < state.columnFilters.length; i += 1) {
          if (!state.columnFilters[i]) {
            continue;
          }
          if (!cells[i].includes(state.columnFilters[i])) {
            return false;
          }
        }
        return true;
      });

      if (state.sortIndex !== null) {
        const idx = state.sortIndex;
        const direction = state.sortDir;
        filtered = filtered.slice().sort((leftRow, rightRow) => {
          const left = parseSortableValue(leftRow.cells[idx]?.textContent || "");
          const right = parseSortableValue(rightRow.cells[idx]?.textContent || "");
          if (left < right) {
            return -1 * direction;
          }
          if (left > right) {
            return 1 * direction;
          }
          return 0;
        });
      }
      return filtered;
    };

    const render = () => {
      const filtered = applyFiltersAndSort();
      const totalPages = Math.max(1, Math.ceil(filtered.length / state.pageSize));
      if (state.page > totalPages) {
        state.page = totalPages;
      }
      const start = (state.page - 1) * state.pageSize;
      const end = start + state.pageSize;
      const pageRows = filtered.slice(start, end);
      tbody.replaceChildren(...pageRows);

      prevButton.disabled = state.page <= 1;
      nextButton.disabled = state.page >= totalPages;
      pageInfo.textContent = `Page ${state.page} / ${totalPages}`;
    };

    Array.from(headerRow.cells).forEach((th, index) => {
      if (!sortable[index]) {
        return;
      }
      th.style.cursor = "pointer";
      th.addEventListener("click", () => {
        if (state.sortIndex === index) {
          state.sortDir = state.sortDir * -1;
        } else {
          state.sortIndex = index;
          state.sortDir = 1;
        }
        render();
      });
    });

    searchInput.addEventListener("input", () => {
      state.globalFilter = searchInput.value;
      state.page = 1;
      render();
    });
    pageSizeSelect.addEventListener("change", () => {
      state.pageSize = Number(pageSizeSelect.value);
      state.page = 1;
      render();
    });
    prevButton.addEventListener("click", () => {
      state.page = Math.max(1, state.page - 1);
      render();
    });
    nextButton.addEventListener("click", () => {
      state.page += 1;
      render();
    });

    render();
  });
})();


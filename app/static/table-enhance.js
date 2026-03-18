(function () {
  "use strict";

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

  tables.forEach((table) => {
    try {
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

      // Insert controls outside .table-responsive if present, otherwise before table
      const insertTarget = table.closest(".table-responsive") || table;
      const insertParent = insertTarget.parentElement;

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
      const printBtn = document.createElement("button");
      printBtn.type = "button";
      printBtn.className = "btn btn-outline-secondary btn-sm d-print-none ms-auto";
      printBtn.title = "Download PDF of filtered results";
      printBtn.innerHTML = '<i class="bi bi-file-earmark-pdf" aria-hidden="true"></i> PDF';
      controls.appendChild(printBtn);
      insertParent.insertBefore(controls, insertTarget);

      const filterRow = document.createElement("tr");
      filterRow.className = "table-filter-row";
      for (let i = 0; i < columnCount; i += 1) {
        const th = document.createElement("th");
        if (filterable[i]) {
          const input = document.createElement("input");
          input.type = "text";
          input.className = "form-control form-control-sm";
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
      insertParent.insertBefore(pagination, insertTarget.nextSibling);

      // Stamp original column label on each <th> before sort buttons replace the text
      Array.from(headerRow.cells).forEach((th) => {
        th.dataset.colLabel = th.textContent.trim();
      });

      // Stamp each sortable header with its column index for delegated click handling
      Array.from(headerRow.cells).forEach((th, index) => {
        if (!sortable[index]) return;
        th.dataset.sortCol = String(index);
        const label = th.textContent.trim();
        th.textContent = "";
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "sort-btn";
        btn.textContent = label;
        const icon = document.createElement("span");
        icon.className = "sort-icon";
        icon.setAttribute("aria-hidden", "true");
        icon.textContent = " \u21C5";
        btn.appendChild(icon);
        th.appendChild(btn);
      });

      // Single delegated listener on <thead> - catches clicks anywhere inside a sortable header
      thead.addEventListener("click", (e) => {
        const th = e.target.closest("th[data-sort-col]");
        if (!th) return;
        const index = parseInt(th.dataset.sortCol, 10);
        if (state.sortIndex === index) {
          state.sortDir = state.sortDir * -1;
        } else {
          state.sortIndex = index;
          state.sortDir = 1;
        }
        render();
      });

      const applyFiltersAndSort = () => {
        const globalQuery = state.globalFilter.trim().toLowerCase();
        let filtered = originalRows.filter((row) => {
          const cells = Array.from(row.cells).map((cell) =>
            (cell.textContent || "").trim().toLowerCase()
          );
          if (globalQuery && !cells.some((v) => v.includes(globalQuery))) {
            return false;
          }
          for (let i = 0; i < state.columnFilters.length; i += 1) {
            if (state.columnFilters[i] && !cells[i].includes(state.columnFilters[i])) {
              return false;
            }
          }
          return true;
        });

        if (state.sortIndex !== null) {
          const idx = state.sortIndex;
          const dir = state.sortDir;
          filtered = filtered.slice().sort((a, b) => {
            const left = parseSortableValue(a.cells[idx]?.textContent || "");
            const right = parseSortableValue(b.cells[idx]?.textContent || "");
            if (left < right) return -1 * dir;
            if (left > right) return 1 * dir;
            return 0;
          });
        }
        return filtered;
      };

      const updateSortIndicators = () => {
        Array.from(headerRow.cells).forEach((th, index) => {
          if (!sortable[index]) return;
          const icon = th.querySelector(".sort-icon");
          if (!icon) return;
          if (state.sortIndex === index) {
            icon.textContent = state.sortDir === 1 ? " \u2191" : " \u2193";
            th.classList.add("sort-active");
          } else {
            icon.textContent = " \u21C5";
            th.classList.remove("sort-active");
          }
        });
      };

      const render = () => {
        const filtered = applyFiltersAndSort();
        const totalPages = Math.max(1, Math.ceil(filtered.length / state.pageSize));
        if (state.page > totalPages) state.page = totalPages;
        const start = (state.page - 1) * state.pageSize;
        tbody.replaceChildren(...filtered.slice(start, start + state.pageSize));
        prevButton.disabled = state.page <= 1;
        nextButton.disabled = state.page >= totalPages;
        pageInfo.textContent = "Page " + state.page + " / " + totalPages;
        updateSortIndicators();
      };

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

      // Before any print (Ctrl+P, browser menu), expand tbody to ALL filtered rows
      // so headers repeat on every page and pagination is bypassed.
      window.addEventListener("beforeprint", () => {
        tbody.replaceChildren(...applyFiltersAndSort());
      });
      window.addEventListener("afterprint", () => {
        render();
      });

      // PDF button — generates a server-side A4 PDF with filter summary,
      // repeated column headers, alternating row shading, and page footer.
      printBtn.addEventListener("click", async () => {
        const allFiltered = applyFiltersAndSort();
        const columns = Array.from(headerRow.cells).map(
          (th) => th.dataset.colLabel || th.textContent.replace(/[\u21C5\u2191\u2193]/g, "").trim()
        );
        const rows = allFiltered.map((row) =>
          Array.from(row.cells).map((cell) => cell.textContent.trim())
        );
        const filters = {};
        if (state.globalFilter) filters["Search"] = state.globalFilter;
        state.columnFilters.forEach((v, i) => {
          if (v) {
            const label = headerRow.cells[i]?.dataset.colLabel || "Col" + (i + 1);
            filters[label] = v;
          }
        });
        const title =
          table.dataset.pdfTitle ||
          document.querySelector("main h1, main h2")?.textContent?.trim() ||
          document.title;

        printBtn.disabled = true;
        printBtn.innerHTML =
          '<i class="bi bi-hourglass-split" aria-hidden="true"></i> Generating\u2026';
        try {
          const resp = await fetch("/api/pdf/table", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title, columns, rows, filters }),
          });
          if (!resp.ok) throw new Error("HTTP " + resp.status);
          const blob = await resp.blob();
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download =
            (title || "export").replace(/[^a-z0-9]/gi, "_").slice(0, 60) + ".pdf";
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
        } catch (err) {
          // eslint-disable-next-line no-console
          console.error("[table-enhance] PDF error:", err);
          alert("PDF generation failed. Please try again.");
        } finally {
          printBtn.disabled = false;
          printBtn.innerHTML =
            '<i class="bi bi-file-earmark-pdf" aria-hidden="true"></i> PDF';
        }
      });

      render();
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[table-enhance] failed to enhance table:", err);
    }
  });
})();

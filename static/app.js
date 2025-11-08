let rowsForExport = [];

// helper: normalize loader names
function normalizeLoader(raw) {
  if (!raw) return raw;
  const s = String(raw).trim().toLowerCase();
  if (s.includes("neoforge") || s.includes("neo-forge")) return "NeoForge";
  if (s.includes("fabric")) return "Fabric";
  if (s.includes("quilt")) return "Quilt";
  if (s.includes("forge")) return "Forge";
  // fallback: capitalize first letter
  return raw.charAt(0).toUpperCase() + raw.slice(1);
}

// timestamp for filenames: YYYY-MM-DD-hh-mm
function exportTimestamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}-${pad(
    d.getHours()
  )}-${pad(d.getMinutes())}`;
}

// simple frontend URL validation - only allow curseforge or modrinth domains
const urlRegex = /^https?:\/\/(www\.)?(curseforge\.com|modrinth\.com)\/.+/i;

document.addEventListener("DOMContentLoaded", () => {
  // get elements (defensive)
  const themeToggle = document.getElementById("themeToggle");
  const analyzeBtn = document.getElementById("analyzeBtn");
  const urlInputEl = document.getElementById("urlInput");

  if (!analyzeBtn) {
    console.warn("analyzeBtn not found in DOM; check template or element id.");
    return;
  }
  if (!urlInputEl) {
    console.warn(
      "urlInput element not found. The analyze button will be disabled."
    );
    analyzeBtn.disabled = true;
    return;
  }

  // Theme toggle (guarded)
  if (themeToggle) {
    function applyTheme(theme) {
      document.body.setAttribute("data-theme", theme);
      localStorage.setItem("theme", theme);
      themeToggle.textContent = theme === "dark" ? "☀️" : "🌙";
    }
    themeToggle.addEventListener("click", () => {
      const newTheme =
        document.body.getAttribute("data-theme") === "dark" ? "light" : "dark";
      applyTheme(newTheme);
    });
    applyTheme(localStorage.getItem("theme") || "dark");
  } else {
    // not fatal, but helpful to know
    console.info("themeToggle not found — theme toggle disabled.");
  }

  // Analyze handler
  analyzeBtn.addEventListener("click", async () => {
    // defensive read
    const input = urlInputEl.value ? urlInputEl.value.trim() : "";
    if (!input) {
      alert("Please enter at least one URL.");
      return;
    }

    const rawUrls = input
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    const invalid = rawUrls.filter((u) => !urlRegex.test(u));
    if (invalid.length) {
      alert(
        "Some URLs look invalid or unsupported (only curseforge/modrinth are allowed):\n\n" +
          invalid.join("\n")
      );
      return;
    }
    const urls = rawUrls; // validated

    // get UI elements (guarded)
    const loading = document.getElementById("loading");
    const tableContainer = document.getElementById("tableContainer");
    const tbody = document.querySelector("#resultTable tbody");
    const exportButtons = document.getElementById("exportButtons");
    const filterSection = document.getElementById("filterSection");
    const topSummary = document.getElementById("compatibilitySummaryTop");
    const bottomSummary = document.getElementById("compatibilitySummaryBottom");

    if (!tbody) {
      console.error(
        "Result table body not found (#resultTable tbody). Aborting."
      );
      return;
    }

    // reset UI (safely)
    if (loading) loading.classList.remove("hidden");
    if (tableContainer) tableContainer.classList.add("hidden");
    if (exportButtons) exportButtons.classList.add("hidden");
    if (filterSection) filterSection.classList.add("hidden");
    if (topSummary) topSummary.classList.add("hidden");
    if (bottomSummary) bottomSummary.classList.add("hidden");
    tbody.innerHTML = "";
    rowsForExport = [];

    try {
      const res = await fetch("/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ urls }),
      });

      if (!res.ok) {
        const txt = await res.text();
        throw new Error(`Server error ${res.status}: ${txt}`);
      }

      const data = await res.json();

      if (loading) loading.classList.add("hidden");

      // Build rows & a helper data structure
      const modsData = []; // { name, url, pairs: [[version,loader], ...] }

      for (const mod of data) {
        if (mod.error) {
          tbody.insertAdjacentHTML(
            "beforeend",
            `<tr><td colspan="2" style="color:#f55">${mod.url || mod.name}: ${
              mod.error
            }</td></tr>`
          );
          continue;
        }

        // dedupe pairs and normalize loaders
        const rawPairs = (mod.versions || []).map(([ver, ldr]) => [
          ver,
          normalizeLoader(ldr),
        ]);
        const uniquePairs = Array.from(
          new Map(rawPairs.map((p) => [p.join("|"), p])).values()
        );

        // collect for export/filter
        const modUrl = mod.url || "";
        uniquePairs.forEach(([version, loader]) => {
          rowsForExport.push({ name: mod.name, url: modUrl, version, loader });
        });

        modsData.push({ name: mod.name, url: modUrl, pairs: uniquePairs });

        // build nested table html
        const versionRows = uniquePairs
          .map(
            ([version, loader]) =>
              `<tr><td>${version}</td><td>${loader}</td></tr>`
          )
          .join("");

        const rowHTML = `
          <tr data-pairs='${JSON.stringify(uniquePairs)}'>
            <td><a href="${modUrl}" target="_blank" rel="noopener">${
          mod.name
        }</a></td>
            <td class="details-cell">
              <button class="details-toggle">Show ${
                uniquePairs.length
              } versions</button>
              <div class="details-content">
                <table>
                  <thead><tr><th>Version</th><th>Loader</th></tr></thead>
                  <tbody>${versionRows}</tbody>
                </table>
              </div>
            </td>
          </tr>
        `;
        tbody.insertAdjacentHTML("beforeend", rowHTML);
      }

      // show table & export buttons
      if (tableContainer) tableContainer.classList.remove("hidden");
      if (exportButtons) exportButtons.classList.remove("hidden");

      // attach toggles
      document.querySelectorAll(".details-toggle").forEach((btn) => {
        btn.addEventListener("click", () => {
          const content = btn.nextElementSibling;
          const open = content.classList.toggle("show");
          const count = content.querySelectorAll("tbody tr").length;
          btn.textContent = open ? "Hide versions" : `Show ${count} versions`;
        });
      });

      // Build filter selects
      const loaderSet = new Set(
        rowsForExport.map((r) => r.loader).filter(Boolean)
      );
      const versionSet = new Set(
        rowsForExport.map((r) => r.version).filter(Boolean)
      );

      function populateFilterSelect(selectEl, values) {
        if (!selectEl) return;
        selectEl.innerHTML = `<option value="">All</option>`;
        [...values].sort().forEach((v) => {
          const opt = document.createElement("option");
          opt.value = v;
          opt.textContent = v;
          selectEl.appendChild(opt);
        });
      }
      populateFilterSelect(document.getElementById("filterLoader"), loaderSet);
      populateFilterSelect(
        document.getElementById("filterVersion"),
        versionSet
      );
      if (filterSection) filterSection.classList.remove("hidden");

      // Filtering
      function applyFilters() {
        const loaderValEl = document.getElementById("filterLoader");
        const versionValEl = document.getElementById("filterVersion");
        const loaderVal = loaderValEl ? loaderValEl.value : "";
        const versionVal = versionValEl ? versionValEl.value : "";
        document.querySelectorAll("#resultTable tbody tr").forEach((row) => {
          const pairs = JSON.parse(row.getAttribute("data-pairs") || "[]");
          if (!pairs.length) {
            row.style.display = "";
            return;
          }
          const matchesLoader =
            !loaderVal ||
            pairs.some((p) => p[1].toLowerCase() === loaderVal.toLowerCase());
          const matchesVersion =
            !versionVal || pairs.some((p) => p[0] === versionVal);
          row.style.display = matchesLoader && matchesVersion ? "" : "none";
        });
      }
      const filterLoaderEl = document.getElementById("filterLoader");
      const filterVersionEl = document.getElementById("filterVersion");
      if (filterLoaderEl) filterLoaderEl.onchange = applyFilters;
      if (filterVersionEl) filterVersionEl.onchange = applyFilters;

      // Compatibility summary (improved)
      function computeCompatibility(mods) {
        if (!mods.length) return { type: "bad", text: "No mods provided" };

        // Helper: parse versions into comparable numeric parts
        function versionKey(v) {
          return v
            .split(".")
            .map((x) => parseInt(x, 10))
            .filter((n) => !isNaN(n));
        }

        // Helper: compare two versions semantically (1.20.10 > 1.20.2)
        function compareVersions(a, b) {
          const pa = versionKey(a);
          const pb = versionKey(b);
          for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
            const diff = (pb[i] || 0) - (pa[i] || 0);
            if (diff !== 0) return diff; // descending (latest first)
          }
          return 0;
        }

        // Collect per mod pairs (like "loader|version")
        const perModSets = mods.map(
          (m) => new Set(m.pairs.map((p) => `${p[1]}|${p[0]}`))
        );

        // Compute strict intersection
        const intersection = [...perModSets[0]].filter((x) =>
          perModSets.every((s) => s.has(x))
        );

        // If full intersection exists
        if (intersection.length > 0) {
          const byLoader = {};
          intersection.forEach((k) => {
            const [loader, version] = k.split("|");
            if (!byLoader[loader]) byLoader[loader] = new Set();
            byLoader[loader].add(version);
          });
          const results = Object.entries(byLoader).map(([loader, versions]) => {
            const sorted = [...versions].sort(compareVersions);
            const best = sorted[0];
            return `${loader} ${best}`;
          });
          return {
            type: "good",
            text: `All mods share → ${results.join(" / ")}`,
          };
        }

        // If no perfect match, look for partial overlap
        const countMap = {};
        perModSets.forEach((s) => {
          s.forEach((k) => {
            countMap[k] = (countMap[k] || 0) + 1;
          });
        });

        const total = mods.length;
        const threshold = Math.max(2, Math.floor(total * 0.5)); // appear in at least 50%
        const common = Object.entries(countMap)
          .filter(([k, c]) => c >= threshold)
          .sort((a, b) => b[1] - a[1]); // by frequency

        if (!common.length) {
          return {
            type: "bad",
            text: "No common denominator between your mods",
          };
        }

        // Group partial matches by loader
        const byLoader = {};
        common.forEach(([k, c]) => {
          const [loader, version] = k.split("|");
          if (!byLoader[loader]) byLoader[loader] = [];
          byLoader[loader].push(version);
        });

        const results = Object.entries(byLoader).map(([loader, versions]) => {
          const sorted = versions.sort(compareVersions);
          return `${loader} ${sorted[0]}`;
        });

        return {
          type: "warning",
          text: `Most of your mods share → ${results.join(" / ")}`,
        };
      }

      // Exports with timestamped filenames
      const exportCSVBtn = document.getElementById("exportCSV");
      const exportMDBtn = document.getElementById("exportMD");

      if (exportCSVBtn) exportCSVBtn.onclick = () => exportCSV(rowsForExport);
      if (exportMDBtn) exportMDBtn.onclick = () => exportMD(rowsForExport);
    } catch (err) {
      console.error("Analyze error:", err);
      alert(
        "An error occurred while fetching mod data. See console for details."
      );
      const loadingEl = document.getElementById("loading");
      if (loadingEl) loadingEl.classList.add("hidden");
    }
  }); // end analyze handler
}); // end DOMContentLoaded

// export functions
function exportCSV(rows) {
  if (!rows || !rows.length) return alert("No data to export!");
  const header = "Mod Name,Version,Loader,URL\n";
  const csv = rows
    .map((r) => `"${r.name}","${r.version}","${r.loader}","${r.url}"`)
    .join("\n");
  const filename = `mods-${exportTimestamp()}.csv`;
  downloadFile(filename, header + csv);
}
function exportMD(rows) {
  if (!rows || !rows.length) return alert("No data to export!");
  let md = "| Mod Name | Version | Loader |\n|---|---:|---:|\n";
  for (const r of rows) {
    md += `| [${r.name}](${r.url}) | ${r.version} | ${r.loader} |\n`;
  }
  const filename = `mods-${exportTimestamp()}.md`;
  downloadFile(filename, md);
}
function downloadFile(filename, content) {
  const blob = new Blob([content], { type: "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
}

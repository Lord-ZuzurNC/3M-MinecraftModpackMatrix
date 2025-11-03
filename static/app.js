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

// ---------- Theme switcher ----------
const themeToggle = document.getElementById("themeToggle");

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

// ---------- Analyze handler ----------
document.getElementById("analyzeBtn").addEventListener("click", async () => {
  const input = document.getElementById("urlInput").value.trim();
  if (!input) return alert("Please enter at least one URL.");

  const urlinput = input
    .split("\n")
    .map((u) => u.trim())
    .filter(Boolean);
  const loading = document.getElementById("loading");
  const tableContainer = document.getElementById("tableContainer");
  const tbody = document.querySelector("#resultTable tbody");
  const exportButtons = document.getElementById("exportButtons");
  const filterSection = document.getElementById("filterSection");
  const topSummary = document.getElementById("compatibilitySummaryTop");
  const bottomSummary = document.getElementById("compatibilitySummaryBottom");

  // reset UI
  loading.classList.remove("hidden");
  tableContainer.classList.add("hidden");
  exportButtons.classList.add("hidden");
  filterSection.classList.add("hidden");
  topSummary.classList.add("hidden");
  bottomSummary.classList.add("hidden");
  tbody.innerHTML = "";
  rowsForExport = [];

  const urlRegex = /^https?:\/\/(www\.)?(curseforge\.com|modrinth\.com)\/.+/i;
  const urls = document
    .getElementById("urls")
    .value.split(/\n+/)
    .map((u) => u.trim())
    .filter(Boolean);

  const validUrls = urls.filter((u) => urlRegex.test(u));
  const invalidUrls = urls.filter((u) => !urlRegex.test(u));

  if (invalidUrls.length > 0) {
    alert("Some URLs are invalid:\n" + invalidUrls.join("\n"));
    return;
  }

  try {
    const res = await fetch("/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls }),
    });
    const data = await res.json();
    loading.classList.add("hidden");

    // Build rows & a helper data structure
    const modsData = []; // { name, url, pairs: [[version,loader], ...] }

    for (const mod of data) {
      if (mod.error) {
        tbody.insertAdjacentHTML(
          "beforeend",
          `
          <tr><td colspan="2" style="color:#f55">${mod.url || mod.name}: ${
            mod.error
          }</td></tr>
        `
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
    tableContainer.classList.remove("hidden");
    exportButtons.classList.remove("hidden");

    // attach toggles
    document.querySelectorAll(".details-toggle").forEach((btn) => {
      btn.addEventListener("click", () => {
        const content = btn.nextElementSibling;
        const open = content.classList.toggle("show");
        const count = content.querySelectorAll("tbody tr").length;
        btn.textContent = open ? "Hide versions" : `Show ${count} versions`;
      });
    });

    // --- Build filter selects from rowsForExport (deduped) ---
    const loaderSet = new Set(
      rowsForExport.map((r) => r.loader).filter(Boolean)
    );
    const versionSet = new Set(
      rowsForExport.map((r) => r.version).filter(Boolean)
    );

    function populateFilterSelect(selectEl, values) {
      selectEl.innerHTML = `<option value="">All</option>`;
      [...values].sort().forEach((v) => {
        const opt = document.createElement("option");
        opt.value = v;
        opt.textContent = v;
        selectEl.appendChild(opt);
      });
    }
    populateFilterSelect(document.getElementById("filterLoader"), loaderSet);
    populateFilterSelect(document.getElementById("filterVersion"), versionSet);
    filterSection.classList.remove("hidden");

    // --- Filtering uses the structured data stored in data-pairs attribute ---
    function applyFilters() {
      const loaderVal = document.getElementById("filterLoader").value;
      const versionVal = document.getElementById("filterVersion").value;
      document.querySelectorAll("#resultTable tbody tr").forEach((row) => {
        const pairs = JSON.parse(row.getAttribute("data-pairs") || "[]"); // [[version,loader],...]
        // if row has no pairs (error row), show it
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
    document.getElementById("filterLoader").onchange = applyFilters;
    document.getElementById("filterVersion").onchange = applyFilters;

    // --- Compatibility summary (top & bottom) ---
    function computeCompatibility(mods) {
      // mods: [{pairs: [[ver,ldr], ...]}, ...]
      if (!mods.length) return { type: "bad", text: "No mods provided" };

      // make per-mod set of strings "Loader|Version"
      const perModSets = mods.map(
        (m) => new Set(m.pairs.map((p) => `${p[1]}|${p[0]}`))
      );

      // intersection: pairs present in all mods
      const intersection = [...perModSets[0]].filter((x) =>
        perModSets.every((s) => s.has(x))
      );

      if (intersection.length > 0) {
        // we may have many pairs across loaders; for each loader pick highest version
        const byLoader = {};
        intersection.forEach((k) => {
          const [loader, version] = k.split("|");
          if (!byLoader[loader]) byLoader[loader] = new Set();
          byLoader[loader].add(version);
        });
        // choose highest version per loader
        const results = Object.entries(byLoader).map(([loader, versions]) => {
          const best = [...versions].sort((a, b) =>
            b.localeCompare(a, undefined, { numeric: true })
          )[0];
          return `${loader} - ${best}`;
        });
        return { type: "good", text: results.join("  &  ") };
      }

      // no full intersection → compute most-common pair across mods
      // count how many distinct mods contain each pair
      const countMap = {};
      perModSets.forEach((s) => {
        s.forEach((k) => {
          countMap[k] = (countMap[k] || 0) + 1;
        });
      });

      // sort by count desc
      const sorted = Object.entries(countMap).sort((a, b) => b[1] - a[1]);
      if (!sorted.length)
        return { type: "bad", text: "No common denominator between your mods" };

      const [topKey, topCount] = sorted[0];
      // tie?
      const ties = sorted.filter(([k, c]) => c === topCount);
      if (ties.length > 1) {
        return { type: "bad", text: "No common denominator between your mods" };
      }

      // if topCount == number of mods, would've been in intersection; so here topCount < mods.length
      if (topCount > 1) {
        // partial commonality — present in topCount mods
        const [loader, version] = topKey.split("|");
        return {
          type: "warning",
          text: `Most of your mods share: ${loader} - ${version} (${topCount}/${mods.length})`,
        };
      }

      return { type: "bad", text: "No common denominator between your mods" };
    }

    const summary = computeCompatibility(modsData);
    [topSummary, bottomSummary].forEach((el) => {
      el.className = `compatibility ${summary.type}`;
      el.textContent = summary.text;
      el.classList.remove("hidden");
    });

    // --- Exports wired to rowsForExport (module-scope) ---
    document.getElementById("exportCSV").onclick = () =>
      exportCSV(rowsForExport);
    document.getElementById("exportMD").onclick = () => exportMD(rowsForExport);
  } catch (err) {
    console.error(err);
    alert("An error occurred. Check console for details.");
    loading.classList.add("hidden");
  }
}); // end analyze handler

document.getElementById("clearCacheBtn").addEventListener("click", async () => {
  if (!confirm("Do you want to remove all local cache?")) return;
  const res = await fetch("/clear_cache", { method: "POST" });
  const msg = await res.text();
  alert(msg);
});

function timestamp() {
  const d = new Date();
  return d.toISOString().slice(0, 19).replace(/[:T]/g, "-");
}

// export functions unchanged but use passed rows
function exportCSV(rows) {
  if (!rows || !rows.length) return alert("No data to export!");
  const header = "Mod Name,Version,Loader,URL\n";
  const csv = rows
    .map((r) => `"${r.name}","${r.version}","${r.loader}","${r.url}"`)
    .join("\n");
  const filename = `mods-${timestamp()}.csv`;
  downloadFile("${filename}.csv", header + csv);
}
function exportMD(rows) {
  if (!rows || !rows.length) return alert("No data to export!");
  let md = "| Mod Name | Version | Loader |\n|---|---:|---:|\n";
  for (const r of rows) {
    md += `| [${r.name}](${r.url}) | ${r.version} | ${r.loader} |\n`;
  }
  const filename = `mods-${timestamp()}.md`;
  downloadFile("{filename}.md", md);
}
function downloadFile(filename, content) {
  const blob = new Blob([content], { type: "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
}

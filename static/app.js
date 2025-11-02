// === THEME SWITCHER ===
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

// === DOM ELEMENTS ===
const analyzeBtn = document.getElementById("analyzeBtn");
const urlInput = document.getElementById("urlInput");
const loading = document.getElementById("loading");
const tableContainer = document.getElementById("tableContainer");
const tbody = document.querySelector("#resultTable tbody");
const exportButtons = document.getElementById("exportButtons");

// === ANALYZE FUNCTION ===
analyzeBtn.addEventListener("click", async () => {
  const input = urlInput.value.trim();
  if (!input) return alert("Please enter at least one URL.");

  const urls = input
    .split("\n")
    .map((u) => u.trim())
    .filter(Boolean);

  loading.classList.remove("hidden");
  tableContainer.classList.add("hidden");
  exportButtons.classList.add("hidden");
  tbody.innerHTML = "";

  try {
    const res = await fetch("/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls }),
    });
    const data = await res.json();
    loading.classList.add("hidden");

    const allRows = [];

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

      // Flatten for export
      mod.versions.forEach(([version, loader]) =>
        allRows.push({ name: mod.name, version, loader, url: mod.url })
      );

      // Create the dropdown with nested table
      const versionRows = mod.versions
        .map(
          ([version, loader]) => `
        <tr><td>${version}</td><td>${loader}</td></tr>
      `
        )
        .join("");

      const rowHTML = `
        <tr>
          <td><a href="${mod.url}" target="_blank" rel="noopener">${mod.name}</a></td>
          <td class="details-cell">
            <button class="details-toggle">Show ${mod.versions.length} versions</button>
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

    tableContainer.classList.remove("hidden");
    exportButtons.classList.remove("hidden");

    // Attach dropdown handlers
    document.querySelectorAll(".details-toggle").forEach((btn) => {
      btn.addEventListener("click", () => {
        const content = btn.nextElementSibling;
        const open = content.classList.toggle("show");
        btn.textContent = open
          ? "Hide versions"
          : `Show ${content.querySelectorAll("tbody tr").length} versions`;
      });
    });

    // Export buttons
    document.getElementById("exportCSV").onclick = () => exportCSV(allRows);
    document.getElementById("exportMD").onclick = () => exportMD(allRows);
  } catch (err) {
    console.error(err);
    alert("An error occurred. Check console for details.");
    loading.classList.add("hidden");
  }

  // Collect all versions/loaders for filtering and comparison
  const allLoaders = new Set();
  const allVersions = new Set();
  const modPairs = [];

  for (const mod of data.filter((m) => !m.error)) {
    const pairs = mod.versions.map(([version, loader]) => ({
      version,
      loader,
    }));
    modPairs.push(pairs);
    pairs.forEach((p) => {
      if (p.loader) allLoaders.add(p.loader);
      if (p.version) allVersions.add(p.version);
    });
  }

  // === Compute compatibility ===
  function computeCompatibility(pairsPerMod) {
    const intersection = pairsPerMod.reduce((acc, pairs) => {
      const pairStrings = pairs.map((p) => `${p.loader} ${p.version}`);
      return acc ? acc.filter((x) => pairStrings.includes(x)) : pairStrings;
    }, null);

    if (intersection && intersection.length > 0) {
      // ✅ Perfect match
      const best = pickBest(intersection);
      return { type: "good", text: `All your mods share: ${best}` };
    }

    // ❌ No perfect match → check most common
    const freq = {};
    pairsPerMod.flat().forEach((p) => {
      const key = `${p.loader} ${p.version}`;
      freq[key] = (freq[key] || 0) + 1;
    });

    const sorted = Object.entries(freq).sort((a, b) => b[1] - a[1]);
    const [top, second] = sorted;

    if (!top) return { type: "bad", text: "No mods found" };

    if (second && top[1] === second[1]) {
      // Tie → no clear winner
      return { type: "bad", text: "No common denominator between your mods" };
    }

    if (top[1] > 1) {
      // ⚠️ Partial commonality
      return { type: "warning", text: `Most of your mods share: ${top[0]}` };
    }

    // 🚫 None share anything
    return { type: "bad", text: "No common denominator between your mods" };
  }

  function pickBest(pairs) {
    // Prefer higher version numerically if multiple (e.g., 1.20.1 > 1.19)
    const sorted = pairs.sort((a, b) => {
      const va = a.match(/\d+(\.\d+)*/)?.[0] || "";
      const vb = b.match(/\d+(\.\d+)*/)?.[0] || "";
      return vb.localeCompare(va, undefined, { numeric: true });
    });
    return sorted[0];
  }

  const summary = computeCompatibility(modPairs);
  const summaryEls = [
    document.getElementById("compatibilitySummaryTop"),
    document.getElementById("compatibilitySummaryBottom"),
  ];

  for (const el of summaryEls) {
    el.className = `compatibility ${summary.type}`;
    el.textContent = summary.text;
    el.classList.remove("hidden");
  }

  // === Populate filter dropdowns ===
  populateFilterSelect(document.getElementById("filterLoader"), allLoaders);
  populateFilterSelect(document.getElementById("filterVersion"), allVersions);
  document.getElementById("filterSection").classList.remove("hidden");

  function populateFilterSelect(select, values) {
    select.innerHTML = `<option value="">All</option>`;
    [...values].sort().forEach((v) => {
      const opt = document.createElement("option");
      opt.value = v;
      opt.textContent = v;
      select.appendChild(opt);
    });
  }

  // === Filtering logic ===
  function applyFilters() {
    const loaderVal = document.getElementById("filterLoader").value;
    const versionVal = document.getElementById("filterVersion").value;

    document.querySelectorAll("#resultTable tbody tr").forEach((row) => {
      const inner = row.querySelector(".details-content");
      const visible =
        (!loaderVal && !versionVal) ||
        (inner &&
          inner.textContent.includes(loaderVal) &&
          inner.textContent.includes(versionVal));
      row.style.display = visible ? "" : "none";
    });
  }

  document.getElementById("filterLoader").onchange = applyFilters;
  document.getElementById("filterVersion").onchange = applyFilters;
});

// === EXPORT FUNCTIONS ===
function exportCSV(rows) {
  if (!rows.length) return alert("No data to export!");
  const header = "Mod Name,Version,Loader,URL\n";
  const csv = rows
    .map((r) => `"${r.name}","${r.version}","${r.loader}","${r.url}"`)
    .join("\n");
  downloadFile("mods.csv", header + csv);
}

function exportMD(rows) {
  if (!rows.length) return alert("No data to export!");
  let md =
    "| Mod Name | Version | Loader |\n|-----------|----------|---------|\n";
  for (const r of rows) {
    md += `| [${r.name}](${r.url}) | ${r.version} | ${r.loader} |\n`;
  }
  downloadFile("mods.md", md);
}

function downloadFile(filename, content) {
  const blob = new Blob([content], { type: "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
}

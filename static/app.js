async function postJSON(url, data) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

let allResults = [];

function createProviderLogo(provider) {
  const img = document.createElement("img");
  img.className = "provider-logo";
  img.alt = provider;
  img.src = provider === "curseforge" ? "/static/cf.svg" : "/static/mr.svg";
  return img;
}

function renderTable(results) {
  const container = document.getElementById("results");
  container.innerHTML = "";

  const table = document.createElement("table");
  const header = document.createElement("tr");
  header.innerHTML =
    "<th>Source</th><th>Mod Name</th><th>Versions / Loaders</th>";
  table.appendChild(header);

  for (const mod of results) {
    const row = document.createElement("tr");

    // Source Logo
    const providerCell = document.createElement("td");
    providerCell.appendChild(createProviderLogo(mod.provider || "?"));

    // Mod Name (clickable)
    const nameCell = document.createElement("td");
    if (mod.url) {
      const a = document.createElement("a");
      a.href = mod.url;
      a.target = "_blank";
      a.textContent = mod.name || "Unknown";
      nameCell.appendChild(a);
    } else {
      nameCell.textContent = mod.name || "Unknown";
    }

    // Versions / Loaders with toggle
    const versionsCell = document.createElement("td");
    if (mod.error) {
      versionsCell.textContent = mod.error;
    } else {
      const toggleBtn = document.createElement("button");
      toggleBtn.textContent = "Show";
      const list = document.createElement("ul");
      list.style.display = "none";
      const seen = new Set();
      for (const [ver, loader] of mod.versions || []) {
        const key = `${ver}-${loader}`;
        if (seen.has(key)) continue;
        seen.add(key);
        const li = document.createElement("li");
        li.textContent = `${ver} → ${loader}`;
        list.appendChild(li);
      }
      toggleBtn.onclick = () => {
        const visible = list.style.display === "block";
        list.style.display = visible ? "none" : "block";
        toggleBtn.textContent = visible ? "Show" : "Hide";
      };
      versionsCell.append(toggleBtn, list);
    }

    row.append(providerCell, nameCell, versionsCell);
    table.appendChild(row);
  }

  container.appendChild(table);
}

document.getElementById("analyze-btn").onclick = async () => {
  const urls = document
    .getElementById("mod-urls")
    .value.split("\n")
    .map((u) => u.trim())
    .filter((u) => u);
  if (!urls.length) return alert("Please enter at least one URL");
  const data = await postJSON("/analyze", { urls });
  allResults = data;
  renderTable(data);
  populateFilters(data);
};

document.getElementById("clear-cache").onclick = async () => {
  if (!confirm("Clear cache?")) return;
  const res = await fetch("/clear_cache", { method: "POST" });
  const data = await res.json();
  alert(data.message || "Done");
};

document.getElementById("theme-toggle").onclick = () => {
  document.body.classList.toggle("dark");
};

function populateFilters(data) {
  const versions = new Set();
  const loaders = new Set();
  data.forEach((m) => {
    (m.versions || []).forEach(([v, l]) => {
      versions.add(v);
      loaders.add(l);
    });
  });
  fillDropdown("filter-version", versions);
  fillDropdown("filter-loader", loaders);
}

function fillDropdown(id, items) {
  const select = document.getElementById(id);
  select.innerHTML = '<option value="">All</option>';
  [...items].sort().forEach((i) => {
    const opt = document.createElement("option");
    opt.value = opt.textContent = i;
    select.appendChild(opt);
  });
}

document.getElementById("apply-filters").onclick = () => {
  const v = document.getElementById("filter-version").value;
  const l = document.getElementById("filter-loader").value;
  const filtered = allResults.filter((m) => {
    if (!m.versions) return true;
    return m.versions.some(
      ([ver, loader]) => (!v || ver === v) && (!l || loader === l)
    );
  });
  renderTable(filtered);
};

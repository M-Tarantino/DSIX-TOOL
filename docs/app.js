const STATUS_COLOR = {
  "Stable": "var(--teal)",
  "Watchful": "var(--steel)",
  "Elevated": "var(--ochre)",
  "High Alert": "var(--amber)",
  "Crisis": "var(--red)",
};

const DIMENSION_COLOR = {
  terrorism_extremism: "var(--red)",
  cyber_security: "var(--amber)",
  critical_infrastructure: "var(--ochre)",
  political_stability: "var(--steel)",
  societal_safety: "var(--teal)",
};

async function fetchJson(path, fallback) {
  try {
    const res = await fetch(path, { cache: "no-store" });
    if (!res.ok) return fallback;
    return await res.json();
  } catch {
    return fallback;
  }
}

function formatTimestamp(iso) {
  if (!iso) return "—";
  const date = new Date(iso);
  return date.toLocaleString("en-GB", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit", timeZoneName: "short",
  });
}

function renderHero(score) {
  document.getElementById("heroScore").textContent = score.overall_score;
  const statusEl = document.getElementById("heroStatus");
  statusEl.textContent = score.status;
  statusEl.style.color = STATUS_COLOR[score.status] || "var(--text-muted)";
  document.getElementById("lastUpdated").textContent =
    "Updated " + formatTimestamp(score.computed_at);
  document.getElementById("scaleMarker").style.left = score.overall_score + "%";
}

function renderDimensions(score) {
  const container = document.getElementById("dimensionList");
  container.innerHTML = "";
  const entries = Object.entries(score.dimensions)
    .sort((a, b) => b[1].weight - a[1].weight);

  for (const [key, dim] of entries) {
    const row = document.createElement("div");
    row.className = "dimension-row";
    row.innerHTML = `
      <div class="dimension-name">${dim.label}<br><span class="dimension-weight">${Math.round(dim.weight * 100)}% weight</span></div>
      <div class="dimension-bar-track">
        <div class="dimension-bar-fill" style="width:${dim.score}%; background:${DIMENSION_COLOR[key] || "var(--steel)"}"></div>
      </div>
      <div class="dimension-score">${dim.score.toFixed(0)}<br><span style="opacity:.7">${dim.incidents_counted} inc.</span></div>
    `;
    container.appendChild(row);
  }
}

function renderTrend(history) {
  const svg = document.getElementById("trendChart");
  if (!history || history.length < 2) {
    svg.innerHTML = `<text x="8" y="60" fill="var(--text-muted)" font-family="var(--font-sans)" font-size="12">Not enough history yet — check back after a few scheduled runs.</text>`;
    return;
  }

  const width = 640, height = 120, pad = 8;
  const scores = history.map(h => h.overall_score);
  const points = scores.map((s, i) => {
    const x = pad + (i / (scores.length - 1)) * (width - pad * 2);
    const y = height - pad - (s / 100) * (height - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  svg.innerHTML = `
    <polyline points="${points.join(" ")}" fill="none" stroke="var(--steel)" stroke-width="2" />
    <circle cx="${points[points.length - 1].split(",")[0]}" cy="${points[points.length - 1].split(",")[1]}" r="3.5" fill="var(--text)" />
  `;
}

function renderIncidents(incidents) {
  const container = document.getElementById("incidentList");
  if (!incidents || incidents.length === 0) return; // keep the static empty-state markup

  const sorted = [...incidents].sort((a, b) => new Date(b.date) - new Date(a.date)).slice(0, 25);
  container.innerHTML = "";
  for (const incident of sorted) {
    const row = document.createElement("div");
    row.className = "incident-row";
    const dateStr = incident.date ? incident.date.slice(0, 10) : "—";
    row.innerHTML = `
      <div class="incident-tags">
        <span class="tag">${(incident.dimension || "").replace(/_/g, " ")}</span>
        <span class="tag tag-severity-${incident.severity}">${incident.severity}</span>
        <span class="incident-date">${dateStr}</span>
      </div>
      <div class="incident-summary">${incident.summary || incident.title || ""}</div>
      <div class="incident-meta">
        ${incident.location ? incident.location + " · " : ""}${incident.source || ""}
        ${incident.url ? ` · <a href="${incident.url}" target="_blank" rel="noopener">source</a>` : ""}
      </div>
    `;
    container.appendChild(row);
  }
}

function renderTop10(top10) {
  const synthesisEl = document.getElementById("top10Synthesis");
  const listEl = document.getElementById("top10List");
  if (!top10 || !top10.items || top10.items.length === 0) return; // keep static empty-state

  synthesisEl.textContent = top10.synthesis_text || "";
  synthesisEl.classList.remove("empty-state");

  listEl.innerHTML = "";
  top10.items.forEach((item, i) => {
    const row = document.createElement("div");
    row.className = "incident-row";
    const dateStr = item.date ? item.date.slice(0, 10) : "—";
    row.innerHTML = `
      <div class="incident-tags">
        <span class="tag">#${i + 1}</span>
        <span class="tag">${(item.dimension || "").replace(/_/g, " ")}</span>
        <span class="tag tag-severity-${item.severity}">${item.severity}</span>
        <span class="incident-date">${dateStr}</span>
      </div>
      <div class="incident-summary">${item.summary || item.title || ""}</div>
      <div class="incident-meta">
        ${item.location ? item.location + " · " : ""}${item.source || ""}
        ${item.url ? ` · <a href="${item.url}" target="_blank" rel="noopener">source</a>` : ""}
      </div>
    `;
    listEl.appendChild(row);
  });
}

async function init() {
  const [score, history, incidents, top10] = await Promise.all([
    fetchJson("data/score.json", null),
    fetchJson("data/history.json", []),
    fetchJson("data/incidents.json", []),
    fetchJson("data/top10.json", null),
  ]);

  if (score) {
    renderHero(score);
    renderDimensions(score);
  }
  renderTrend(history);
  renderTop10(top10);
  renderIncidents(incidents);
}

init();

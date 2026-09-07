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
    hour: "2-digit", minute: "2-digit",
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

function renderTrend7Days(history) {
  if (!history || history.length < 2) {
    document.getElementById("heroTrend").innerHTML = `<span>—</span><span>—</span>`;
    return;
  }
  
  const last7 = history.slice(-7);
  const first = last7[0].overall_score;
  const last = last7[last7.length - 1].overall_score;
  const diff = last - first;
  const direction = diff > 0 ? "↑" : diff < 0 ? "↓" : "→";
  const color = diff > 0 ? "var(--red)" : diff < 0 ? "var(--teal)" : "var(--text-muted)";
  
  document.getElementById("trendDirection").textContent = direction;
  document.getElementById("trendDirection").style.color = color;
  document.getElementById("trendValue").textContent = `${Math.abs(diff).toFixed(1)}`;
  document.getElementById("trendValue").style.color = color;
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
      <div class="dimension-score">${dim.score.toFixed(0)}</div>
    `;
    container.appendChild(row);
  }
}

function renderTrendChart(history) {
  const svg = document.getElementById("trendChart");
  if (!history || history.length < 2) {
    svg.innerHTML = `<text x="8" y="60" fill="var(--text-muted)" font-family="var(--font-sans)" font-size="12">Not enough history yet.</text>`;
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

function renderIncidents(incidents, container, limit = null) {
  if (!incidents || incidents.length === 0) {
    container.innerHTML = `<p class="empty-state">No incidents.</p>`;
    return;
  }

  const sorted = [...incidents]
    .sort((a, b) => new Date(b.date) - new Date(a.date))
    .slice(0, limit || 25);

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

function getMostImportantSinceMidnight(recent) {
  if (!recent || recent.length === 0) return [];
  
  const now = new Date();
  const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  
  const sinceMidnight = recent
    .filter(inc => new Date(inc.date) >= midnight)
    .sort((a, b) => {
      const severityOrder = { critical: 0, severe: 1, moderate: 2, minor: 3 };
      return (severityOrder[a.severity] || 99) - (severityOrder[b.severity] || 99);
    });
  
  return sinceMidnight.slice(0, 5);
}

function getTop5(allIncidents) {
  if (!allIncidents || allIncidents.length === 0) return [];
  
  const severityScore = { critical: 4, severe: 3, moderate: 2, minor: 1 };
  const now = new Date();
  
  const scored = allIncidents.map(inc => {
    const age = (now - new Date(inc.date)) / (1000 * 60 * 60 * 24);
    const decay = Math.pow(0.5, age / 14);
    const base = severityScore[inc.severity] || 0;
    return { ...inc, score: base * decay };
  });
  
  return scored
    .sort((a, b) => b.score - a.score)
    .slice(0, 5)
    .map(({ score, ...rest }) => rest);
}

async function init() {
  const [score, history, recent, allIncidents] = await Promise.all([
    fetchJson("data/score.json", null),
    fetchJson("data/history.json", []),
    fetchJson("data/incidents-recent.json", []),
    fetchJson("data/incidents.json", []),
  ]);

  if (score) {
    renderHero(score);
    renderDimensions(score);
    renderTrendChart(history);
    renderTrend7Days(history);
  }

  // Latest RSS (recent)
  const rssCount = document.getElementById("rssCount");
  rssCount.textContent = recent.length;
  renderIncidents(recent, document.getElementById("latestRss"), 3);

  // Latest Web — mark by source containing "deep-search" or similar
  const webIncidents = recent.filter(inc => inc.item_id && inc.item_id.includes("deep-search"));
  document.getElementById("webCount").textContent = webIncidents.length;
  renderIncidents(webIncidents, document.getElementById("latestWeb"), 3);

  // Top since midnight
  const topMidnight = getMostImportantSinceMidnight(recent);
  renderIncidents(topMidnight, document.getElementById("topMidnight"), 5);

  // Top 5 all time
  const top5 = getTop5(allIncidents);
  renderIncidents(top5, document.getElementById("top5List"), 5);
}

init();
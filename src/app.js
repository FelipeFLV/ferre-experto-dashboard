const state = {
  data: null,
  month: "all",
  metric: "views",
  granularity: "daily",
  sort: "date",
  query: "",
  videosOnly: false,
  expanded: new Set(),
  trendChart: null,
};

const NUMBER = new Intl.NumberFormat("es-PE", { maximumFractionDigits: 0 });
const DECIMAL = new Intl.NumberFormat("es-PE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const DATE_SHORT = new Intl.DateTimeFormat("es-PE", { day: "numeric", month: "short" });
const DATE_LONG = new Intl.DateTimeFormat("es-PE", { day: "numeric", month: "long", year: "numeric" });
const DATE_TIME = new Intl.DateTimeFormat("es-PE", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: "America/Lima",
});
const METRIC_LABELS = { views: "Views", viewers: "Viewers", visits: "Visits", follows: "Follows" };
const TYPE_LABELS = {
  photos: "Foto",
  photo: "Foto",
  videos: "Video",
  video: "Video",
  reel: "Reel",
  "multi media": "Multimedia",
  link: "Enlace",
  text: "Texto",
};

function escapeHtml(value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

function number(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return NUMBER.format(value);
}

function decimal(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return DECIMAL.format(value);
}

function percent(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${DECIMAL.format(value)}%`;
}

function parseDate(iso) {
  return new Date(`${iso}T12:00:00`);
}

function formatDate(iso) {
  return DATE_LONG.format(parseDate(iso));
}

function formatDateShort(iso) {
  return DATE_SHORT.format(parseDate(iso));
}

function formatCutoff(iso) {
  const [year, month, day] = iso.split("-");
  return `${day}/${month}/${year}`;
}

function formatUpdated(iso) {
  if (!iso) return "—";
  const value = new Date(iso);
  if (Number.isNaN(value.getTime())) return "—";
  return DATE_TIME.format(value);
}

function typeLabel(type) {
  return TYPE_LABELS[String(type || "").toLowerCase()] || type || "Publicación";
}

function formatDuration(seconds) {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${NUMBER.format(seconds)} s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ${Math.round(seconds % 60)} s`;
  const hours = Math.floor(minutes / 60);
  return `${hours} h ${minutes % 60} min`;
}

function monthMeta(key) {
  return state.data.months.find((month) => month.key === key);
}

function monthLabel(key) {
  const meta = monthMeta(key);
  if (!meta) return key;
  return meta.partial ? `${meta.label} (en curso)` : meta.label;
}

function rangeLabel() {
  const months = state.data.months;
  if (!months.length) return "";
  return months.length === 1 ? months[0].label : `${months[0].label} – ${months[months.length - 1].label}`;
}

function currentTotals() {
  if (state.month === "all") {
    return state.data.results.daily.reduce((acc, row) => {
      acc.views += row.views;
      acc.viewers += row.viewers;
      acc.visits += row.visits;
      acc.follows += row.follows;
      return acc;
    }, { views: 0, viewers: 0, visits: 0, follows: 0 });
  }
  return state.data.results.monthly.find((row) => row.month === state.month) || { views: 0, viewers: 0, visits: 0, follows: 0 };
}

function previousTotals() {
  const index = state.data.months.findIndex((month) => month.key === state.month);
  if (index <= 0) return null;
  return state.data.results.monthly[index - 1];
}

function setupHeader() {
  const cutoff = state.data.page.cutoff;
  document.querySelectorAll("#cutoff-label, #footer-cutoff").forEach((node) => {
    node.textContent = formatCutoff(cutoff);
  });
  document.querySelector("#cutoff-copy").textContent = formatCutoff(cutoff);
  document.querySelectorAll("#footer-updated, #updated-copy").forEach((node) => {
    node.textContent = formatUpdated(state.data.page.updatedAt);
  });
  document.querySelector("#followers-label").textContent = NUMBER.format(state.data.page.followers);

  const select = document.querySelector("#period-select");
  const options = [{ key: "all", label: "Todo el período" }].concat(
    state.data.months.map((month) => ({ key: month.key, label: monthLabel(month.key) }))
  );
  select.innerHTML = options
    .map((option) => `<option value="${escapeHtml(option.key)}">${escapeHtml(option.label)}</option>`)
    .join("");
}

function renderKPIs() {
  const totals = currentTotals();
  const previous = previousTotals();
  const activeMonth = state.month === "all" ? null : monthMeta(state.month);
  const isPartial = Boolean(activeMonth && activeMonth.partial);

  ["views", "viewers", "visits", "follows"].forEach((key) => {
    document.querySelector(`#kpi-${key}`).textContent = number(totals[key]);
    const delta = document.querySelector(`#delta-${key}`);
    delta.className = "kpi-delta";
    delta.textContent = "";

    if (state.month === "all") {
      delta.textContent = rangeLabel();
      return;
    }
    if (!previous) {
      delta.textContent = "Sin mes anterior comparable";
      return;
    }
    if (!previous[key]) {
      delta.textContent = "Sin base de comparación";
      return;
    }
    const change = ((totals[key] - previous[key]) / previous[key]) * 100;
    const sign = change > 0 ? "+" : "";
    delta.textContent = `${sign}${decimal(change)}% vs. ${monthMeta(previous.month).short}${isPartial ? " · mes en curso" : ""}`;
    delta.classList.add(change >= 0 ? "is-up" : "is-down");
  });

  const caption = state.month === "all"
    ? `${rangeLabel()} · datos al ${formatCutoff(state.data.page.cutoff)}.`
    : `${monthLabel(state.month)} · datos al ${formatCutoff(state.data.page.cutoff)}.`;
  document.querySelector("#period-caption").textContent = caption;
}

function renderTrendChart() {
  if (typeof Chart === "undefined") {
    document.querySelector("#chart-note").textContent = "No se pudo cargar el gráfico.";
    return;
  }

  const metric = state.metric;
  let labels = [];
  let values = [];

  if (state.granularity === "monthly") {
    const monthly = state.data.results.monthly;
    labels = monthly.map((row) => monthMeta(row.month).short);
    values = monthly.map((row) => row[metric]);
  } else {
    const rows = state.data.results.daily.filter((row) => state.month === "all" || row.date.startsWith(state.month));
    labels = rows.map((row) => formatDateShort(row.date));
    values = rows.map((row) => row[metric]);
  }

  const dataset = {
    label: METRIC_LABELS[metric],
    data: values,
    borderColor: "#c62828",
    backgroundColor: "rgba(198, 40, 40, 0.12)",
    borderWidth: 2,
    pointRadius: state.granularity === "monthly" ? 4 : 0,
    pointHoverRadius: 4,
    pointBackgroundColor: "#c62828",
    fill: true,
    tension: 0.32,
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#1c1c1c",
        padding: 10,
        displayColors: false,
        callbacks: {
          label: (context) => `${METRIC_LABELS[metric]}: ${NUMBER.format(context.parsed.y)}`,
        },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        border: { display: false },
        ticks: { maxTicksLimit: 8, autoSkip: true, maxRotation: 0, color: "#5f5f5f" },
      },
      y: {
        beginAtZero: true,
        grid: { color: "rgba(28, 28, 28, 0.07)" },
        border: { display: false },
        ticks: { precision: 0, callback: (value) => NUMBER.format(value), color: "#5f5f5f" },
      },
    },
  };

  if (state.trendChart) {
    state.trendChart.data.labels = labels;
    state.trendChart.data.datasets[0] = dataset;
    state.trendChart.options = options;
    state.trendChart.update();
  } else {
    state.trendChart = new Chart(document.querySelector("#trend-chart"), {
      type: "line",
      data: { labels, datasets: [dataset] },
      options,
    });
  }

  const scope = state.granularity === "monthly"
    ? rangeLabel()
    : state.month === "all" ? "Todo el período" : monthLabel(state.month);
  document.querySelector("#chart-note").textContent = `${scope} · serie ${state.granularity === "daily" ? "diaria" : "mensual"} · Fuente: Meta Graph API.`;
}

function metricBlock(label, value) {
  return `<div class="metric"><div class="metric-label">${escapeHtml(label)}</div><div class="metric-value">${escapeHtml(value)}</div></div>`;
}

function detailBlock(label, value) {
  return `<div class="metric"><div class="metric-label">${escapeHtml(label)}</div><div class="metric-value">${escapeHtml(value)}</div></div>`;
}

function detailItems(post) {
  const metrics = post.metrics;
  const items = [
    ["Clics en foto", number(metrics.photoClicks)],
    ["Otros clics", number(metrics.otherClicks)],
    ["Segundos vistos", number(metrics.secondsViewed)],
    ["Promedio s", decimal(metrics.averageSecondsViewed)],
  ];
  if (post.isVideo) {
    items.push(
      ["3-sec views", number(metrics.threeSecondViews)],
      ["1-min views", number(metrics.oneMinuteViews)],
      ["3-sec viewers", number(metrics.threeSecondViewers)],
      ["1-min viewers", number(metrics.oneMinuteViewers)],
      ["Duración", formatDuration(metrics.duration)]
    );
  }
  return items;
}

function postCard(post) {
  const isExpanded = state.expanded.has(post.id);
  const caption = post.caption
    ? `<p class="post-caption">${escapeHtml(post.caption)}</p>`
    : `<p class="post-caption is-empty">Video publicado el ${escapeHtml(formatDate(post.date))}.</p>`;
  const media = post.image
    ? `<img src="${escapeHtml(post.image)}" alt="Publicación del ${escapeHtml(formatDate(post.date))}" loading="lazy" width="640" height="800">`
    : `<div class="post-placeholder"><div><strong>${post.isVideo ? "Video sin captura" : "Publicación sin captura"}</strong><span>${post.isVideo ? "Métricas de reproducción disponibles" : "Métricas de la publicación disponibles"}</span></div></div>`;
  const link = post.permalink
    ? `<a class="post-link" href="${escapeHtml(post.permalink)}" target="_blank" rel="noopener">Ver publicación ↗</a>`
    : "";
  const audienceValue = post.metrics.reach != null ? post.metrics.reach : post.metrics.viewers;
  const metrics = [
    ["Views", number(post.metrics.views)],
    [post.metrics.reach != null ? "Alcance" : "Viewers", number(audienceValue)],
    ["Interacciones", number(post.metrics.interactions)],
    ["Engagement", percent(post.engagementRate)],
    ["Reacciones", number(post.metrics.reactions)],
    ["Comentarios", number(post.metrics.comments)],
    ["Compartidos", number(post.metrics.shares)],
    ["Clics totales", number(post.metrics.totalClicks)],
    ["Clics enlace", number(post.metrics.linkClicks)],
  ].map(([label, value]) => metricBlock(label, value)).join("");

  const detail = detailItems(post).map(([label, value]) => detailBlock(label, value)).join("");

  return `
    <article class="post-card">
      <div class="post-media">${media}</div>
      <div class="post-body">
        <div class="post-meta">
          <span class="pill">${escapeHtml(typeLabel(post.type))}</span>
          <time datetime="${escapeHtml(post.date)}">${escapeHtml(formatDate(post.date))}</time>
        </div>
        ${caption}
        ${link}
        <div class="metrics-grid">${metrics}</div>
        <button type="button" class="detail-toggle" data-toggle="${escapeHtml(post.id)}" aria-expanded="${isExpanded}">
          ${isExpanded ? "Ocultar detalle" : "Ver detalle completo"}
        </button>
        <div class="post-detail"${isExpanded ? "" : " hidden"}>${detail}</div>
      </div>
    </article>
  `;
}

function filteredPosts() {
  const query = state.query.trim().toLowerCase();
  const posts = state.data.posts.filter((post) => {
    if (state.month !== "all" && post.month !== state.month) return false;
    if (state.videosOnly && !post.isVideo) return false;
    if (query && !`${post.caption} ${post.type}`.toLowerCase().includes(query)) return false;
    return true;
  });

  const audienceValue = (post) => post.metrics.reach ?? post.metrics.viewers ?? -1;
  const sorters = {
    date: (a, b) => b.date.localeCompare(a.date),
    reach: (a, b) => audienceValue(b) - audienceValue(a),
    views: (a, b) => (b.metrics.views || -1) - (a.metrics.views || -1),
    interactions: (a, b) => (b.metrics.interactions || -1) - (a.metrics.interactions || -1),
    engagement: (a, b) => (b.engagementRate || -1) - (a.engagementRate || -1),
  };
  return posts.sort(sorters[state.sort] || sorters.date);
}

function renderPosts() {
  const posts = filteredPosts();
  const grid = document.querySelector("#posts-grid");
  const empty = document.querySelector("#posts-empty");
  grid.innerHTML = posts.map(postCard).join("");
  empty.hidden = posts.length > 0;
}

function renderAudience() {
  if (typeof Chart === "undefined") return;
  const audience = state.data.audience || {};
  const ageGender = audience.ageGender || [];
  const cities = audience.cities || [];
  const countries = audience.countries || [];

  const showEmpty = (selector, text) => {
    const canvas = document.querySelector(selector);
    if (!canvas) return;
    canvas.parentElement.innerHTML = `<p class="note">${escapeHtml(text)}</p>`;
  };

  if (!ageGender.length) {
    showEmpty("#audience-gender", "Meta no devuelve el desglose por género vía API.");
    showEmpty("#audience-age", "Meta no devuelve el desglose por edad vía API.");
  } else {
    const men = ageGender.reduce((sum, row) => sum + row.men, 0);
    const women = ageGender.reduce((sum, row) => sum + row.women, 0);

    new Chart(document.querySelector("#audience-gender"), {
      type: "doughnut",
      data: {
        labels: ["Hombres", "Mujeres"],
        datasets: [{
          data: [men, women],
          backgroundColor: ["#c62828", "#1c1c1c"],
          borderColor: "#ffffff",
          borderWidth: 3,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "62%",
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true } },
          tooltip: {
            callbacks: {
              label: (context) => `${context.label}: ${DECIMAL.format(context.parsed)}%`,
            },
          },
        },
      },
    });

    new Chart(document.querySelector("#audience-age"), {
      type: "bar",
      data: {
        labels: ageGender.map((row) => row.age),
        datasets: [
          { label: "Hombres", data: ageGender.map((row) => row.men), backgroundColor: "#c62828", borderRadius: 4 },
          { label: "Mujeres", data: ageGender.map((row) => row.women), backgroundColor: "#1c1c1c", borderRadius: 4 },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true } },
          tooltip: {
            callbacks: {
              label: (context) => `${context.dataset.label}: ${DECIMAL.format(context.parsed.y)}%`,
            },
          },
        },
        scales: {
          x: { grid: { display: false }, border: { display: false } },
          y: {
            beginAtZero: true,
            grid: { color: "rgba(28, 28, 28, 0.07)" },
            border: { display: false },
            ticks: { callback: (value) => `${value}%` },
          },
        },
      },
    });
  }

  const horizontal = (selector, rows, color) => {
    new Chart(document.querySelector(selector), {
      type: "bar",
      data: {
        labels: rows.map((row) => row.name),
        datasets: [{ data: rows.map((row) => row.pct), backgroundColor: color, borderRadius: 4 }],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: { label: (context) => `${DECIMAL.format(context.parsed.x)}%` },
          },
        },
        scales: {
          x: {
            beginAtZero: true,
            grid: { color: "rgba(28, 28, 28, 0.07)" },
            border: { display: false },
            ticks: { callback: (value) => `${value}%` },
          },
          y: {
            grid: { display: false },
            border: { display: false },
            ticks: { autoSkip: false, font: { size: 11 } },
          },
        },
      },
    });
  };

  if (cities.length) horizontal("#audience-cities", cities, "#c62828");
  else showEmpty("#audience-cities", "Meta no devuelve ciudades de la audiencia vía API.");
  if (countries.length) horizontal("#audience-countries", countries, "#1c1c1c");
  else showEmpty("#audience-countries", "Meta no devuelve países de la audiencia vía API.");
}

function bindEvents() {
  document.querySelector("#period-select").addEventListener("change", (event) => {
    state.month = event.target.value;
    renderKPIs();
    renderTrendChart();
    renderPosts();
  });

  document.querySelector("#metric-chips").addEventListener("click", (event) => {
    const button = event.target.closest("[data-metric]");
    if (!button) return;
    state.metric = button.dataset.metric;
    document.querySelectorAll("#metric-chips .chip").forEach((chip) => {
      chip.classList.toggle("is-active", chip === button);
    });
    renderTrendChart();
  });

  document.querySelector("#granularity-toggle").addEventListener("click", (event) => {
    const button = event.target.closest("[data-granularity]");
    if (!button) return;
    state.granularity = button.dataset.granularity;
    document.querySelectorAll("#granularity-toggle button").forEach((item) => {
      item.classList.toggle("is-active", item === button);
    });
    renderTrendChart();
  });

  document.querySelector("#post-search").addEventListener("input", (event) => {
    state.query = event.target.value;
    renderPosts();
  });

  document.querySelector("#post-sort").addEventListener("change", (event) => {
    state.sort = event.target.value;
    renderPosts();
  });

  document.querySelector("#videos-only").addEventListener("change", (event) => {
    state.videosOnly = event.target.checked;
    renderPosts();
  });

  document.querySelector("#posts-grid").addEventListener("click", (event) => {
    const button = event.target.closest("[data-toggle]");
    if (!button) return;
    const id = button.dataset.toggle;
    const detail = button.nextElementSibling;
    const expanded = !state.expanded.has(id);
    if (expanded) {
      state.expanded.add(id);
    } else {
      state.expanded.delete(id);
    }
    button.setAttribute("aria-expanded", String(expanded));
    button.textContent = expanded ? "Ocultar detalle" : "Ver detalle completo";
    detail.hidden = !expanded;
  });
}

async function init() {
  try {
    const response = await fetch("data.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    if (typeof Chart !== "undefined") {
      Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
      Chart.defaults.color = "#5f5f5f";
    }
    setupHeader();
    bindEvents();
    renderKPIs();
    renderTrendChart();
    renderPosts();
    renderAudience();
  } catch (error) {
    document.querySelector("#period-caption").textContent = "No se pudieron cargar los datos. Verifica que data.json exista y abre el sitio desde un servidor local o GitHub Pages.";
    document.querySelector("#posts-empty").hidden = false;
    document.querySelector("#posts-empty").textContent = "No se pudieron cargar las publicaciones.";
    console.error(error);
  }
}

init();

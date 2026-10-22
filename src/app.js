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
  pdfBusy: false,
  range: { start: "", end: "" },
};

const NUMBER = new Intl.NumberFormat("es-PE", { maximumFractionDigits: 0 });
const DECIMAL = new Intl.NumberFormat("es-PE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const DATE_SHORT = new Intl.DateTimeFormat("es-PE", { day: "numeric", month: "short" });
const DATE_MED = new Intl.DateTimeFormat("es-PE", { day: "numeric", month: "short", year: "numeric" });
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

function formatDateMed(iso) {
  return DATE_MED.format(parseDate(iso));
}

function shiftDate(iso, days) {
  const value = parseDate(iso);
  value.setDate(value.getDate() + days);
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}

function dataRange() {
  const daily = state.data.results.daily;
  return {
    start: daily.length ? daily[0].date : "",
    end: daily.length ? daily[daily.length - 1].date : "",
  };
}

function daysInRange(start, end) {
  const first = parseDate(start);
  const last = parseDate(end);
  return Math.round((last - first) / 86400000) + 1;
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
  if (state.month === "custom") {
    return `${formatDate(state.range.start)} – ${formatDate(state.range.end)}`;
  }
  const months = state.data.months;
  if (!months.length) return "";
  return months.length === 1 ? months[0].label : `${months[0].label} – ${months[months.length - 1].label}`;
}

function selectedDailyRows() {
  const rows = state.data.results.daily;
  if (state.month === "custom") {
    return rows.filter((row) => row.date >= state.range.start && row.date <= state.range.end);
  }
  if (state.month === "all") return rows;
  return rows.filter((row) => row.date.startsWith(state.month));
}

function currentTotals() {
  return selectedDailyRows().reduce((acc, row) => {
    acc.views += row.views;
    acc.viewers += row.viewers;
    acc.visits += row.visits;
    acc.follows += row.follows;
    return acc;
  }, { views: 0, viewers: 0, visits: 0, follows: 0 });
}

function previousTotals() {
  if (state.month === "custom") return null;
  const index = state.data.months.findIndex((month) => month.key === state.month);
  if (index <= 0) return null;
  return state.data.results.monthly[index - 1];
}

function monthlyRows() {
  const grouped = {};
  for (const row of selectedDailyRows()) {
    const key = row.date.slice(0, 7);
    if (!grouped[key]) {
      grouped[key] = { month: key, views: 0, viewers: 0, visits: 0, follows: 0 };
    }
    for (const metric of ["views", "viewers", "visits", "follows"]) {
      grouped[key][metric] += row[metric];
    }
  }
  return state.data.months
    .filter((meta) => grouped[meta.key])
    .map((meta) => grouped[meta.key]);
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
  const options = [{ key: "all", label: "Todo el período" }]
    .concat(state.data.months.map((month) => ({ key: month.key, label: monthLabel(month.key) })))
    .concat([{ key: "custom", label: "Rango personalizado" }]);
  select.innerHTML = options
    .map((option) => `<option value="${escapeHtml(option.key)}">${escapeHtml(option.label)}</option>`)
    .join("");
  select.value = state.month;
  setupCustomRange();
}

function setupCustomRange() {
  const limits = dataRange();
  const startInput = document.querySelector("#range-start");
  const endInput = document.querySelector("#range-end");
  startInput.min = limits.start;
  startInput.max = limits.end;
  endInput.min = limits.start;
  endInput.max = limits.end;
  if (!state.range.start || !state.range.end) {
    state.range = { start: limits.start, end: limits.end };
  }
  startInput.value = state.range.start;
  endInput.value = state.range.end;
  toggleCustomRange();
}

function toggleCustomRange() {
  const isCustom = state.month === "custom";
  const box = document.querySelector("#custom-range");
  box.hidden = !isCustom;
  if (!isCustom) document.querySelector("#range-error").textContent = "";
}

function syncRangeUrl() {
  const url = new URL(window.location.href);
  if (state.month === "custom") {
    url.searchParams.set("from", state.range.start);
    url.searchParams.set("to", state.range.end);
  } else {
    url.searchParams.delete("from");
    url.searchParams.delete("to");
  }
  window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
}

function applyRangeInputs() {
  const start = document.querySelector("#range-start").value;
  const end = document.querySelector("#range-end").value;
  const error = document.querySelector("#range-error");
  const limits = dataRange();
  if (!start || !end) {
    error.textContent = "Selecciona ambas fechas.";
    return;
  }
  if (start < limits.start || end > limits.end) {
    error.textContent = `Disponible del ${formatDateMed(limits.start)} al ${formatDateMed(limits.end)}.`;
    return;
  }
  if (start > end) {
    error.textContent = "La fecha inicial no puede ser posterior a la final.";
    return;
  }
  state.range = { start, end };
  error.textContent = "";
  syncRangeUrl();
  renderKPIs();
  renderTrendChart();
  renderPosts();
}

function applyRangeFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const start = params.get("from");
  const end = params.get("to");
  if (!start || !end) return;
  const limits = dataRange();
  if (start < limits.start || end > limits.end || start > end) return;
  state.month = "custom";
  state.range = { start, end };
}

function renderKPIs() {
  const totals = currentTotals();
  const previous = previousTotals();
  const activeMonth = state.month === "all" || state.month === "custom" ? null : monthMeta(state.month);
  const isPartial = Boolean(activeMonth && activeMonth.partial);

  ["views", "viewers", "visits", "follows"].forEach((key) => {
    document.querySelector(`#kpi-${key}`).textContent = number(totals[key]);
    const delta = document.querySelector(`#delta-${key}`);
    delta.className = "kpi-delta";
    delta.textContent = "";

    if (state.month === "custom") {
      delta.textContent = `${NUMBER.format(daysInRange(state.range.start, state.range.end))} días del rango`;
      return;
    }
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

  const caption = state.month === "all" || state.month === "custom"
    ? `${rangeLabel()} · datos al ${formatCutoff(state.data.page.cutoff)}.`
    : `${monthLabel(state.month)} · datos al ${formatCutoff(state.data.page.cutoff)}.`;
  document.querySelector("#period-caption").textContent = caption;
  updatePdfButton();
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
    const monthly = monthlyRows();
    labels = monthly.map((row) => monthMeta(row.month).short);
    values = monthly.map((row) => row[metric]);
  } else {
    const rows = selectedDailyRows();
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

  const scope = state.month === "custom"
    ? rangeLabel()
    : state.granularity === "monthly"
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

const RANGE_ADDITIVE_KEYS = [
  "views",
  "interactions",
  "reactions",
  "comments",
  "shares",
  "totalClicks",
  "linkClicks",
  "otherClicks",
  "photoClicks",
  "secondsViewed",
  "threeSecondViews",
  "oneMinuteViews",
];

const ALL_METRIC_KEYS = RANGE_ADDITIVE_KEYS.concat([
  "viewers",
  "reach",
  "threeSecondViewers",
  "oneMinuteViewers",
  "duration",
  "averageSecondsViewed",
]);

function snapshotMetrics(postId, day) {
  const snapshots = (state.data.postHistory || {})[postId] || [];
  const snapshot = snapshots.find((item) => item.date === day);
  return snapshot ? snapshot.metrics || {} : null;
}

function emptyMetrics() {
  return ALL_METRIC_KEYS.reduce((acc, key) => {
    acc[key] = null;
    return acc;
  }, {});
}

function postRangeMetrics(post) {
  if (state.month !== "custom") return null;
  const { start, end } = state.range;
  if (!start || !end || post.date < start || post.date > end) return null;

  const endMetrics = snapshotMetrics(post.id, end);
  if (!endMetrics) return null;

  const hasBase = post.date < start;
  const baseMetrics = hasBase ? snapshotMetrics(post.id, shiftDate(start, -1)) : {};
  if (hasBase && !baseMetrics) return null;

  const metrics = emptyMetrics();
  for (const key of RANGE_ADDITIVE_KEYS) {
    const current = endMetrics[key];
    const base = hasBase ? baseMetrics[key] : 0;
    if (current == null || (hasBase && base == null)) continue;
    metrics[key] = Math.max(0, current - (base || 0));
  }

  metrics.duration = endMetrics.duration ?? null;
  const watched = metrics.secondsViewed;
  if (watched != null && metrics.views > 0) {
    metrics.averageSecondsViewed = watched / metrics.views;
  } else {
    metrics.averageSecondsViewed = endMetrics.averageSecondsViewed ?? null;
  }

  if (!Object.values(metrics).some((value) => value != null)) return null;
  const denominator = metrics.reach ?? metrics.views;
  const engagementRate = denominator > 0 && metrics.interactions != null
    ? (metrics.interactions / denominator) * 100
    : null;
  return { metrics, engagementRate };
}

function detailItems(post, metrics = post.metrics) {
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
  const rangeMode = state.month === "custom";
  const range = rangeMode ? postRangeMetrics(post) : null;
  const metricsValues = range ? range.metrics : post.metrics;
  const engagementRate = range ? range.engagementRate : post.engagementRate;
  const showMetrics = !rangeMode || Boolean(range);
  const caption = post.caption
    ? `<p class="post-caption">${escapeHtml(post.caption)}</p>`
    : `<p class="post-caption is-empty">Video publicado el ${escapeHtml(formatDate(post.date))}.</p>`;
  const placeholderDetail = showMetrics
    ? post.isVideo ? "Métricas de reproducción disponibles" : "Métricas de la publicación disponibles"
    : "Disponible en la publicación original";
  const media = post.image
    ? `<img src="${escapeHtml(post.image)}" alt="Publicación del ${escapeHtml(formatDate(post.date))}" loading="lazy" width="640" height="800">`
    : `<div class="post-placeholder"><div><strong>${post.isVideo ? "Video sin captura" : "Publicación sin captura"}</strong><span>${placeholderDetail}</span></div></div>`;
  const link = post.permalink
    ? `<a class="post-link" href="${escapeHtml(post.permalink)}" target="_blank" rel="noopener">Ver publicación ↗</a>`
    : "";
  const audienceValue = metricsValues.reach != null ? metricsValues.reach : metricsValues.viewers;
  const metrics = [
    ["Views", number(metricsValues.views)],
    [metricsValues.reach != null ? "Alcance" : "Viewers", number(audienceValue)],
    ["Interacciones", number(metricsValues.interactions)],
    ["Engagement", percent(engagementRate)],
    ["Reacciones", number(metricsValues.reactions)],
    ["Comentarios", number(metricsValues.comments)],
    ["Compartidos", number(metricsValues.shares)],
    ["Clics totales", number(metricsValues.totalClicks)],
    ["Clics enlace", number(metricsValues.linkClicks)],
  ].map(([label, value]) => metricBlock(label, value)).join("");

  const missingNote = rangeMode && !range
    ? `<p class="post-range-note">Métricas por publicación no disponibles para este rango.</p>`
    : "";
  const detail = showMetrics
    ? detailItems(post, metricsValues).map(([label, value]) => detailBlock(label, value)).join("")
    : "";
  const detailControl = showMetrics
    ? `<button type="button" class="detail-toggle" data-toggle="${escapeHtml(post.id)}" aria-expanded="${isExpanded}">
          ${isExpanded ? "Ocultar detalle" : "Ver detalle completo"}
        </button>
        <div class="post-detail"${isExpanded ? "" : " hidden"}>${detail}</div>`
    : "";

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
        ${showMetrics ? `<div class="metrics-grid">${metrics}</div>` : missingNote}
        ${detailControl}
      </div>
    </article>
  `;
}

function filteredPosts() {
  const query = state.query.trim().toLowerCase();
  const posts = state.data.posts.filter((post) => {
    if (state.month === "custom") {
      if (post.date < state.range.start || post.date > state.range.end) return false;
    } else if (state.month !== "all" && post.month !== state.month) {
      return false;
    }
    if (state.videosOnly && !post.isVideo) return false;
    if (query && !`${post.caption} ${post.type}`.toLowerCase().includes(query)) return false;
    return true;
  });

  const metricsFor = (post) => state.month === "custom"
    ? postRangeMetrics(post)?.metrics || {}
    : post.metrics;
  const engagementFor = (post) => state.month === "custom"
    ? postRangeMetrics(post)?.engagementRate ?? -1
    : post.engagementRate ?? -1;
  const audienceValue = (post) => metricsFor(post).reach ?? metricsFor(post).viewers ?? -1;
  const sorters = {
    date: (a, b) => b.date.localeCompare(a.date),
    reach: (a, b) => audienceValue(b) - audienceValue(a),
    views: (a, b) => (metricsFor(b).views ?? -1) - (metricsFor(a).views ?? -1),
    interactions: (a, b) => (metricsFor(b).interactions ?? -1) - (metricsFor(a).interactions ?? -1),
    engagement: (a, b) => engagementFor(b) - engagementFor(a),
  };
  return posts.sort(sorters[state.sort] || sorters.date);
}

function renderPosts() {
  const posts = filteredPosts();
  const grid = document.querySelector("#posts-grid");
  const empty = document.querySelector("#posts-empty");
  const subtitle = document.querySelector("#posts-subtitle");
  const note = document.querySelector("#posts-range-note");
  const isCustom = state.month === "custom";
  const hasRangeMetrics = isCustom && posts.some((post) => postRangeMetrics(post));

  subtitle.textContent = isCustom
    ? "Publicaciones del rango seleccionado."
    : "Rendimiento acumulado de cada publicación al cierre del período.";
  if (!isCustom || !posts.length) {
    note.hidden = true;
    note.textContent = "";
  } else if (hasRangeMetrics) {
    note.hidden = false;
    note.textContent = state.data.postHistoryStart
      ? `Métricas calculadas con los snapshots diarios. Historial desde el ${formatDateMed(state.data.postHistoryStart)}. Viewers y alcance únicos no están disponibles por rango.`
      : "Métricas calculadas con los snapshots diarios. Viewers y alcance únicos no están disponibles por rango.";
  } else {
    note.hidden = false;
    note.textContent = state.data.postHistoryStart
      ? `Métricas por publicación no disponibles para este rango. El historial comienza el ${formatDateMed(state.data.postHistoryStart)}.`
      : "Métricas por publicación no disponibles para rangos históricos. Se guardarán a partir del primer snapshot diario.";
  }

  grid.innerHTML = posts.map(postCard).join("");
  empty.hidden = posts.length > 0;
}

function renderAudience() {
  if (typeof Chart === "undefined") return;
  const audience = state.data.audience || {};
  const ageGender = audience.ageGender || [];
  const cities = audience.cities || [];
  const countries = audience.countries || [];
  const note = document.querySelector("#audience-note");
  if (note) {
    note.textContent = audience.source === "business-suite"
      ? "Datos demográficos del export de Meta Business Suite. El resto de métricas proviene de la API."
      : audience.source === "api"
        ? "Datos demográficos de Meta Graph API."
        : "No hay datos demográficos disponibles. Exporta la audiencia desde Meta Business Suite y reemplaza data/audience.csv.";
  }

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
    const audienceTotal = men + women;
    const menPct = audienceTotal > 0 ? (men / audienceTotal) * 100 : 0;
    const womenPct = audienceTotal > 0 ? (women / audienceTotal) * 100 : 0;

    new Chart(document.querySelector("#audience-gender"), {
      type: "doughnut",
      data: {
        labels: ["Hombres", "Mujeres"],
        datasets: [{
          data: [menPct, womenPct],
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

const PDF_METRIC_KEYS = ["views", "viewers", "visits", "follows"];
const PDF_POSTS_PER_PAGE = 4;

function updatePdfButton() {
  const button = document.querySelector("#download-pdf");
  if (!button) return;
  const isMonth = state.month !== "all" && state.month !== "custom" && Boolean(monthMeta(state.month));
  button.disabled = state.pdfBusy || !isMonth;
  button.textContent = state.pdfBusy ? "Generando PDF…" : "Descargar PDF";
  button.title = isMonth
    ? `Descargar reporte de ${monthMeta(state.month).label}`
    : "Selecciona un mes para descargar el PDF";
  button.setAttribute("aria-busy", String(state.pdfBusy));
}

function pdfMonthlyRow(monthKey) {
  return state.data.results.monthly.find((row) => row.month === monthKey) || null;
}

function pdfPreviousMonthlyRow(monthKey) {
  const index = state.data.months.findIndex((month) => month.key === monthKey);
  if (index <= 0) return null;
  return pdfMonthlyRow(state.data.months[index - 1].key);
}

function pdfSumRows(rows) {
  return rows.reduce((acc, row) => {
    for (const key of PDF_METRIC_KEYS) acc[key] += row[key] || 0;
    return acc;
  }, { views: 0, viewers: 0, visits: 0, follows: 0 });
}

function pdfDelta(row, previous, key, isPartial) {
  if (!previous) return { text: "Sin mes anterior comparable", className: "" };
  if (!previous[key]) return { text: "Sin base de comparación", className: "" };
  const change = ((row[key] - previous[key]) / previous[key]) * 100;
  const sign = change > 0 ? "+" : "";
  return {
    text: `${sign}${decimal(change)}% vs. ${monthMeta(previous.month).short}${isPartial ? " · mes en curso" : ""}`,
    className: change >= 0 ? "is-up" : "is-down",
  };
}

function pdfGrowthNarrative(row, previous, isPartial) {
  if (!previous) return "No hay un mes anterior comparable para calcular variaciones.";
  const changes = PDF_METRIC_KEYS
    .filter((key) => previous[key] > 0)
    .map((key) => ({ key, pct: ((row[key] - previous[key]) / previous[key]) * 100 }));
  if (!changes.length) return "No hay base suficiente para calcular variaciones.";

  const sorted = [...changes].sort((a, b) => b.pct - a.pct);
  const best = sorted[0];
  const worst = sorted[sorted.length - 1];
  const parts = [];

  if (best.pct > 0) {
    parts.push(`El mayor avance fue ${METRIC_LABELS[best.key]} (+${decimal(best.pct)}%).`);
  } else {
    parts.push(`Ninguna métrica creció frente a ${monthMeta(previous.month).label}.`);
  }
  if (worst.pct < 0) {
    parts.push(`La mayor caída fue ${METRIC_LABELS[worst.key]} (${decimal(worst.pct)}%).`);
  } else {
    parts.push("No hubo caídas entre las métricas comparables.");
  }
  if (isPartial) parts.push("El mes está en curso; la comparación es preliminar.");
  return parts.join(" ");
}

function pdfPage(content, { className = "", showHead = true } = {}) {
  const meta = monthMeta(state.month);
  const head = showHead
    ? `<div class="pdf-page-head"><span>Ferre Experto · Reporte mensual</span><span>${escapeHtml(meta ? meta.label : "")}</span></div>`
    : "";
  return `<section class="pdf-page ${className}">
    ${head}
    ${content}
    <div class="pdf-page-footer">
      <span>Ferre Experto Pacasmayo · Datos al ${escapeHtml(formatCutoff(state.data.page.cutoff))}</span>
      <span class="pdf-page-number"></span>
    </div>
  </section>`;
}

function pdfStatStrip(items, className = "") {
  return `<div class="pdf-stat-strip ${className}">${items.map(([label, value]) => `
    <div class="pdf-stat">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `).join("")}</div>`;
}

function pdfPostSummary(posts) {
  const views = posts.reduce((sum, post) => sum + (post.metrics?.views || 0), 0);
  const interactions = posts.reduce((sum, post) => sum + (post.metrics?.interactions || 0), 0);
  const engagement = posts
    .map((post) => post.engagementRate)
    .filter((value) => Number.isFinite(value));
  const averageEngagement = engagement.length
    ? engagement.reduce((sum, value) => sum + value, 0) / engagement.length
    : null;

  return pdfStatStrip([
    ["Publicaciones", number(posts.length)],
    ["Views totales", number(views)],
    ["Interacciones", number(interactions)],
    ["Engagement promedio", averageEngagement == null ? "—" : percent(averageEngagement)],
  ], "is-posts");
}

function pdfEvolutionSummary(rows, row) {
  const peak = rows.reduce((best, current) => (!best || current.views > best.views ? current : best), null);
  const average = rows.length ? row.views / rows.length : 0;
  return pdfStatStrip([
    ["Día con más views", peak ? `${formatDateShort(peak.date)} · ${number(peak.views)}` : "—"],
    ["Promedio diario", number(average)],
    ["Días con datos", number(rows.length)],
    ["Follows netos", number(row.follows)],
  ], "is-evolution");
}

function pdfAudienceSource(source) {
  if (source === "business-suite") return "Business Suite";
  if (source === "api") return "Graph API";
  return "Sin datos";
}

function pdfSummaryPage(row, previous, meta, daily, posts) {
  const isPartial = Boolean(meta.partial);
  const kpis = PDF_METRIC_KEYS.map((key) => {
    const delta = pdfDelta(row, previous, key, isPartial);
    return `<article class="pdf-kpi">
      <p class="pdf-kpi-label">${escapeHtml(METRIC_LABELS[key])}</p>
      <p class="pdf-kpi-value">${escapeHtml(number(row[key]))}</p>
      <p class="pdf-kpi-delta ${delta.className}">${escapeHtml(delta.text)}</p>
    </article>`;
  }).join("");

  return pdfPage(`
    <div class="pdf-cover-hero">
      <div class="pdf-cover-brand">
        <img src="logo-full.png?v=20261022b" alt="Pandora Marketing con Propósito">
        <span>Ferre Experto Pacasmayo</span>
      </div>
      <p class="pdf-eyebrow">Reporte mensual</p>
      <h1>${escapeHtml(meta.label)}${isPartial ? " <span class=\"pdf-status-badge\">Mes en curso</span>" : ""}</h1>
      <p class="pdf-cover-sub">Resumen ejecutivo · Datos al ${escapeHtml(formatCutoff(state.data.page.cutoff))}</p>
    </div>
    <div class="pdf-summary-body">
      <div class="pdf-summary-topline">
        <p class="pdf-section-kicker">Crecimiento del período</p>
        <p class="pdf-section-note">${previous ? `Comparado con ${escapeHtml(monthMeta(previous.month).label)}` : "Sin mes anterior comparable"}</p>
      </div>
      <div class="pdf-kpi-grid">${kpis}</div>
      <div class="pdf-growth-box">
        <h2>Lectura del período</h2>
        <p>${escapeHtml(pdfGrowthNarrative(row, previous, isPartial))}</p>
      </div>
      ${pdfStatStrip([
        ["Publicaciones", number(posts.length)],
        ["Seguidores al corte", number(state.data.page.followers)],
        ["Días con datos", number(daily.length)],
        ["Corte", formatCutoff(state.data.page.cutoff)],
      ], "is-context")}
      <div class="pdf-summary-agenda">
        <p class="pdf-section-kicker">Contenido del informe</p>
        <div class="pdf-agenda-grid">
          <div class="pdf-agenda-item"><span>01</span><div><strong>Resumen ejecutivo</strong><small>KPIs y contexto del mes</small></div></div>
          <div class="pdf-agenda-item"><span>02</span><div><strong>Evolución diaria</strong><small>Series de las cuatro métricas</small></div></div>
          <div class="pdf-agenda-item"><span>03</span><div><strong>Publicaciones</strong><small>Fichas y lectura del contenido</small></div></div>
          <div class="pdf-agenda-item"><span>04</span><div><strong>Audiencia y método</strong><small>Alcance, fuentes y notas</small></div></div>
        </div>
      </div>
      <p class="pdf-summary-meta">Actualizado ${escapeHtml(formatUpdated(state.data.page.updatedAt))} · Fuente: Meta Graph API.</p>
    </div>
  `, { className: "pdf-summary", showHead: false });
}

function pdfEvolutionPage(rows, row) {
  const cards = PDF_METRIC_KEYS.map((key) => `
    <article class="pdf-chart-card">
      <div class="pdf-chart-head">
        <h3>${escapeHtml(METRIC_LABELS[key])}</h3>
        <span>${escapeHtml(number(row[key]))}</span>
      </div>
      <div class="pdf-chart-box"><canvas id="pdf-chart-${key}" aria-label="Evolución diaria de ${escapeHtml(METRIC_LABELS[key])}"></canvas></div>
    </article>
  `).join("");

  return pdfPage(`
    <div class="pdf-section-head">
      <p class="pdf-eyebrow">Evolución diaria</p>
      <h1>Comportamiento del período</h1>
      <p class="pdf-section-note">Serie diaria de las cuatro métricas principales.</p>
    </div>
    ${rows.length ? `<div class="pdf-chart-grid">${cards}</div>` : `<p class="pdf-empty">No hay datos diarios para este mes.</p>`}
    <div class="pdf-insight-box">
      <h2>Hallazgos de la evolución</h2>
      ${pdfEvolutionSummary(rows, row)}
    </div>
  `);
}

function pdfCaption(text, limit = 300) {
  const clean = String(text || "").replace(/\s+/g, " ").trim();
  if (!clean) return "";
  if (clean.length <= limit) return clean;
  const cut = clean.slice(0, limit);
  const lastSpace = cut.lastIndexOf(" ");
  return `${cut.slice(0, lastSpace > 0 ? lastSpace : limit).trim()}…`;
}

function pdfMetricBlock(label, value) {
  return `<div class="pdf-metric"><span class="pdf-metric-label">${escapeHtml(label)}</span><span class="pdf-metric-value">${escapeHtml(value)}</span></div>`;
}

function pdfPostCard(post, captionLimit = 300) {
  const metrics = post.metrics || {};
  const audienceValue = metrics.reach != null ? metrics.reach : metrics.viewers;
  const values = [
    ["Views", number(metrics.views)],
    [metrics.reach != null ? "Alcance" : "Viewers", number(audienceValue)],
    ["Interacciones", number(metrics.interactions)],
    ["Engagement", percent(post.engagementRate)],
    ["Reacciones", number(metrics.reactions)],
    ["Comentarios", number(metrics.comments)],
    ["Compartidos", number(metrics.shares)],
    ["Clics totales", number(metrics.totalClicks)],
    ["Clics enlace", number(metrics.linkClicks)],
  ];
  const media = post.image
    ? `<img src="${escapeHtml(post.image)}" alt="Publicación del ${escapeHtml(formatDate(post.date))}">`
    : `<div class="pdf-post-placeholder"><strong>${post.isVideo ? "Video sin captura" : "Publicación sin captura"}</strong><span>Disponible en la publicación original</span></div>`;
  const caption = post.caption
    ? `<p class="pdf-post-caption">${escapeHtml(pdfCaption(post.caption, captionLimit))}</p>`
    : `<p class="pdf-post-caption is-empty">Video publicado el ${escapeHtml(formatDate(post.date))}.</p>`;

  return `<article class="pdf-post-card">
    <div class="pdf-post-media">${media}</div>
    <div class="pdf-post-body">
      <div class="pdf-post-meta">
        <span class="pdf-pill">${escapeHtml(typeLabel(post.type))}</span>
        <time datetime="${escapeHtml(post.date)}">${escapeHtml(formatDate(post.date))}</time>
      </div>
      ${caption}
      <div class="pdf-metrics-grid">${values.map(([label, value]) => pdfMetricBlock(label, value)).join("")}</div>
    </div>
  </article>`;
}

function pdfPostHighlights(posts) {
  const withViews = posts.filter((post) => Number.isFinite(post.metrics?.views));
  const topViews = [...withViews].sort((a, b) => b.metrics.views - a.metrics.views)[0];
  const withEngagement = posts.filter((post) => Number.isFinite(post.engagementRate));
  const topEngagement = [...withEngagement].sort((a, b) => b.engagementRate - a.engagementRate)[0];
  const parts = [];

  if (topViews) {
    parts.push(`La publicación con más views fue la del ${formatDateShort(topViews.date)} (${number(topViews.metrics.views)}).`);
  }
  if (topEngagement) {
    parts.push(`El mejor engagement fue el de la publicación del ${formatDateShort(topEngagement.date)} (${percent(topEngagement.engagementRate)}).`);
  }

  return `<div class="pdf-insight-box">
    <h2>Lectura de las publicaciones</h2>
    <p>${escapeHtml(parts.join(" "))}</p>
  </div>`;
}

function pdfPostsPages(posts) {
  if (!posts.length) {
    return [pdfPage(`
      <div class="pdf-section-head">
        <p class="pdf-eyebrow">Contenido</p>
        <h1>Publicaciones del mes</h1>
      </div>
      <p class="pdf-empty">No hay publicaciones para este mes.</p>
    `)];
  }

  const pages = [];
  for (let index = 0; index < posts.length; index += PDF_POSTS_PER_PAGE) {
    const chunk = posts.slice(index, index + PDF_POSTS_PER_PAGE);
    const gridClass = chunk.length === 1 ? "is-single" : chunk.length === 2 ? "is-sparse" : "is-compact";
    const captionLimit = gridClass === "is-compact" ? 160 : 300;
    const summary = index === 0 ? pdfPostSummary(posts) : "";
    const highlights = index === 0 && chunk.length <= 2 ? pdfPostHighlights(posts) : "";
    pages.push(pdfPage(`
      <div class="pdf-section-head">
        <p class="pdf-eyebrow">Contenido</p>
        <h1>${index === 0 ? "Publicaciones del mes" : "Publicaciones (continuación)"}</h1>
        <p class="pdf-section-note">${posts.length} publicaciones · todas las del mes, sin filtros de búsqueda, orden o tipo.</p>
      </div>
      ${summary}
      <div class="pdf-post-grid ${gridClass}">${chunk.map((post) => pdfPostCard(post, captionLimit)).join("")}</div>
      ${highlights}
      <p class="pdf-page-note">Métricas por publicación acumuladas hasta el corte; no corresponden solo al mes de publicación.</p>
    `));
  }
  return pages;
}

function pdfAudiencePanel(id, title, hasData, emptyText) {
  return `<article class="pdf-audience-card">
    <h3>${escapeHtml(title)}</h3>
    ${hasData ? `<div class="pdf-chart-box"><canvas id="pdf-audience-${id}" aria-label="${escapeHtml(title)}"></canvas></div>` : `<p class="pdf-empty-note">${escapeHtml(emptyText)}</p>`}
  </article>`;
}

function pdfAudiencePage() {
  const audience = state.data.audience || {};
  const ageGender = audience.ageGender || [];
  const cities = audience.cities || [];
  const countries = audience.countries || [];
  const note = audience.source === "business-suite"
    ? "Datos demográficos del export de Meta Business Suite. El resto de métricas proviene de la API."
    : audience.source === "api"
      ? "Datos demográficos de Meta Graph API."
      : "No hay datos demográficos disponibles. Exporta la audiencia desde Meta Business Suite y reemplaza data/audience.csv.";

  return pdfPage(`
    <div class="pdf-section-head">
      <p class="pdf-eyebrow">Público</p>
      <h1>Audiencia</h1>
      <p class="pdf-section-note">Seguidores del fanpage: <strong>${escapeHtml(NUMBER.format(state.data.page.followers))}</strong> al corte. La audiencia es una foto fija y no cambia con el mes.</p>
    </div>
    ${pdfStatStrip([
      ["Seguidores", number(state.data.page.followers)],
      ["Fuente demográfica", pdfAudienceSource(audience.source)],
      ["Ciudades", number(cities.length)],
      ["Países", number(countries.length)],
    ], "is-audience")}
    <div class="pdf-audience-grid">
      ${pdfAudiencePanel("gender", "Género", ageGender.length > 0, "Meta no devuelve el desglose por género vía API.")}
      ${pdfAudiencePanel("age", "Edad y género", ageGender.length > 0, "Meta no devuelve el desglose por edad vía API.")}
      ${pdfAudiencePanel("cities", "Top ciudades", cities.length > 0, "Meta no devuelve ciudades de la audiencia vía API.")}
      ${pdfAudiencePanel("countries", "Top países", countries.length > 0, "Meta no devuelve países de la audiencia vía API.")}
    </div>
    <p class="pdf-footnote">${escapeHtml(note)}</p>
  `);
}

function pdfMethodologyPage() {
  const daily = state.data.results.daily.filter((row) => row.date.startsWith(state.month));
  const posts = state.data.posts.filter((post) => post.month === state.month || post.date.startsWith(state.month));

  return pdfPage(`
    <div class="pdf-section-head">
      <p class="pdf-eyebrow">Transparencia</p>
      <h1>Metodología y notas</h1>
      <p class="pdf-section-note">Cómo leer este informe y de dónde salen los números.</p>
    </div>
    ${pdfStatStrip([
      ["Fuente", "Meta Graph API"],
      ["Corte", formatCutoff(state.data.page.cutoff)],
      ["Publicaciones", number(posts.length)],
      ["Días con datos", number(daily.length)],
    ], "is-method")}
    <div class="pdf-method-grid">
      <div class="pdf-prose">
        <h2>Definiciones</h2>
        <ul>
          <li><strong>Views:</strong> veces que se vieron las publicaciones del fanpage.</li>
          <li><strong>Viewers:</strong> personas únicas que vieron contenido.</li>
          <li><strong>Visits:</strong> visitas a la página del fanpage.</li>
          <li><strong>Follows:</strong> seguidores netos ganados en el período.</li>
          <li><strong>Viewers por publicación:</strong> personas únicas que vieron una publicación; Meta no expone alcance por publicación vía API.</li>
          <li><strong>Interacciones:</strong> reacciones + comentarios + compartidos.</li>
          <li><strong>Engagement:</strong> interacciones divididas entre alcance o, si no hay alcance, entre views. Se muestra “—” cuando no hay base comparable.</li>
        </ul>
      </div>
      <aside class="pdf-method-side">
        <div class="pdf-method-card">
          <h2>Ficha del reporte</h2>
          <dl>
            <div><dt>Mes</dt><dd>${escapeHtml(monthLabel(state.month))}</dd></div>
            <div><dt>Actualizado</dt><dd>${escapeHtml(formatUpdated(state.data.page.updatedAt))}</dd></div>
            <div><dt>Seguidores</dt><dd>${escapeHtml(number(state.data.page.followers))}</dd></div>
            <div><dt>Comparación</dt><dd>Mes anterior</dd></div>
          </dl>
        </div>
        <div class="pdf-method-card">
          <h2>Alcance</h2>
          <p>Las métricas por publicación son acumuladas (<em>lifetime</em>) hasta la fecha de corte, no solo del mes en que se publicaron.</p>
        </div>
      </aside>
    </div>
    <div class="pdf-method-notes">
      <h2>Notas</h2>
      <p>El mes en curso se marca como parcial y no se compara como un mes cerrado. Las variaciones se calculan contra el mes anterior; si el mes está en curso, la comparación es preliminar.</p>
      <p>La audiencia corresponde a los seguidores del fanpage y es una foto fija al corte; no cambia con el selector de mes. Meta dejó de exponer la demografía vía API, por lo que se usa el export de Meta Business Suite cuando está disponible.</p>
      <p>Reporte generado automáticamente desde el dashboard de Ferre Experto Pacasmayo.</p>
    </div>
    <div class="pdf-method-extra">
      <div class="pdf-method-extra-card">
        <h2>Trazabilidad</h2>
        <ul>
          <li><strong>Fanpage y publicaciones:</strong> Meta Graph API.</li>
          <li><strong>Audiencia:</strong> export de Meta Business Suite cuando está disponible.</li>
          <li><strong>Consolidación:</strong> dashboard de Ferre Experto Pacasmayo.</li>
        </ul>
      </div>
      <div class="pdf-method-extra-card">
        <h2>Criterios de lectura</h2>
        <ul>
          <li><strong>Mes cerrado:</strong> comparación completa contra el mes anterior.</li>
          <li><strong>Mes en curso:</strong> datos al corte; comparación preliminar.</li>
          <li><strong>Publicaciones:</strong> métricas acumuladas, no solo del mes.</li>
        </ul>
      </div>
    </div>
  `);
}

function pdfLineChart(canvas, rows, metric) {
  return new Chart(canvas, {
    type: "line",
    data: {
      labels: rows.map((row) => formatDateShort(row.date)),
      datasets: [{
        data: rows.map((row) => row[metric]),
        borderColor: "#c62828",
        backgroundColor: "rgba(198, 40, 40, 0.12)",
        borderWidth: 2,
        pointRadius: 0,
        fill: true,
        tension: 0.32,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: {
        x: {
          grid: { display: false },
          border: { display: false },
          ticks: { maxTicksLimit: 6, autoSkip: true, maxRotation: 0, color: "#5f5f5f", font: { size: 9 } },
        },
        y: {
          beginAtZero: true,
          grid: { color: "rgba(28, 28, 28, 0.07)" },
          border: { display: false },
          ticks: { precision: 0, color: "#5f5f5f", font: { size: 9 }, callback: (value) => NUMBER.format(value) },
        },
      },
    },
  });
}

function createPdfAudienceCharts(report) {
  if (typeof Chart === "undefined") return [];
  const charts = [];
  const audience = state.data.audience || {};
  const ageGender = audience.ageGender || [];
  const cities = audience.cities || [];
  const countries = audience.countries || [];

  if (ageGender.length) {
    const men = ageGender.reduce((sum, row) => sum + row.men, 0);
    const women = ageGender.reduce((sum, row) => sum + row.women, 0);
    const total = men + women;
    const genderCanvas = report.querySelector("#pdf-audience-gender");
    if (genderCanvas) {
      charts.push(new Chart(genderCanvas, {
        type: "doughnut",
        data: {
          labels: ["Hombres", "Mujeres"],
          datasets: [{
            data: [total > 0 ? (men / total) * 100 : 0, total > 0 ? (women / total) * 100 : 0],
            backgroundColor: ["#c62828", "#1c1c1c"],
            borderColor: "#ffffff",
            borderWidth: 3,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          cutout: "62%",
          plugins: {
            legend: { position: "bottom", labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, font: { size: 9 } } },
            tooltip: { enabled: false },
          },
        },
      }));
    }

    const ageCanvas = report.querySelector("#pdf-audience-age");
    if (ageCanvas) {
      charts.push(new Chart(ageCanvas, {
        type: "bar",
        data: {
          labels: ageGender.map((row) => row.age),
          datasets: [
            { label: "Hombres", data: ageGender.map((row) => row.men), backgroundColor: "#c62828", borderRadius: 3 },
            { label: "Mujeres", data: ageGender.map((row) => row.women), backgroundColor: "#1c1c1c", borderRadius: 3 },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          plugins: {
            legend: { position: "bottom", labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, font: { size: 9 } } },
            tooltip: { enabled: false },
          },
          scales: {
            x: { grid: { display: false }, border: { display: false }, ticks: { font: { size: 8 } } },
            y: {
              beginAtZero: true,
              grid: { color: "rgba(28, 28, 28, 0.07)" },
              border: { display: false },
              ticks: { callback: (value) => `${value}%`, font: { size: 8 } },
            },
          },
        },
      }));
    }
  }

  const horizontal = (id, rows, color) => {
    const canvas = report.querySelector(`#pdf-audience-${id}`);
    if (!canvas) return;
    charts.push(new Chart(canvas, {
      type: "bar",
      data: {
        labels: rows.map((row) => row.name),
        datasets: [{ data: rows.map((row) => row.pct), backgroundColor: color, borderRadius: 3 }],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        scales: {
          x: {
            beginAtZero: true,
            grid: { color: "rgba(28, 28, 28, 0.07)" },
            border: { display: false },
            ticks: { callback: (value) => `${value}%`, font: { size: 8 } },
          },
          y: { grid: { display: false }, border: { display: false }, ticks: { autoSkip: false, font: { size: 8 } } },
        },
      },
    }));
  };

  horizontal("cities", cities, "#c62828");
  horizontal("countries", countries, "#1c1c1c");
  return charts;
}

function buildPdfReport(monthKey) {
  const meta = monthMeta(monthKey);
  const daily = state.data.results.daily.filter((row) => row.date.startsWith(monthKey));
  const row = pdfMonthlyRow(monthKey) || { month: monthKey, ...pdfSumRows(daily) };
  const previous = pdfPreviousMonthlyRow(monthKey);
  const posts = state.data.posts
    .filter((post) => post.month === monthKey || post.date.startsWith(monthKey))
    .sort((a, b) => b.date.localeCompare(a.date));
  const pages = [
    pdfSummaryPage(row, previous, meta, daily, posts),
    pdfEvolutionPage(daily, row),
    ...pdfPostsPages(posts),
    pdfAudiencePage(),
    pdfMethodologyPage(),
  ];

  const report = document.querySelector("#pdf-report");
  report.innerHTML = pages.join("");
  const pageNodes = [...report.querySelectorAll(".pdf-page")];
  pageNodes.forEach((page, index) => {
    const label = page.querySelector(".pdf-page-number");
    if (label) label.textContent = `Página ${index + 1} de ${pageNodes.length}`;
  });

  const charts = [];
  PDF_METRIC_KEYS.forEach((key) => {
    const canvas = report.querySelector(`#pdf-chart-${key}`);
    if (canvas) charts.push(pdfLineChart(canvas, daily, key));
  });
  charts.push(...createPdfAudienceCharts(report));
  return { report, charts };
}

function nextFrame() {
  return new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
}

async function waitForImages(root) {
  const images = [...root.querySelectorAll("img")];
  await Promise.all(images.map((image) => {
    if (image.complete) return Promise.resolve();
    return new Promise((resolve) => {
      image.addEventListener("load", resolve, { once: true });
      image.addEventListener("error", resolve, { once: true });
    });
  }));
}

async function downloadPdfReport() {
  if (state.pdfBusy) return;
  if (state.month === "all" || state.month === "custom" || !monthMeta(state.month)) return;
  if (typeof Chart === "undefined" || typeof html2canvas !== "function" || !(window.jspdf && window.jspdf.jsPDF)) {
    document.querySelector("#period-caption").textContent = "No se pudo cargar el generador de PDF. Recarga la página e intenta nuevamente.";
    return;
  }

  state.pdfBusy = true;
  updatePdfButton();
  const report = document.querySelector("#pdf-report");
  let charts = [];

  try {
    const built = buildPdfReport(state.month);
    charts = built.charts;
    await nextFrame();
    await waitForImages(report);
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    await nextFrame();

    const pages = [...report.querySelectorAll(".pdf-page")];
    if (!pages.length) throw new Error("El reporte no tiene páginas.");

    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4", compress: true });
    pdf.setDisplayMode("fullpage");
    pdf.viewerPreferences({ FitWindow: true, PrintScaling: "None" });
    pdf.setProperties({
      title: `Reporte mensual ${monthLabel(state.month)}`,
      subject: "Métricas del fanpage Ferre Experto Pacasmayo",
      author: "Ferre Experto Pacasmayo",
      creator: "Dashboard Ferre Experto",
    });

    for (let index = 0; index < pages.length; index += 1) {
      const canvas = await html2canvas(pages[index], {
        scale: 2,
        backgroundColor: "#f5f4f1",
        useCORS: true,
        logging: false,
        imageTimeout: 20000,
        width: 794,
        height: 1123,
      });
      const image = canvas.toDataURL("image/jpeg", 0.9);
      if (index > 0) pdf.addPage();
      pdf.addImage(image, "JPEG", 0, 0, 210, 297, undefined, "FAST");
    }

    pdf.save(`reporte-ferre-experto-${state.month}.pdf`);
  } catch (error) {
    console.error(error);
    document.querySelector("#period-caption").textContent = "No se pudo generar el PDF. Intenta nuevamente.";
  } finally {
    charts.forEach((chart) => chart.destroy());
    report.innerHTML = "";
    state.pdfBusy = false;
    updatePdfButton();
  }
}

function bindEvents() {
  document.querySelector("#download-pdf").addEventListener("click", downloadPdfReport);

  document.querySelector("#period-select").addEventListener("change", (event) => {
    state.month = event.target.value;
    toggleCustomRange();
    syncRangeUrl();
    renderKPIs();
    renderTrendChart();
    renderPosts();
  });

  document.querySelector("#range-start").addEventListener("change", applyRangeInputs);
  document.querySelector("#range-end").addEventListener("change", applyRangeInputs);

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
    applyRangeFromUrl();
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

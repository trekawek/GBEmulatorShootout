import {
  element,
  fetchJson,
  formattedDate,
  safeAssetUrl,
  safeExternalUrl,
  showError,
  systemBadges,
} from "./common.js";

const STATUS = {
  pass: { label: "Passed", icon: "✓", filter: "pass" },
  fail: { label: "Failed", icon: "×", filter: "fail" },
  info: { label: "Info", icon: "·", filter: "other" },
  missing: { label: "Missing", icon: "·", filter: "other" },
  error: { label: "Error", icon: "!", filter: "other" },
  skipped: { label: "Skipped", icon: "·", filter: "other" },
};
const VALID_FILTERS = new Set(["all", "pass", "fail", "other"]);
const params = new URLSearchParams(location.search);
let filter = VALID_FILTERS.has(params.get("status")) ? params.get("status") : "all";
let expanded = new Set(params.get("suite") ? [params.get("suite")] : []);
let emulator;
let resultData;
let catalog;

function matchesFilter(item) {
  return filter === "all" || STATUS[item.status]?.filter === filter;
}

function updateUrl() {
  const next = new URL(location.href);
  if (filter === "all") next.searchParams.delete("status");
  else next.searchParams.set("status", filter);
  if (expanded.size === 1) next.searchParams.set("suite", [...expanded][0]);
  else next.searchParams.delete("suite");
  history.replaceState(null, "", next);
}

function filterButton(id, label, count) {
  const button = element("button", {
    className: "filter",
    type: "button",
    "aria-pressed": String(filter === id),
  }, [label, element("span", { text: String(count) })]);
  button.addEventListener("click", () => {
    filter = id;
    if (filter !== "all") {
      expanded = new Set(catalog.suites.map((suite) => suite.id));
    }
    updateUrl();
    renderResults();
  });
  return button;
}

function sourceLinks(suite) {
  const fragment = document.createDocumentFragment();
  for (const source of suite.sources || []) {
    const label = suite.sources.length === 1 ? "Suite source" : source.label;
    fragment.append(element("a", {
      href: safeExternalUrl(source.url),
      target: "_blank",
      rel: "noopener noreferrer",
    }, [label, element("span", { text: " ↗", "aria-hidden": "true" })]));
  }
  return fragment;
}

function statusCount(results, status) {
  return results.filter((item) => item.status === status).length;
}

function suiteStatusSummary(results) {
  const fragment = document.createDocumentFragment();
  for (const status of ["pass", "fail", "info"]) {
    const count = statusCount(results, status);
    if (count) fragment.append(element("span", { className: `${status}-text`, text: `${count} ${STATUS[status].label.toLowerCase()}` }));
  }
  const other = results.filter((item) => ["missing", "error", "skipped"].includes(item.status)).length;
  if (other) fragment.append(element("span", { className: "other-text", text: `${other} other` }));
  return fragment;
}

function openScreenshot(item) {
  const dialog = document.querySelector("#screenshot-dialog");
  const image = document.querySelector("#dialog-image");
  document.querySelector("#dialog-title").textContent = `${item.legacyName} · ${STATUS[item.status].label}`;
  image.src = safeAssetUrl(item.screenshot.url);
  image.alt = `${item.legacyName}: ${STATUS[item.status].label}`;
  dialog.showModal();
}

function testCard(item) {
  const status = STATUS[item.status] || { label: item.status, icon: "·" };
  let visual;
  if (item.screenshot) {
    visual = element("button", {
      className: "screen has-image",
      type: "button",
      "aria-label": `Enlarge ${item.legacyName} screenshot`,
    }, element("img", {
      src: safeAssetUrl(item.screenshot.url),
      width: item.screenshot.width,
      height: item.screenshot.height,
      loading: "lazy",
      alt: `${item.legacyName}: ${status.label}`,
    }));
    visual.addEventListener("click", () => openScreenshot(item));
  } else {
    visual = element("div", { className: "screen" });
    visual.append(element("span", { className: "no-image", text: item.reason || "No screenshot captured" }));
  }

  const card = element("figure", { className: "test-card" }, [
    element("div", { className: "test-heading" }, [
      element("span", { className: `status ${item.status}`, text: `${status.icon} ${status.label}` }),
      element("span", { className: "model", text: item.system === "unknown" ? "Model ?" : item.system }),
    ]),
    visual,
    element("figcaption", { text: item.name }),
  ]);
  if (item.group) card.append(element("div", { className: "path", text: item.group }));
  if (item.reason && item.screenshot) card.append(element("div", { className: "reason", text: item.reason }));
  return card;
}

function suiteSection(suite, allResults, shownResults) {
  const isOpen = expanded.has(suite.id);
  const section = element("section", { className: "suite" });
  const grid = element("div", { className: "test-grid", id: `suite-${suite.id}`, hidden: !isOpen });
  for (const item of shownResults) grid.append(testCard(item));
  const toggle = element("button", {
    className: "suite-toggle",
    type: "button",
    "aria-expanded": String(isOpen),
    "aria-controls": grid.id,
  }, [
    element("span", { className: "chevron", text: isOpen ? "▾" : "▸", "aria-hidden": "true" }),
    suite.name,
    element("span", { className: "suite-count", text: String(shownResults.length) }),
  ]);
  toggle.addEventListener("click", () => {
    if (expanded.has(suite.id)) expanded.delete(suite.id);
    else expanded.add(suite.id);
    updateUrl();
    renderResults();
  });
  const meta = element("div", { className: "suite-meta" });
  meta.append(suiteStatusSummary(allResults), sourceLinks(suite));
  section.append(element("div", { className: "suite-heading" }, [toggle, meta]), grid);
  return section;
}

function renderResults() {
  const filters = document.querySelector("#filters");
  filters.replaceChildren();
  const all = resultData.results;
  const otherCount = all.filter((item) => STATUS[item.status]?.filter === "other").length;
  filters.append(
    filterButton("all", "All", all.length),
    filterButton("pass", "Passed", resultData.counts.pass),
    filterButton("fail", "Failed", resultData.counts.fail),
    filterButton("other", "Other", otherCount),
  );

  const shown = all.filter(matchesFilter);
  const suiteById = new Map(catalog.suites.map((suite) => [suite.id, suite]));
  const visibleSuiteIds = [...new Set(shown.map((item) => item.suiteId))];
  const visibleSuites = catalog.suites.filter((suite) => visibleSuiteIds.includes(suite.id));
  document.querySelector("#results-count").textContent =
    `${shown.length} ${filter === "all" ? "test cases" : filter === "other" ? "other results" : `${filter}ed tests`} in ${visibleSuites.length} suites`;

  const container = document.querySelector("#suites");
  container.replaceChildren();
  for (const suiteId of visibleSuiteIds) {
    const suite = suiteById.get(suiteId) || { id: suiteId, name: suiteId, sources: [] };
    const allSuiteResults = all.filter((item) => item.suiteId === suiteId);
    const shownSuiteResults = shown.filter((item) => item.suiteId === suiteId);
    container.append(suiteSection(suite, allSuiteResults, shownSuiteResults));
  }
  if (!shown.length) container.append(element("div", { className: "empty", text: "No tests match this filter." }));

  const toggle = document.querySelector("#toggle-suites");
  const everyOpen = visibleSuiteIds.every((id) => expanded.has(id));
  toggle.textContent = everyOpen ? "Collapse all suites" : "Expand all suites";
  toggle.onclick = () => {
    expanded = everyOpen ? new Set() : new Set(visibleSuiteIds);
    updateUrl();
    renderResults();
  };
}

async function start() {
  const error = document.querySelector("#load-error");
  try {
    const emulatorId = params.get("id");
    const index = await fetchJson("data/index.json");
    emulator = index.emulators.find((item) => item.id === emulatorId);
    if (!emulator || !emulator.resultsUrl) throw new Error("Unknown emulator or no results available");
    resultData = await fetchJson(emulator.resultsUrl);
    catalog = await fetchJson(resultData.catalogUrl);
    if (resultData.emulatorId !== emulator.id || resultData.catalogId !== catalog.id) {
      throw new Error("The results and catalog do not match the index");
    }
    if (!expanded.size) {
      const first = catalog.suites.find((suite) => resultData.results.some((item) => item.suiteId === suite.id));
      if (first) expanded.add(first.id);
    }

    document.title = `${emulator.name} · GB Emulator Shootout`;
    document.querySelector("#emulator-name").textContent = emulator.name;
    const systems = document.querySelector("#emulator-systems");
    systems.append(systemBadges(emulator.systems));
    const homepage = document.querySelector("#emulator-homepage");
    homepage.href = safeExternalUrl(emulator.homepage);
    homepage.target = "_blank";
    homepage.rel = "noopener noreferrer";
    document.querySelector("#tested-at").textContent = formattedDate(emulator.testedAt);
    document.querySelector("#score-value").textContent = emulator.score.value;
    document.querySelector("#score-recorded").textContent = emulator.score.recorded;
    renderResults();
    document.querySelector("#report").hidden = false;
  } catch (caught) {
    showError(error, caught);
  }
}

const dialog = document.querySelector("#screenshot-dialog");
document.querySelector("#close-dialog").addEventListener("click", () => dialog.close());
dialog.addEventListener("click", (event) => {
  if (event.target === dialog) dialog.close();
});

start();

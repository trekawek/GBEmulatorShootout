import {
  element,
  fetchJson,
  formattedDate,
  safeExternalUrl,
  showError,
  systemBadges,
} from "./common.js";

function renderRow(emulator) {
  const homepage = element("a", {
    className: "emulator-name",
    href: safeExternalUrl(emulator.homepage),
    target: "_blank",
    rel: "noopener noreferrer",
  }, [emulator.name, element("span", { className: "external", text: "↗", "aria-hidden": "true" })]);

  const scoreValue = emulator.score.recorded ? String(emulator.score.value) : "—";
  const percentage = emulator.score.recorded ? (emulator.score.value / emulator.score.recorded) * 100 : 0;
  const score = element("div", {}, [
    element("div", { className: "score-line" }, [
      element("strong", { text: scoreValue }),
      element("span", { text: `/ ${emulator.score.recorded}` }),
    ]),
    element("div", { className: "meter", "aria-hidden": "true" }, [
      element("span", { style: `width:${percentage}%` }),
    ]),
  ]);

  const systems = element("div", { className: "systems" });
  systems.append(systemBadges(emulator.systems));
  const details = emulator.resultsUrl
    ? element("a", {
        className: "details-link",
        href: `emulator.html?id=${encodeURIComponent(emulator.id)}`,
      }, ["View tests", element("span", { text: "→", "aria-hidden": "true" })])
    : element("span", { className: "results-count", text: "No results" });

  return element("tr", {}, [
    element("td", {}, homepage),
    element("td", {}, score),
    element("td", {}, systems),
    element("td", { className: "align-right" }, details),
  ]);
}

async function start() {
  const error = document.querySelector("#load-error");
  try {
    const data = await fetchJson("data/index.json");
    if (data.schemaVersion !== 1 || !Array.isArray(data.emulators)) throw new Error("Unsupported index schema");
    const body = document.querySelector("#emulator-rows");
    const catalogCount = new Set(data.emulators.map((item) => item.catalogId)).size;
    document.querySelector("#overview-summary").textContent =
      `${data.emulators.length} emulators · accuracy results grouped by test suite`;
    document.querySelector("#snapshot").textContent =
      `${formattedDate(data.publishedAt).replace("Tested", "Published")} · ${catalogCount} test catalog${catalogCount === 1 ? "" : "s"}`;
    for (const emulator of data.emulators) body.append(renderRow(emulator));
    document.querySelector("#results-table").hidden = false;
    document.querySelector("#page-notes").hidden = false;
  } catch (caught) {
    showError(error, caught);
  }
}

start();

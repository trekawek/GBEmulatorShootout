export const siteBase = new URL("../", import.meta.url);

export async function fetchJson(relativeUrl) {
  const url = new URL(relativeUrl, siteBase);
  const response = await fetch(url, { cache: "no-cache" });
  if (!response.ok) {
    throw new Error(`Could not load ${url.pathname} (${response.status})`);
  }
  return response.json();
}

export function element(name, attributes = {}, children = []) {
  const node = document.createElement(name);
  for (const [key, value] of Object.entries(attributes)) {
    if (value === undefined || value === null) continue;
    if (key === "className") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("aria-")) node.setAttribute(key, value);
    else node[key] = value;
  }
  for (const child of Array.isArray(children) ? children : [children]) {
    if (child !== null && child !== undefined) node.append(child);
  }
  return node;
}

export function safeExternalUrl(value) {
  const url = new URL(value);
  if (url.protocol !== "https:" && url.protocol !== "http:") {
    throw new Error(`Unsupported external URL protocol: ${url.protocol}`);
  }
  return url.href;
}

export function safeAssetUrl(value) {
  if (!value || value.startsWith("/") || value.includes("..")) {
    throw new Error("Unsafe asset path");
  }
  const url = new URL(value, siteBase);
  if (url.origin !== siteBase.origin) throw new Error("Asset URL leaves the site origin");
  return url.href;
}

export function formattedDate(value) {
  if (!value) return "Test date not recorded";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "Test date not recorded";
  return `Tested ${new Intl.DateTimeFormat("en", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(date)}`;
}

export function formattedGenerationTime(value) {
  if (!value) return "Generation time not recorded";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "Generation time not recorded";
  const timestamp = new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
    timeZone: "UTC",
  }).format(date);
  return `Results generated ${timestamp} UTC`;
}

export function systemBadges(systems) {
  const fragment = document.createDocumentFragment();
  for (const model of ["dmg", "cgb", "sgb"]) {
    const value = systems?.[model];
    let text = model.toUpperCase();
    let className = "system";
    let meaning = "supported by the test adapter";
    if (value === null || value === undefined) {
      text += " ?";
      className += " unknown";
      meaning = "support unknown";
    } else if (value === false) {
      text = "—";
      className += " unsupported";
      meaning = "unsupported by the test adapter";
    }
    fragment.append(element("span", {
      className,
      text,
      "aria-label": `${model.toUpperCase()}: ${meaning}`,
    }));
  }
  return fragment;
}

export function showError(container, error) {
  console.error(error);
  container.textContent = "The results could not be loaded. Please refresh the page or try again later.";
  container.hidden = false;
}

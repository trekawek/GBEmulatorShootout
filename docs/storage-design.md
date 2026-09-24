# Static results site: storage proposal

Status: implemented by the static report builder and `gh-pages-new` deployment workflow.

Use HTML, CSS, and a small JavaScript module that reads JSON published alongside the site. Keep screenshots as PNG files. No database, application server, framework, or GitHub API calls are needed in the browser. This fits [GitHub Pages' static hosting model](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages); JavaScript can load JSON with [the Fetch API](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch).

## What exists today

The original migration findings came from the local `gh-pages` snapshot at `72fd745` (2026-06-04). The fork's newer `gh-pages` snapshot at `bc4edbb` also includes Coffee GB and SuperSnes9x; the generated `gh-pages-new` branch now includes their results. These commits describe stored snapshots, not a verification of the currently published website.

| Area | Existing behavior | Design implication |
| --- | --- | --- |
| Emulator metadata | `main.py` has 20 `EMULATOR_SPECS` in the fork, including Coffee GB and SuperSnes9x; the former export contained display name, homepage, and result filename. | Add stable IDs and explicit system metadata. Display names must not be storage keys. |
| Test metadata | Nine suite modules feed the test list. Export includes name, description, and an optional URL. `Test` already knows the model and required features, but these are not exported. | Export suite, model, variant, and feature requirements directly. |
| Results | One JSON per emulator contains its name, Unix timestamp, and tests keyed by display name. Each test has result, timings, and a base64 screenshot. | Preserve the convenient per-emulator split, but use stable case IDs and file paths for images. |
| Scoring | `build.py` counts every recorded result other than `FAIL`, including `INFO`; the denominator is the number of recorded results. Sorting uses that count, not a percentage. | Preserve and clearly label this rule during the presentation migration. |
| Missing results | Unsupported models/features, execution errors, and absent results all disappear from the result dictionary. A run with no results does not write JSON. | Old data cannot reliably distinguish these cases. New runs should record explicit outcomes. |
| Screenshots | `build.py` embeds every screenshot again in one large HTML matrix. | The list page should load no test images; details can load images as they approach the viewport. |
| Publishing | `deploy-pages.yml` clones `gh-pages`, replaces available emulator JSONs with CI artifacts, regenerates metadata and HTML, then pushes the branch. Other emulators retain their previous data. | Preserve independent emulator updates and show each run's date. A site build date is not a test date. |

The adapters do not declare supported systems centrally. Some reject particular models; others rely on automatic selection. An adapter accepting a model is not proof of complete upstream support. The metadata should distinguish upstream support from what this harness can test, particularly for SGB. The current suite has only one explicitly SGB-targeted case (`cpp/sgb-ext-test.gb`), so an SGB badge must not imply broad validation.

Catalog drift is already visible in the local snapshot: `tests.json` lists 264 cases, while No$gmb's result file also contains three names absent from that catalog. Its existing score is 44/205 (39 PASS, 161 FAIL, 5 INFO). Preserve those records and the score when importing; silently joining only against the current catalog would change the reported results.

## Pages and behavior

- **Overview:** a semantic table with Name (homepage link), Score, Supported systems (DMG/CGB/SGB), and Details. Put emulator version and test date below the name, avoiding extra columns. Default sorting preserves the existing score order. Search and system filters are optional conveniences.
- **Details:** emulator heading and run information, then suites with source links and their own totals. Within each suite, display a grid of test cards containing case name, system, text status, and screenshot. Preserve test subgroup paths such as `acceptance/ppu` for orientation.
- **Filtering:** All, Passed, Failed, and Other. Other keeps informational, skipped, error, and missing cases discoverable. Filters combine with suite/system/search filters and show the number of visible results. Filtering must not change the emulator's overall score.
- **Images:** every available screenshot belongs to a card in All. Use native pixel dimensions, `image-rendering: pixelated`, explicit width/height, and `loading="lazy"`; clicking opens a comparison with the captured image beside every accepted reference variant. Cases without a reference show a clear message. Missing captures display an explanation instead of a broken image.
- **Suite sources:** most suites have one repository link. Acid and Ashiepaws group multiple projects, so store a list of sources and retain individual test URLs. Do not synthesize an incorrect single repository for such groups.

## Minimum published layout

```text
site/
  index.html
  emulator.html
  assets/
    site.css
    site.js
  data/
    index.json                     # small table metadata + derived summaries
    catalogs/
      catalog-001.json              # suite and case definitions for this revision
    results/
      sameboy.json                 # latest accepted run for this emulator
      mgba.json
  screenshots/
    sameboy/
      run-001/
        acid-dmg-acid2-dmg.png
    mgba/
      run-002/
        acid-dmg-acid2-dmg.png
  references/
    acid/
      dmg-acid2.png                   # shared accepted reference image
  .nojekyll
```

Keep author-maintained metadata beside the Python source, for example `metadata/emulators.json` and `metadata/suites.json`. Give emulator specifications and `Test` explicit IDs, and generate the published catalog from those definitions. Homepage/support/suite links should have one maintained source, not independently edited copies in Python, HTML, and JSON.

Publish only the latest accepted result for each emulator initially. Keep the catalog revisions referenced by those results, because independently updated emulators may have run different test sets. Screenshot paths include a run ID to avoid stale image reuse after an update. Old screenshots may be removed from the next site artifact once no current result references them. Historical result browsing is optional: it would move result files into `data/runs/<run-id>/` and make the table index point to them; the page model need not change.

## JSON contract

The examples below illustrate the proposed format, not actual SameBoy results or support assertions. The catalog and result examples show only one item; they are abbreviated and do not reproduce the summary counts.

`data/index.json` is generated, never edited by hand. It is sufficient to render the overview without fetching every emulator's results.

```json
{
  "schemaVersion": 1,
  "publishedAt": "2026-09-23T12:00:00Z",
  "scorePolicy": "legacy-nonfail-v1",
  "emulators": [
    {
      "id": "sameboy",
      "name": "SameBoy",
      "homepage": "https://sameboy.github.io/",
      "systems": {"dmg": "supported", "cgb": "supported", "sgb": "supported"},
      "testedSystems": ["dmg", "cgb", "sgb"],
      "version": null,
      "testedAt": "2026-09-22T15:00:00Z",
      "runId": "run-001",
      "runState": "legacy",
      "catalogId": "catalog-001",
      "resultsUrl": "data/results/sameboy.json?run=run-001",
      "counts": {"pass": 6, "fail": 1, "info": 1, "error": 0, "skipped": 1, "missing": 0},
      "score": {"value": 7, "recorded": 8},
      "coverage": {"recorded": 8, "catalogTotal": 9}
    }
  ]
}
```

Use `supported`, `unsupported`, or `unknown` for each system; a blank or unknown value must not become an assertion of no support. Maintain support evidence and its checked date in the source metadata. `testedSystems` describes this run's coverage, separately from the declared support badges. A null version means the old export did not record it; show “Version not recorded.”

`data/catalogs/catalog-001.json` defines suites and stable test cases. Case identity includes the execution model and hardware/reference variant: the same ROM run in DMG and CGB modes must remain two cases. Existing names containing `GBC` normalize to `cgb` through the actual Python `model`, not filename guessing. Mealybug's revision-specific variants must remain distinct if enabled later.

```json
{
  "schemaVersion": 1,
  "id": "catalog-001",
  "suites": [
    {
      "id": "acid",
      "name": "Acid tests",
      "sources": [
        {"label": "dmg-acid2", "url": "https://github.com/mattcurrie/dmg-acid2"},
        {"label": "cgb-acid2", "url": "https://github.com/mattcurrie/cgb-acid2"},
        {"label": "cgb-acid-hell", "url": "https://github.com/mattcurrie/cgb-acid-hell"}
      ],
      "sourceRevision": null
    }
  ],
  "tests": [
    {
      "id": "acid-dmg-acid2-dmg",
      "legacyName": "acid/dmg-acid2.gb",
      "name": "dmg-acid2",
      "suiteId": "acid",
      "group": "Rendering",
      "system": "dmg",
      "variant": null,
      "requiredFeatures": [],
      "description": "Rendering test for classic Game Boy.",
      "sourceUrl": "https://github.com/mattcurrie/dmg-acid2",
      "expected": [
        {"url": "references/acid/dmg-acid2.png", "width": 160, "height": 144}
      ]
    }
  ]
}
```

`data/results/sameboy.json` stores outcomes and provenance. Its image URLs, like the index's `resultsUrl`, are relative to the site's root directory (the directory containing `index.html`), not relative to the JSON file.

```json
{
  "schemaVersion": 1,
  "emulatorId": "sameboy",
  "runId": "run-001",
  "runState": "legacy",
  "testedAt": "2026-09-22T15:00:00Z",
  "emulatorVersion": null,
  "catalogId": "catalog-001",
  "catalogUrl": "data/catalogs/catalog-001.json",
  "provenance": {
    "runnerCommit": null,
    "workflowUrl": null,
    "platform": "windows",
    "selection": {"emulators": ["sameboy"], "tests": null, "systems": null},
    "importedLegacy": true
  },
  "results": [
    {
      "testId": "acid-dmg-acid2-dmg",
      "status": "pass",
      "reason": null,
      "startupSeconds": 0.8,
      "runtimeSeconds": 1.6,
      "screenshot": {
        "url": "screenshots/sameboy/run-001/acid-dmg-acid2-dmg.png",
        "width": 160,
        "height": 144
      }
    }
  ]
}
```

New runs record the resolved emulator version/build, runner commit, workflow URL, execution platform, actual selection, and test/reference catalog revision. Suite source revisions are recorded when known; do not invent revision IDs when the repository only has vendored files. `runState` is `complete`, `partial`, `failed`, or `legacy`; imported legacy data cannot establish that a run was complete. `screenshot` can be null. Output should contain one outcome per selected case, including skips and execution errors. The build creates `missing` placeholders for absent catalog cases when importing legacy data; their reason remains unknown.

## Scores, statuses, and comparable results

The redesign should not silently change the ranking algorithm. Initially retain `legacy-nonfail-v1`:

```text
score.value    = pass + info
score.recorded = pass + fail + info
```

Display `7 / 8` with a nearby explanation: “Recorded non-failing results; includes informational tests.” Sort by `score.value` descending as today, with name as a deterministic tie-break. A percentage, if shown, is a non-failing share, not an accuracy percentage. Do not call `INFO` a passed test in the details filter.

| Status | Meaning | Legacy score treatment |
| --- | --- | --- |
| `pass` | Runner returned PASS. | Numerator and denominator. |
| `fail` | Runner returned FAIL. | Denominator only. |
| `info` | Runner returned INFO; no pass verdict was established. | Numerator and denominator, matching current behavior. |
| `error` | Execution failed, for example a crash or harness exception. | Neither; shown separately. |
| `skipped` | Known reason such as unsupported system/feature or excluded selection. | Neither; reason required. |
| `missing` | No recorded result, with no reliable explanation. | Neither; never infer failure or unsupported hardware. |

Reject unexpected status strings during validation instead of counting them as success. The legacy builder accepts any non-FAIL string; the converter should report any such historical anomalies for review rather than silently reinterpret them. A zero denominator displays “No results,” not 0%.

Show coverage and run date alongside the score or in its explanation. A DMG-only emulator can have a high percentage on a small subset; percentages across different coverage are not equivalent measurements. An optional future `strict-pass-v2` policy would use `pass / (pass + fail)` and exclude informational outcomes, but should be introduced as an explicit scoring change, with per-system coverage and comparisons within the same catalog and selection. This is not required for the presentation work.

Mark filtered/incomplete runs clearly; do not let a small rerun replace an emulator's complete overview snapshot. By default, promotion requires the full configured selection and an explicit outcome for every selected case. Old imported data remains labelled “Legacy coverage unknown.” A failed new run can be retained as a diagnostic artifact while the table continues to show the last accepted run and its actual date. Do not combine tests from different emulator versions into a result that claims to be one run.

## Loading and routing

Use real files and query parameters: `index.html` and `emulator.html?id=sameboy&status=fail&suite=acid`. Refreshing or sharing these URLs requires no server routing rule. Use `URLSearchParams`, validate the emulator ID against the downloaded index, and preserve filters in the URL.

Resolve paths against the site directory, for example `const siteBase = new URL("./", location.href)` for these two root-level pages. Fetch `new URL("data/index.json", siteBase)`, then the selected result and its referenced catalog. Do not start paths with `/`, which would discard `/GBEmulatorShootout/` on a project site. [GitHub's documentation describes the project-site URL prefix](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages).

Check `response.ok` before parsing JSON, as [Fetch does not reject merely because an HTTP error status was returned](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch). Show visible loading, unavailable-data, unknown-emulator, and empty-filter states. Render imported text with `textContent`, and accept only expected HTTP(S) source URLs and local asset paths.

Fetch the index with revalidation, and use the run ID in result URLs. Validate that the returned run ID matches the index; if an update races with a page load, refresh the index once and show a retry state rather than silently joining different runs. Catalog URLs and screenshot paths change when their contents change. No service worker or custom caching layer is needed.

For local preview, serve the output with `python -m http.server --directory site 8000`; loading a page through `file://` is not the supported fetch workflow. A small build-time HTML table fallback is optional if no-JavaScript browsing/search indexing becomes a requirement.

## Build, validation, and migration

Keep the existing CI flow for the first version: runner artifacts feed a Python build that produces one complete site directory, then the existing `gh-pages` publishing step copies that output. Extend artifact upload/download to include PNGs in their emulator-specific paths. A later change could deploy that directory through [GitHub's official Pages artifact workflow](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages); that is independent of the data redesign.

Before publishing, validate schema versions; unique emulator/suite/test IDs; allowed enums; catalog references; nonnegative timings and counts; complete image paths and dimensions; and agreement between the index's derived summaries and detailed results. Reject paths escaping the output directory. Recompute summaries in the builder from results so browser and table cannot develop different formulas. Basic schema checks and cross-file checks are sufficient; no schema registry is needed.

1. Add stable metadata and a converter accepting the existing JSON export. Match legacy display names explicitly; use suite module/model definitions to enrich metadata. Unmapped tests remain visible in an “Unmapped legacy tests” group and are reported during conversion. Never silently drop results.
2. Decode the existing base64 images into PNGs, preserving image contents. Map PASS/FAIL/INFO exactly; preserve timestamps/timings; leave unavailable provenance null. Do not assign a skipped/error reason to an absent legacy entry.
3. Generate the compact index, referenced catalogs, latest result files, and site assets. Validate that score counts and recorded denominators match `build.py` for every emulator and that all recorded screenshots resolve.
4. Review the overview and details on desktop/mobile. Verify suite source links, pass/fail/other filters, direct detail URLs, empty/missing-data states, and operation beneath the GitHub Pages project path.
5. Switch the existing publishing step to this output. Keep the old HTML export available during the transition if useful for side-by-side checking. Update the runner afterward to produce explicit statuses and provenance directly; the converter supports older snapshots in the meantime.

This separates presentation from test execution: changing the layout requires only HTML/CSS/JavaScript changes, while adding an emulator or suite primarily changes metadata and generated JSON.

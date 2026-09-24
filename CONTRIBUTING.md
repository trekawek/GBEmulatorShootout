# Contributing

Contributions are welcome! Feel free to open an issue or even a pull request.

## Adding a new emulator

To add a new emulator:

1. Create an adapter in `emulators/`. Its constructor accepts a `spec` and passes `spec.name` and `spec.url` to `Emulator.__init__`. Implement `setup()` and `startProcess()`; override other base methods as needed.
2. Add one entry under `emulators:` in `catalog.yaml`. The ID is used for CLI and CI selection, and as the site ID unless `site_id` is set. Add aliases only when they differ from the ID and display name. Use `systems` to record known model support; omitted systems default to unknown. Set CI options only when their defaults do not work.
3. Run `python -m catalog validate` and `python main.py --emulator myemu` on a supported system.

For example, append this entry to the list:

```yaml
  - id: myemu
    name: MyEmulator
    url: https://myemulator.example.com/
    adapter: emulators.myemu:MyEmulator
```

The same catalog entry supplies the HTML report and the CI matrix. To run one emulator in GitHub Actions, dispatch `CI - emulators` with its ID; use `all` for the full suite.

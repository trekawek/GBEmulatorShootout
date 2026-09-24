# Contributing

Contributions are welcome! Feel free to open an issue or even a pull request.

## Adding a new emulator

To add a new emulator:

1. Create an adapter in `emulators/`. Its constructor accepts a `spec` and passes `spec.name` and `spec.url` to `Emulator.__init__`. Implement `setup()` and `startProcess()`; override other base methods as needed.
2. Add one `EmulatorSpec` entry to `EMULATORS` in `emulators/catalog.py`. The ID is used for CLI and CI selection. Add aliases only when they differ from the ID and display name. Set CI options there if the defaults do not work.
3. Run `python -m emulators.catalog validate` and `python main.py --emulator myemu` on a supported system.

An example emulator specification:

```python
EmulatorSpec("myemu", "MyEmulator", "https://myemulator.example.com/", "emulators.myemu:MyEmulator")
```

The same catalog entry supplies the HTML report and the CI matrix. To run one emulator in GitHub Actions, dispatch `CI - emulators` with its ID; use `all` for the full suite.

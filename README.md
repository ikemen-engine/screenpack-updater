# screenpack-updater

A small patcher for IKEMEN screenpack config files (`system.def`). It updates/cleans keys and values and then marks the file as:

- `[Info]`
- `ikemenversion = 1.0`

If the file already has `ikemenversion >= 1.0`, it won’t patch it.

## Usage

### Windows
Run the executable:
- `screenpack-updater.exe`

If you start it without arguments, a file picker opens — select the file to patch (usually `system.def`).  
It patches in place and creates a backup: `system.def.bak`.

### macOS / Linux
Run the binary from the release zip:
```bash
./screenpack-updater path/to/system.def

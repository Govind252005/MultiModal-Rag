# Multimodal RAG Installer — Review Findings & Fixes

I went through every `.iss` and `.ps1` file line by line rather than just
scoring the draft checklist. Here's what's actually true, what's not, and
what I fixed in this folder.

## Fixed (confirmed compile/runtime bugs)

### 1. AppId GUID was malformed (would fail to compile)
`constants.iss` defines `APP_GUID` **with its own curly braces already
baked in**:
```
#define APP_GUID "{A7B9C2E1-4F3D-4A6B-9E2C-1D8F5A6B7C90}"
```
`installer.iss` then used `AppId={#APP_GUID}`. After the preprocessor
substitutes the macro, Inno's compiler sees a single unescaped `{` in the
directive value and tries to expand it as a named constant (like `{app}`)
— which doesn't exist, so it fails.
**Fix:** `AppId={{#APP_GUID}` — the extra leading `{` combines with the
brace already inside the macro value to produce the correctly-escaped
`{{GUID}` form Inno expects.

### 2. Module includes were outside the `[Code]` section (would fail to compile)
This is the *real* version of the draft's "CE-001." The include guards
(`#ifndef X_ISS / #define X_ISS / #endif`) are perfectly valid Inno
preprocessor syntax and are **not** the problem — Inno's ISPP supports
them natively. The actual bug is placement: `installer.iss` included
`globals.iss`, `utils.iss`, `logging.iss`, etc. — all of which contain
`var` blocks and Pascal functions — **between `[UninstallDelete]` and
`[Code]`**. Pascal Script is only legal inside an open `[Code]` section,
so the compiler would choke on the first `var`/`function` it hit.
**Fix:** moved the entire include block to just after the `[Code]` header.

### 3. Two `[Code]` headers → consolidated to one
Technically Inno *does* allow a section to reappear and merges the
entries, so this alone wasn't fatal. But per the project's own design
rule ("Ensure there is only one [Code] section"), I moved
`CurUninstallStepChanged` up next to `CurStepChanged` under the single
`[Code]` header and removed the second one.

### 4. Model-already-installed check silently always failed
`download_model.iss` → `IsModelAlreadyInstalled` ran:
```
ExecAndWait(OllamaPath, 'list > "' + ResultsFile + '"', '', ExitCode);
```
`Exec()` launches `ollama.exe` directly — there's no shell involved, so
`>` is passed to Ollama as a literal argument instead of redirecting
output. `ResultsFile` never gets created, the check always reports "not
installed," and the installer would re-pull the model (or the fallback)
on every run/repair even when it's already there.
**Fix:** route through `{cmd} /C "..." list > "..."`, the same pattern
already used correctly in `services.iss`.

### 5. Ollama path detection was narrower than diagnostics
`diagnostics.ps1` checks both `%LOCALAPPDATA%\Programs\Ollama\ollama.exe`
and `%ProgramFiles%\Ollama\ollama.exe`, but `install_ollama.iss` only ever
checked the LocalAppData path. A system-wide install would be reported as
missing by `LocateOllama`/`VerifyOllamaInstalled` even though diagnostics
found it. **Fix:** added a shared `FindOllamaOnDisk` helper that checks
both locations, used by both functions.

## Checked and NOT actual bugs (draft report was off here)

- **CE-001 as written** ("remove include guards") — wrong diagnosis, see
  above. The guards are fine; the include *placement* was the bug.
- **`uninsneveruninstall` + `[UninstallDelete]` on the parent folder** —
  looked suspicious (does `cleanup.ps1` get deleted before it runs?) but
  the ordering is correct: `CurUninstallStepChanged(usUninstall)` fires
  before Inno's built-in file removal for that step, so `cleanup.ps1`
  has already run by the time `[UninstallDelete]` removes the folder.
  Worth testing on a clean VM to be sure, but not a bug in the code.
- Ini section/key names written by `diagnostics.ps1` line up exactly with
  what `checks.iss` reads — no mismatches there.
- No missing `Result :=` assignments in any function — every path returns
  a value.

## Still worth doing (matches the draft's checklist, genuinely useful)

- Digitally sign `MultimodalRagSetup.exe` and the bundled scripts before
  release (Windows SmartScreen will flag an unsigned installer that
  downloads and silently runs other executables).
- Test clean install → upgrade → uninstall on an actual clean VM,
  especially the GPU/CUDA detection path and the "Ollama already
  installed" skip path.
- `UPDATE_GITHUB_API` in `constants.iss` still points at
  `YOUR_ORG/multimodal-rag` — placeholder, update before shipping.
- Minor cleanup: `SRC_BACKEND`, `SRC_FRONTEND`, and `ASSET_SPLASH` in
  `constants.iss` are defined but never referenced anywhere.

## What changed in this folder
- `installer.iss` — AppId escaping, include placement, single `[Code]` section
- `download_model.iss` — shell redirection fix
- `install_ollama.iss` — widened Ollama path detection
- Everything else copied through unchanged

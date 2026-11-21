# H3ZJ — ONNX Runtime and hardware facts come from skellytracker; the version and the build identity

**Status:** accepted, 2026-11-21 (owner; migrated from the
[certification checkpoint](../../current-work-plans/02-pipeline/ep-certification-integration.md), decisions 2 to 4,
6 to 8 and 11, and F17).

## Decision

1. **ONNX Runtime through skellytracker.** freemocap must not declare `onnx` or `onnxruntime` as a dependency.
   Both come through skellytracker. The dev pin `onnx==1.22.0` of `pyproject.toml` stays only for the legacy
   tracker benchmark, and it goes with that benchmark. `freemocap.spec` collects no ONNX Runtime file. PyInstaller
   loads the `hook-onnxruntime.py` of skellytracker through the `pyinstaller40` entry point.
2. **Import order.** On Windows the ONNX Runtime distribution is `onnxruntime-windowsml`, which brings DirectML.
   `import skellytracker` sets `ORT_DISABLE_TELEMETRY=1`. No freemocap module imports `onnxruntime` before
   skellytracker.
3. **Version.** `freemocap.__version__` is SemVer with no leading `v`, for example `2.0.0-alpha.25`. A change of
   the version form changes each reader of it in the same commit.
4. **Build identity.** The `package.commit` of freemocap comes from `BUILD_GIT_SHA` in `freemocap/build_info.py`.
   The installer workflow writes that file. In a source tree, freemocap asks git, else it gives `no-commit`. The
   workflow must compute `BUILD_TREE_MODIFIED` from the tracked files before it writes `build_info.py`, because
   that write makes the tree dirty. Outside CI the value is `None`.
5. **Hardware facts.** skellytracker is the only home of the hardware facts and the live metrics. The anonymous
   `app_opened` ping stays in freemocap (`freemocap/system/telemetry/telemetry.py`). It takes its facts from
   `probe_host()` and `probe_environment().python.version` of skellytracker. `load_snapshot()` of
   `freemocap/tools/machine_benchmarks.py` uses `LiveSampler`, and its load average is `load_average_1m`.
6. **psutil.** freemocap imports `psutil` directly, so `pyproject.toml` must declare it.
7. **UTF-8 output.** `freemocap/__main__.py` sets stdout and stderr to UTF-8 before each other import. A frozen
   app ignores `PYTHONUTF8` and `PYTHONIOENCODING`. skellylogs does not change for this.

## Reason

- The skellycertify report format needs SemVer with no prefix and a 40-hex commit for a report that is valid as
  evidence.
- One owner of ONNX Runtime and of the hardware probe prevents two copies of the EP rules and of the probe code.
- The installed `onnxruntime` files were the same set before and after the move to the hook of skellytracker
  (36 files under `onnxruntime`, `windowsml`, `onnx` and their metadata).
- With piped stdout, the cp1252 console printed `UnicodeEncodeError` logging errors in the frozen app.

## Consequences

- A development build has `no-version` or `modified-tree` in `evidence.reasons`. The UI shows that "not valid as
  evidence" as the expected state of a development build, not as a failed check.
- The telemetry `app_version` changed its spelling with the version change.
- A frozen build from editable sibling installs does not start, because PyInstaller does not see skellycam and
  skellylogs there. This blocks release builds. [open-work.md](../open-work.md) lists it.

## Not repeated

- Do not add `onnxruntime` hidden imports or excludes to `freemocap.spec`. The hook of skellytracker owns them.
- Development worker processes still print the cp1252 errors. Their logging setup is in skellycam.

## Open work

[open-work.md](../open-work.md)

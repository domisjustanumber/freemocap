# Certify report

Schema `skellycertify.report/1.0.0`, app freemocap 2.0.0, created 2026-11-19T10:00:00Z (UTC).

**skellytracker 2.0.0:** valid as evidence.

| Module | Section | Result | Reason |
|---|---|---|---|
| skellytracker | 1. Checkout and versions | pass | |
| skellytracker | 3. EPs: install, verify and certify | pass | |

This file is a sample for the relay tests. It holds example values only.

## Data

```json
{
 "schema": "skellycertify.report/1.0.0",
 "app": {
  "name": "freemocap",
  "version": "2.0.0",
  "commit": "89abcdef0123456789abcdef0123456789abcdef"
 },
 "modules": [
  {
   "schema": "skellycertify.report/1.0.0",
   "package": {
    "name": "skellytracker",
    "version": "2.0.0",
    "commit": "0123456789abcdef0123456789abcdef01234567",
    "tree_modified": false
   },
   "kind": "full",
   "created_utc": "2026-11-19T10:00:00Z",
   "host": {
    "os": {
     "name": "Windows",
     "release": "11",
     "version": "10.0.26300",
     "build": 26300,
     "label": "Windows 11 Home 26H2",
     "arch": "x86_64"
    },
    "cpu": {
     "name": "Example 8-Core Processor"
    },
    "memory_bytes": 34359738368,
    "gpus": [
     {
      "vendor": "nvidia",
      "name": "NVIDIA GeForce RTX 3070",
      "id": "10de:2484",
      "driver_version": "610.88",
      "vram_bytes": 8589934592
     }
    ]
   },
   "sections": [
    {
     "id": "1",
     "name": "Checkout and versions",
     "result": "pass",
     "reason": null,
     "seconds": 3.1,
     "exit_code": 0,
     "summary": "tree clean; Python 3.13.18; 0 package(s) differ from uv.lock",
     "details": {
      "onnx_stack": {
       "ort_distributions": {
        "onnxruntime-windowsml": "1.30.0.202609102321"
       },
       "ort_version": "1.30.0",
       "windowsml": "2.6.74rc0",
       "catalog_revision": "9f2c1b7e5d4a3c2b1a0f9e8d7c6b5a4938271605f4e3d2c1b0a9f8e7d6c5b4a3",
       "set_hash": "4abfaa7678817ed4a8ccb5f3e355ba28672589e8a3468bb6805e491dfe03a302",
       "ort_disable_telemetry": "1"
      }
     }
    },
    {
     "id": "3",
     "name": "EPs: install, verify and certify",
     "result": "pass",
     "reason": null,
     "seconds": 41.2,
     "exit_code": 0,
     "summary": "trt-rtx pass, cuda pass, cpu pass; 3 not run",
     "details": {
      "hardware_class": "nvidia-cc80-r580",
      "store": "isolated"
     }
    }
   ],
   "checks": [
    {
     "section": "1",
     "name": "checkout",
     "result": "pass",
     "reason": null,
     "numbers": {
      "changed_files": 0
     }
    },
    {
     "section": "1",
     "name": "python",
     "result": "pass",
     "reason": null
    },
    {
     "section": "1",
     "name": "packages",
     "result": "pass",
     "reason": null,
     "numbers": {
      "differ": 0,
      "pinned": 141
     }
    },
    {
     "section": "1",
     "name": "telemetry-switch",
     "result": "pass",
     "reason": null
    },
    {
     "section": "3",
     "name": "trt-rtx",
     "result": "pass",
     "reason": null
    },
    {
     "section": "3",
     "name": "cuda",
     "result": "pass",
     "reason": null
    },
    {
     "section": "3",
     "name": "amdgpu",
     "result": "not-run",
     "reason": "not-offered"
    },
    {
     "section": "3",
     "name": "migraphx",
     "result": "not-run",
     "reason": "os"
    },
    {
     "section": "3",
     "name": "cpu",
     "result": "pass",
     "reason": null
    }
   ],
   "cleanup": [],
   "details": {
    "suite_version": 1,
    "selected": [
     1,
     2,
     3,
     4,
     5,
     6,
     7
    ],
    "telemetry_database": {
     "before": false,
     "after": false
    },
    "scrub": {
     "exempted_terms": 0
    }
   },
   "evidence": {
    "valid": true,
    "reasons": []
   }
  }
 ],
 "note": "Example note: the run took about five minutes."
}
```

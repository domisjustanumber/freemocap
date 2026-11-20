# Certify report

freemocap 2.0.0 · 2026-11-19 10:00 UTC

- skellytracker 2.0.0 · full run · valid as evidence

- OS: Windows 11 26H2
- CPU: AMD Ryzen 7 7700X
- RAM: 32 GB

| GPU | Module | Result |
|---|---|---|
| NVIDIA RTX 3070 8 GB | TensorRT RTX | pass |
| NVIDIA RTX 3070 8 GB | CUDA | pass |
| NVIDIA RTX 3070 8 GB | CUDA GPU decode | pass |
| - | CPU | pass |
| Intel UHD 770 | | not checked |

Cameras: not checked on this system.

Note of the person:

> Example note: the run took about five minutes. This file is a sample for the relay tests. It holds example values only.

## Data

```json
{
 "schema": "skellycertify.report/1.2.0",
 "app": {
  "name": "freemocap",
  "version": "2.0.0",
  "commit": "89abcdef0123456789abcdef0123456789abcdef"
 },
 "modules": [
  {
   "schema": "skellycertify.report/1.2.0",
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
     "name": "AMD Ryzen 7 7700X 8-Core Processor"
    },
    "memory_bytes": 34359738368,
    "gpus": [
     {
      "vendor": "nvidia",
      "name": "NVIDIA GeForce RTX 3070",
      "id": "10de:2484",
      "driver_version": "610.88",
      "vram_bytes": 8589934592
     },
     {
      "vendor": "intel",
      "name": "Intel(R) UHD Graphics 770",
      "id": "8086:4688",
      "driver_version": "32.0.101.6881",
      "vram_bytes": 134217728
     }
    ]
   },
   "summary": [
    {
     "group": "ep",
     "name": "TensorRT RTX",
     "device": "10de:2484",
     "result": "pass"
    },
    {
     "group": "ep",
     "name": "CUDA",
     "device": "10de:2484",
     "result": "pass"
    },
    {
     "group": "gpu-jpeg",
     "name": "CUDA",
     "device": "10de:2484",
     "result": "pass"
    },
    {
     "group": "ep",
     "name": "CPU",
     "device": null,
     "result": "pass"
    }
   ],
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
 "note": "Example note: the run took about five minutes. This file is a sample for the relay tests. It holds example values only."
}
```

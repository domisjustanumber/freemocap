# Certify report

freemocap 2.0.0 · 2026-11-19 10:00 UTC

- freemocap 2.0.0 · quick run · valid as evidence
- skellytracker 2.0.0 · quick run · valid as evidence

- OS: Windows 11 26H2
- CPU: AMD Ryzen 7 7700X
- RAM: 32 GB

| GPU | Module | Result |
|---|---|---|
| NVIDIA RTX 3070 8 GB | CUDA | pass |
| NVIDIA RTX 3070 8 GB | CUDA GPU decode | pass |

| Module | Result |
|---|---|
| Build identity | pass |
| Child process | pass |
| Bundle imports | pass |
| Data folder | pass |
| Post-hoc session | pass |
| Install facts | record |
| Blender | record |

Cameras: not checked on this system.

Note of the person:

> Example note: freemocap's own quick report of format 1.6.0 beside a skellytracker report of format 1.4.0. This file is a sample for freemocap's tests. It holds example values only.

## Data

```json
{
 "schema": "skellycertify.report/1.6.0",
 "app": {
  "name": "freemocap",
  "version": "2.0.0",
  "commit": "89abcdef0123456789abcdef0123456789abcdef"
 },
 "modules": [
  {
   "schema": "skellycertify.report/1.6.0",
   "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
   "package": {
    "name": "freemocap",
    "version": "2.0.0",
    "commit": "89abcdef0123456789abcdef0123456789abcdef",
    "tree_modified": false
   },
   "kind": "quick",
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
     }
    ]
   },
   "checks": [
    {
     "name": "build-identity",
     "result": "pass",
     "reason": null,
     "module": "Build identity"
    },
    {
     "name": "spawn-child",
     "result": "pass",
     "reason": null,
     "module": "Child process"
    },
    {
     "name": "bundle-imports",
     "result": "pass",
     "reason": null,
     "module": "Bundle imports"
    },
    {
     "name": "data-folder",
     "result": "pass",
     "reason": null,
     "module": "Data folder"
    },
    {
     "name": "posthoc-session",
     "result": "pass",
     "reason": null,
     "module": "Post-hoc session"
    },
    {
     "name": "install-facts",
     "result": "record-only",
     "reason": null,
     "module": "Install facts"
    },
    {
     "name": "blender",
     "result": "record-only",
     "reason": null,
     "module": "Blender"
    }
   ],
   "cleanup": [],
   "evidence": {
    "valid": true,
    "reasons": []
   },
   "summary": [
    {
     "group": "component",
     "name": "Build identity",
     "device": null,
     "result": "pass"
    },
    {
     "group": "component",
     "name": "Child process",
     "device": null,
     "result": "pass"
    },
    {
     "group": "component",
     "name": "Bundle imports",
     "device": null,
     "result": "pass"
    },
    {
     "group": "component",
     "name": "Data folder",
     "device": null,
     "result": "pass"
    },
    {
     "group": "component",
     "name": "Post-hoc session",
     "device": null,
     "result": "pass"
    },
    {
     "group": "component",
     "name": "Install facts",
     "device": null,
     "result": "record-only"
    },
    {
     "group": "component",
     "name": "Blender",
     "device": null,
     "result": "record-only"
    }
   ]
  },
  {
   "schema": "skellycertify.report/1.4.0",
   "id": "3f2b8c1e-9a4d-4e7b-b6a1-0c5d2e8f7a90",
   "package": {
    "name": "skellytracker",
    "version": "2.0.0",
    "commit": "0123456789abcdef0123456789abcdef01234567",
    "tree_modified": false
   },
   "kind": "quick",
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
     }
    ]
   },
   "summary": [
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
    }
   ],
   "checks": [
    {
     "name": "cuda@10de-2484-0",
     "result": "pass",
     "reason": null
    },
    {
     "name": "cuda@10de-2484-0:probe",
     "result": "pass",
     "reason": null
    },
    {
     "name": "cuda@10de-2484-0:image",
     "result": "pass",
     "reason": null
    },
    {
     "name": "cuda@10de-2484-0:jpeg-decode",
     "result": "pass",
     "reason": null
    },
    {
     "name": "cuda@10de-2484-0:jpeg-preprocess",
     "result": "pass",
     "reason": null
    }
   ],
   "cleanup": [],
   "details": {
    "pipeline": "yolox-rtmw-wholebody@skellytracker",
    "eps": {
     "cuda@10de-2484-0": {
      "gpu": "10de:2484",
      "device": "gpu:10de:2484:0",
      "models": [
       {
        "key": "yolox-m",
        "version": "1.0.0",
        "size": "m",
        "precision": "fp16",
        "execution_provider": "cuda",
        "device": "gpu:10de:2484:0"
       }
      ],
      "warnings": [],
      "pack_version": "0.2.0"
     }
    },
    "versions": {
     "ort_distribution": "onnxruntime-gpu",
     "ort_version": "1.23.0",
     "windowsml": null,
     "catalog_revision": "9f2c1b7e5d4a3c2b1a0f9e8d7c6b5a4938271605f4e3d2c1b0a9f8e7d6c5b4a3",
     "set_hash": "4abfaa7678817ed4a8ccb5f3e355ba28672589e8a3468bb6805e491dfe03a302"
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
 "note": "Example note: freemocap's own quick report of format 1.6.0 beside a skellytracker report of format 1.4.0. This file is a sample for freemocap's tests. It holds example values only."
}
```

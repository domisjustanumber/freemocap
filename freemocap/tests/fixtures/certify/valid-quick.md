# Certify report

freemocap 2.0.0 · 2026-11-19 10:00 UTC

- skellytracker 2.0.0 · quick run · valid as evidence
- skellytracker 2.0.0 · quick run · not valid as evidence: check-failed

- OS: Windows 11 26H2
- CPU: AMD Ryzen 7 7700X
- RAM: 32 GB

| GPU | Module | Result |
|---|---|---|
| NVIDIA RTX 3070 8 GB | CUDA | pass |
| NVIDIA RTX 3070 8 GB | CUDA GPU decode | pass |
| NVIDIA RTX 3070 8 GB | TensorRT RTX | fail |
| NVIDIA RTX 3070 8 GB | TensorRT RTX GPU decode | pass |
| NVIDIA RTX 3070 8 GB | DirectML | pass |

Cameras: not checked on this system.

Checks that did not pass:

| Package | Module | Test | Result | Reason |
|---|---|---|---|---|
| skellytracker | TensorRT RTX | trt-rtx@10de-2484-0 | fail | image-failed |
| skellytracker | TensorRT RTX | trt-rtx@10de-2484-0:image | fail | output-mismatch |

Note of the person:

> Example note: two quick runs of skellytracker on one PC. This file is a sample for the relay tests. It holds example values only.

## Data

```json
{
 "schema": "skellycertify.report/1.4.0",
 "app": {
  "name": "freemocap",
  "version": "2.0.0",
  "commit": "89abcdef0123456789abcdef0123456789abcdef"
 },
 "modules": [
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
  },
  {
   "schema": "skellycertify.report/1.4.0",
   "id": "c1d2e3f4-5a6b-4c7d-8e9f-a0b1c2d3e4f5",
   "package": {
    "name": "skellytracker",
    "version": "2.0.0",
    "commit": "0123456789abcdef0123456789abcdef01234567",
    "tree_modified": false
   },
   "kind": "quick",
   "created_utc": "2026-11-19T10:12:30Z",
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
     "name": "TensorRT RTX",
     "device": "10de:2484",
     "result": "fail"
    },
    {
     "group": "gpu-jpeg",
     "name": "TensorRT RTX",
     "device": "10de:2484",
     "result": "pass"
    },
    {
     "group": "ep",
     "name": "DirectML",
     "device": "10de:2484",
     "result": "pass"
    }
   ],
   "checks": [
    {
     "name": "trt-rtx@10de-2484-0",
     "module": "TensorRT RTX",
     "result": "fail",
     "reason": "image-failed"
    },
    {
     "name": "trt-rtx@10de-2484-0:probe",
     "result": "pass",
     "reason": null
    },
    {
     "name": "trt-rtx@10de-2484-0:image",
     "module": "TensorRT RTX",
     "result": "fail",
     "reason": "output-mismatch"
    },
    {
     "name": "trt-rtx@10de-2484-0:jpeg-decode",
     "result": "pass",
     "reason": null
    },
    {
     "name": "trt-rtx@10de-2484-0:jpeg-preprocess",
     "result": "pass",
     "reason": null
    },
    {
     "name": "directml@10de-2484-0",
     "result": "pass",
     "reason": null
    },
    {
     "name": "directml@10de-2484-0:probe",
     "result": "pass",
     "reason": null
    },
    {
     "name": "directml@10de-2484-0:image",
     "result": "pass",
     "reason": null
    }
   ],
   "cleanup": [],
   "details": {
    "pipeline": "yolox-rtmw-wholebody@skellytracker",
    "eps": {
     "trt-rtx@10de-2484-0": {
      "gpu": "10de:2484",
      "device": "gpu:10de:2484:0",
      "models": [
       {
        "key": "yolox-m",
        "version": "1.0.0",
        "size": "m",
        "precision": "fp16",
        "execution_provider": "trt-rtx",
        "device": "gpu:10de:2484:0"
       }
      ],
      "warnings": [],
      "pack_version": "0.2.0"
     },
     "directml@10de-2484-0": {
      "gpu": "10de:2484",
      "device": "gpu:10de:2484:0",
      "models": [
       {
        "key": "yolox-m",
        "version": "1.0.0",
        "size": "m",
        "precision": "fp16",
        "execution_provider": "directml",
        "device": "gpu:10de:2484:0"
       }
      ],
      "warnings": [],
      "pack_version": "builtin"
     }
    },
    "versions": {
     "ort_distribution": "onnxruntime-windowsml",
     "ort_version": "1.30.0",
     "windowsml": "2.6.74rc0",
     "catalog_revision": "9f2c1b7e5d4a3c2b1a0f9e8d7c6b5a4938271605f4e3d2c1b0a9f8e7d6c5b4a3",
     "set_hash": "4abfaa7678817ed4a8ccb5f3e355ba28672589e8a3468bb6805e491dfe03a302"
    },
    "scrub": {
     "exempted_terms": 0
    }
   },
   "evidence": {
    "valid": false,
    "reasons": [
     "check-failed"
    ]
   }
  }
 ],
 "note": "Example note: two quick runs of skellytracker on one PC. This file is a sample for the relay tests. It holds example values only."
}
```

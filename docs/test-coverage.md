# Test Coverage Goals — tinygpt

## Tier: EXEMPLARY

tinygpt targets EXEMPLARY test coverage across all three runtimes: Swift (native Mac), Python (reference impl), and TypeScript (browser).

## Coverage Targets

| Component | Target | Framework | CI Gate |
|-----------|--------|-----------|---------|
| Swift (TinyGPTModel) | >80% line | XCTest + xccov | Reports (gate TBD) |
| Swift (TinyGPTIO) | >85% line | XCTest + xccov | Reports (gate TBD) |
| Python (python_ref/) | >70% line | unittest + coverage | Reports |
| TypeScript (browser/src/) | >75% line | Vitest + v8 coverage | Reports |

## CI Integration

### Swift coverage
- `CLANG_ENABLE_CODE_COVERAGE=YES` passed to `xcodebuild test`
- `xcrun xccov view --report --json` extracts per-target coverage
- Coverage JSON uploaded as artifact (`swift-coverage-report`)

### Python coverage
- `coverage run --source=python_ref` runs `test_phase1.py` + `test_lora.py`
- `coverage report -m` prints per-file summary
- Coverage XML uploaded as artifact (`python-coverage-report`)

### TypeScript coverage
- `vitest run --coverage` in the `browser` CI job
- v8 coverage provider, thresholds in `browser/vitest.config.ts`
- Coverage targets: `tokenizer.ts`, `datasets.ts`, `gallery-schema.ts`, `runtime_detect.ts`, `storage.ts`

## Running Coverage Locally

### Swift
```bash
cd native-mac
xcodebuild test \
  -scheme TinyGPT-Package \
  -destination 'platform=macOS' \
  -resultBundlePath /tmp/test-result.xcresult \
  CLANG_ENABLE_CODE_COVERAGE=YES
xcrun xccov view --report /tmp/test-result.xcresult
```

### Python
```bash
pip install coverage
coverage run --source=python_ref tests/test_phase1.py
coverage run --source=python_ref --append tests/test_lora.py
coverage report -m
```

### TypeScript (browser)
```bash
cd browser
npm test:coverage
```

## Test Inventory

### Swift (181+ tests across 28 files)
- **TinyGPTModelTests**: 25 files, 181+ test functions (model config, LoRA, optimizers, eval gates, etc.)
- **TinyGPTIOTests**: 1 file, 12+ tests (file format I/O)
- **TinyGPTServeTests**: 2 files (HTTP parser + server)

### Python (14+ tests across 2 files)
- `test_phase1.py`: 14 tests (tokenizer, layer shapes, loss, overfit, gradient check, checkpoint reload)
- `test_lora.py`: LoRA injection, frozen-base gradients, save/load roundtrip

### TypeScript (54 tests across 4 files)
- `tokenizer.test.ts`: 13 tests (encode/decode/roundtrip for ASCII + Unicode)
- `datasets.test.ts`: 18 tests (catalog validation, fetchHfText with mocked HTTP, error handling)
- `runtime_detect.test.ts`: 16 tests (browser detection, hardware tiers, model recommendation)
- `storage.test.ts`: 7 tests (OPFS save/load, gallery cache, durable storage)

### Eval smoke tests (24 bash scripts)
- `eval-gate-smoke.sh`, `common-smoke.sh` run in CI
- Remaining 22 scripts run locally (some need GPU/model access)

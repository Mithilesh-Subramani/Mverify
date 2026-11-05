# Mverify v0.9.0 + Mcore 0.1.0

## Mverify
- Added separate deterministic generated test cases and heuristic/specification-derived suggested scenarios.
- Added a Test Cases desktop tab.
- Added optional Qwen-backed scenario suggestions through the Mcore local API.
- Added an explicit queue action for candidate training examples. Submitted examples remain pending review and are not automatically used for training.
- Added common VCS `.f` filelist discovery, nested filelist handling, `+incdir+` and `+define+` capture in the scan report.
- Updated UVM generation: bounded structural input activity, smoke sequence, active driver where non-reset inputs exist, output observation, analysis-port connections, non-empty scoreboard reporting, unknown-sample checks and a base test that runs sequences.
- Added `verification_testcases.json` to generated UVM output.
- Fixed clock port handling for `clk` and `clock` names.

## Mcore
- Added independent `Mcore/` package and localhost API.
- Added Ollama/Qwen adapter, local knowledge store, training candidate queue and JSONL export of approved examples.
- Added explicit approval with data-use consent.

## Validation
- 38 Python tests pass.
- Python compileall passes for Mverify and Mcore.
- Mcore `/health` endpoint returns HTTP 200.
- Generated UVM structure inspected using a synthetic valid DUT fixture.
- No VCS compile or functional simulation was performed in this build environment.

# Mverify v0.9.0

## Mverify
- Added separate deterministic generated test cases and heuristic/specification-derived suggested scenarios.
- Added a Test Cases desktop tab.
- Added common VCS `.f` filelist discovery, nested filelist handling, `+incdir+` and `+define+` capture in the scan report.
- Updated UVM generation: bounded structural input activity, smoke sequence, active driver where non-reset inputs exist, output observation, analysis-port connections, non-empty scoreboard reporting, unknown-sample checks and a base test that runs sequences.
- Added `verification_testcases.json` to generated UVM output.
- Fixed clock port handling for `clk` and `clock` names.

## Validation
- 38 Python tests pass.
- Python compileall passes for Mverify and Mcore.
- Mcore `/health` endpoint returns HTTP 200.
- Generated UVM structure inspected using a synthetic valid DUT fixture.
- No VCS compile or functional simulation was performed in this build environment.

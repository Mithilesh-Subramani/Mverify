# Mverify 0.11.0

- Consolidated Mverify into one canonical Python package.
- Published Mcore's Python package at the repository root so `import mcore` works consistently.
- Added project-wide file classification for RTL, VHDL, filelists, constraints, project metadata, Tcl, documentation and support scripts.
- Added explicit topology evidence and optional EDA tool probing.
- Added desktop project explorer, source preview, metric cards and topology tab.
- Improved specification JSON review and approval workflow.
- Added packaging metadata, reproducible installation instructions and GitHub Actions test workflow.
- Removed Python bytecode, pytest caches and local test databases from tracked release content.
- Kept conservative UVM generation boundaries. The generated result is a scaffold, not protocol-functional verification.

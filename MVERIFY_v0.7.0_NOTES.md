# Mverify v0.7.0 — Analysis and UVM generator correction

## Included

- Added a conservative RTL semantic evidence pass for procedural block counts,
  candidate writes/reads, continuous assignments, and case-based state-machine candidates.
- Added semantic evidence to requirement-to-RTL mapping.
- Extracted surrounding text and numbered-heading candidates around normative requirement lines.
- Updated the UI to show semantic evidence and its limitations.
- Fixed generated SystemVerilog interface declarations so DUT port directions are not repeated as interface member declarations.
- Removed the generic random 32-bit smoke sequence. It was not a legal PCIe transaction model.
- Changed generated UVM output to a passive compile/topology scaffold. It does not instantiate active drivers or claim functional protocol verification.
- Removed duplicate standalone compilation of `mverify_items.sv`, because it is included by the generated UVM package.
- Added `GENERATION_STATUS.md` to each generated UVM project.
- Added regression tests for interface declarations, passive generation, file-list composition, and semantic evidence extraction.

## Validation

- Python test suite: 29 passed.
- Python compilation: checked by the test/runtime import path.
- A synthetic generated interface was inspected and now emits `logic signal;` rather than `input/output logic signal;`.
- Generated file list was inspected for package/include ordering and duplicate item compilation.

## Explicit limitations

- No VCS executable was available in this build environment. The generated project has NOT been compiled with the user's VCS installation.
- The RTL semantic pass is lexical and conservative. It is not a complete SystemVerilog AST, elaborator, or resolved driver-to-consumer graph.
- PCIe specification extraction is not yet a complete normative protocol knowledge engine. Extracted requirement lines and nearby context still need clause review.
- Generated UVM output is a compile/topology scaffold, not a functional PCIe UVM environment. Protocol-aware drivers, monitors, scoreboards, assertions, coverage and sequences require explicit interface semantics and approved protocol models.
- No PCIe compliance or functional pass result is claimed.

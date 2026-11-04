# Mverify v0.8.2 — UVM generated-source newline fix

- Fixed generated `tests/mverify_base_test.sv` and `GENERATION_STATUS.md` templates.
- Generated SystemVerilog now contains real line breaks instead of literal `\n` text.
- This fixes the malformed source that caused VCS to report a syntax error at the `uvm_component_utils` macro expansion.
- This is a source-generation fix. It does not add active PCIe pin-level stimulus or prove VCS compilation.

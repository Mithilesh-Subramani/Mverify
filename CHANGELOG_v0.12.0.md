# Mverify 0.12.0

## UVM generation
- Replaced unsafe name-grouped active drivers with a single top-level virtual interface.
- Connects every parsed DUT top-level port exactly once.
- Adds a passive monitor that samples every parsed non-clock port.
- Connects monitor analysis output to a scoreboard.
- Adds `uvm_top.print_topology()` in `end_of_elaboration_phase`.
- Adds a generated topology preview and selectable observation/scenario test stubs.
- Adds an explicit protocol sequence template. It is not compiled or enabled until signal mapping is reviewed.
- Adds VCS compile and run scripts.

## Desktop and Mcore
- Adds a simulator-log loader for UVM topology output.
- Shows generated topology preview in the UVM tab.
- Adds RTL indexing, RAG search and Mcore engineering-reasoning controls to the desktop GUI.
- Documents that current Mcore retrieval is local lexical retrieval, not vector embedding search.
- Adds a root-level Mcore API launcher.

## Verification and limitations
- Preserves the local-first workflow and optional Mcore architecture.
- Keeps all active DUT stimulus disabled by default. Port names do not prove protocol semantics.
- Generated test classes are observation/scenario stubs, not protocol-functional tests.
- No VCS/Questa compile or simulation result is claimed by this release.

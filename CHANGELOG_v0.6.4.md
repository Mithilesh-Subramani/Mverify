# Mverify v0.6.4

## Fixes
- Fixed the verification-plan crash caused by the UI expecting `decomposition` while the planner did not include it in each plan record.
- Added a safe UI fallback for older or incomplete saved plan records.
- Clarified that entering a PCIe specification revision only labels the selected revision for traceability; it does not load or interpret the specification document.

## Validation
- Python compilation passed.
- Automated tests: 26 passed.
- VCS compilation was not performed.

## Known limitation
The current planner produces requirement-derived draft test dimensions. It is not yet a complete PCIe protocol reasoning engine. A revision string alone cannot provide PCIe requirements. The applicable specification document, clause references, requirement review, and deeper protocol modelling are still required.

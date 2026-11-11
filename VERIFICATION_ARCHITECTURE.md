# Verification architecture

Mverify separates structural evidence from behavioral claims. `strategy_registry.select_strategy` gates active stimulus on a selected top, parsed port directions, the recognized WRR interface, and matching round/quota evidence in RTL. Unknown contracts continue through the existing assisted observation generator.

For WRR, `wrr_uvm_generator` emits one active UVM agent. The driver changes request, weight, acceptance, and reset controls on the falling edge. The monitor samples DUT outputs on rising edges. The scoreboard uses a linear scan and explicit software quota array, independent of the RTL parallel-prefix selector. It compares valid, index, and one-hot outputs per sample and updates its model only after an accepted grant. Assertions check one-hot grants, index consistency, active requests, and positive weights.

`simulator_backend` constructs argument lists, checks duplicate definitions and unresolved package imports, saves logs, applies timeouts, and reports compile and functional simulation states separately. VCD is the waveform fallback. Verdi starts without blocking Tkinter only after functional pass evidence and waveform validation.

Generation or compilation alone is not verification. See `TEST_RESULTS.md` for the stages exercised in this release environment.

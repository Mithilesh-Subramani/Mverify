# VCS and Verdi setup

Mverify discovers `vcs` and `verdi` on `PATH`, or uses `VCS_BIN` and `VERDI_BIN`. It leaves `SNPSLMD_LICENSE_FILE`, `LM_LICENSE_FILE`, and other license variables unchanged. Generated compile commands select UVM 1.2.

## Linux csh setup

```csh
source /tools/synopsys/cshrc
set path = (/tools/synopsys/verdi_supp/U-2023.03-SP1/bin /tools/synopsys/verdi/U-2023.03-SP1/bin $path)
rehash
which vcs
which verdi
vcs -ID
verdi -version
```

The pasted lines `setenv path` and `setenv {$path}` are incomplete csh commands. Use `set path = (...)` to add executable directories. Do not replace license settings while configuring PATH.

The supplied VCS diagnostic reaches `/tools/synopsys/vcs/U-2023.03/linux/bin/vcs1` but fails because `libelf.so.1` cannot be loaded. Check whether the compatible library is available:

```bash
ldconfig -p | grep 'libelf.so.1'
```

Ask the host administrator to install/provide the compatible `libelf.so.1` runtime or configure its supported library path. Do not substitute a different SONAME with a symlink. Recheck with `vcs -ID`. The supplied Verdi output also says the Verdi-Elite license is unavailable; ask the license administrator to confirm entitlement and server before automatic launch.

## Windows desktop and Linux tools

The backend runs local executables. Since the described tools are installed on Linux, start Mverify on that Linux host with the Synopsys environment loaded. Windows cannot execute `/tools/...` binaries directly. This release does not include remote source transfer/execution.

Each generated project writes `build/compile.log`, a simulation log, and a JSON report. Simulation passes only when process exit is zero, UVM has no errors/fatals, the completion marker appears, and the functional scoreboard emits `MVERIFY_FUNCTIONAL_PASS`. Verdi is launched only after that evidence and a minimally valid non-empty waveform.

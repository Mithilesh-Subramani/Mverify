from pathlib import Path
from mverify.core.uvm_generator import order_rtl_sources

def test_package_dependencies_are_compiled_before_modules(tmp_path):
    pkg=tmp_path/"pcie_pkg.sv"
    pkg.write_text("package pcie_pkg; typedef enum logic [1:0] {A,B} txn_kind_e; endpackage")
    decoder=tmp_path/"pcie_addr_decoder.sv"
    decoder.write_text("module pcie_addr_decoder(output pcie_pkg::txn_kind_e kind); endmodule")
    ordered, packages=order_rtl_sources([str(decoder),str(pkg)])
    assert ordered.index(str(pkg)) < ordered.index(str(decoder))
    assert "pcie_pkg" in packages

from mverify.core.testcase_engine import generate_testcases

def test_testcases_separate_generated_and_suggested():
    report={"selected_top":"dut","module_details":[{"name":"dut","ports":[{"name":"clk","direction":"input"},{"name":"rst_n","direction":"input"},{"name":"req_valid","direction":"input"},{"name":"req_ready","direction":"output"},{"name":"grant","direction":"output"}]}]}
    result=generate_testcases(report)
    assert result["generated"]
    assert result["suggested"]
    assert all(x["kind"]=="generated" for x in result["generated"])
    assert all(x["kind"]=="suggested" for x in result["suggested"])
    assert result["summary"]["functional_oracle_available"] is False

def test_approved_requirement_creates_suggestion():
    report={"selected_top":"dut","module_details":[{"name":"dut","ports":[{"name":"clk","direction":"input"},{"name":"data","direction":"input"}]}]}
    req=[{"requirement_id":"REQ-1","statement":"DUT shall accept data when ready is high","review_status":"approved"}]
    result=generate_testcases(report,req)
    assert any(x.get("requirement_id")=="REQ-1" for x in result["suggested"])

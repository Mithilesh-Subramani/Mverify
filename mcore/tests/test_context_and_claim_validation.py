from mcore.reasoning.context_builder import build_engineering_context
from mcore.reasoning.evaluation import validate_engineering_claims, downgrade_unsupported_claims


def test_context_builder_is_project_scoped_bounded_and_provenanced():
    context=build_engineering_context(project_id="project-a",task="explain output",
        project_context={"dut_top":"alu"},rtl_evidence={"dut_top":"alu","selected_module":{
            "name":"alu","source_file":"alu.sv","ports":[{"name":"result","direction":"output","width":"[7:0]"}]},
            "universal_design_model":{"schema":"mverify.udm.v1","modules":["alu"]}},
        retrieved_knowledge=[{"project_id":"project-a","source":"alu.sv","topic":"rtl_source","content":"result is assigned from the ALU operation","score":0.9},
                             {"project_id":"project-b","source":"secret.sv","content":"must not appear","score":1.0}],
        max_chars=10000)
    assert context["retrieval"]["scope"]=="project_only"
    assert all(item["project_id"]=="project-a" for item in context["evidence"])
    port=next(x for x in context["evidence"] if x["kind"]=="rtl_port")
    assert port["classification"]=="CONFIRMED_FROM_PARSER" and port["content_sha256"]
    assert all(len(x["id"])==27 for x in context["evidence"])


def test_claim_validation_downgrades_missing_and_cross_project_claims():
    evidence=[{"id":"ev_valid","project_id":"project-a","content":"output result width 8 bits",
               "module":"alu","symbol":"result","kind":"rtl_port"}]
    response={"confirmed_facts":[{"claim":"ALU result output has width 8 bits","classification":"CONFIRMED","evidence_ids":["ev_valid"]},
                                  {"claim":"DUT implements encryption","classification":"CONFIRMED","evidence_ids":["other-project"]}],
              "inferences":[],"unknowns":[]}
    report=validate_engineering_claims(response,evidence,"project-a")
    assert report["claims"]["supported"]==1 and report["unsupported_claims"]==1
    clean=downgrade_unsupported_claims(response,report)
    assert clean["confirmed_facts"][1]["classification"]=="UNKNOWN"
    assert report["engineering_correctness"]=="NOT_PROVEN"


def test_conflicting_fact_provenance_is_flagged():
    evidence=[{"id":"ev_in","project_id":"p","content":"input request","fact_key":"port:arb.request:direction","fact_value":"input"},
              {"id":"ev_out","project_id":"p","content":"output request","fact_key":"port:arb.request:direction","fact_value":"output"}]
    response={"confirmed_facts":[{"claim":"request is an input","classification":"CONFIRMED","evidence_ids":["ev_in"]}]}
    report=validate_engineering_claims(response,evidence,"p")
    assert report["contradicted_claims"]==1
    assert report["status"]=="ENGINEERING_REVIEW_REQUIRED"

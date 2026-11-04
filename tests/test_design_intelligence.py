from mverify.core.design_intelligence import build_dut_model, propose_architectures, generate_intelligence


def sample_report():
    return {
        'selected_top': 'pcie_top', 'top_candidates': ['pcie_top'],
        'module_details': [{'name':'pcie_top','source_file':'top.sv','ports':[
            {'name':'clk','direction':'input','width':1},
            {'name':'rst_n','direction':'input','width':1},
            {'name':'req_valid','direction':'input','width':1},
            {'name':'req_ready','direction':'output','width':1},
            {'name':'tx_data','direction':'output','width':128},
            {'name':'tx_valid','direction':'output','width':1},
            {'name':'tx_ack','direction':'input','width':1},
        ]}],
        'hierarchy': [{'parent':'pcie_top','child':'dll','instance':'u_dll'}],
        'feature_analysis': {'features':[{'feature':'Handshake','modules_involved':['pcie_top']}]},
        'semantic_analysis': {'modules':[{'module':'pcie_top','procedural_block_count':3,
            'state_machine_candidates':[{'selector':'state','case_labels':['IDLE','SEND']}],
            'write_candidates':['state','tx_valid'],'continuous_assignments':[]} ]},
        'architecture_discovery': {'protocol':{'value':'PCIe'}}
    }


def test_model_groups_actual_ports_and_state_evidence():
    model=build_dut_model(sample_report(), [], 'PCIe Base 4.0')
    groups={x['id']:x for x in model['interface_candidates']}
    assert 'request_stream' in groups
    assert 'req_valid' in groups['request_stream']['dut_inputs']
    assert model['state_machines'][0]['selector']=='state'
    assert model['hierarchy']['child_count']==1


def test_architecture_options_are_dut_specific_and_include_passive_fallback():
    model=build_dut_model(sample_report())
    options=propose_architectures(model)
    assert {x['id'] for x in options} >= {'layered','single_virtual','passive'}
    layered=next(x for x in options if x['id']=='layered')
    assert any(a['name']=='request_interface_agent' for a in layered['agents'])


def test_intelligence_changes_with_actual_interface_evidence():
    model=build_dut_model(sample_report())
    options=propose_architectures(model)
    result=generate_intelligence(model,options,[],False)
    assert result['evidence_snapshot']['dut']=='pcie_top'
    assert result['dut_specific_findings']
    assert result['architecture_recommendation']['id'] in {'layered','passive'}

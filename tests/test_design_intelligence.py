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
    assert options[0]['id'] in {'layered', 'coordinated_layered', 'passive_observation'}
    layered=next(x for x in options if x['id']=='layered')
    assert any(a['name']=='request_stream_agent' for a in layered['components'])


def test_intelligence_changes_with_actual_interface_evidence():
    model=build_dut_model(sample_report())
    options=propose_architectures(model)
    result=generate_intelligence(model,options,[],False)
    assert result['evidence_snapshot']['dut']=='pcie_top'
    assert result['dut_specific_findings']
    assert result['architecture_recommendation']['id'] in {x['id'] for x in options}


def test_simple_alu_gets_compact_architecture_not_pcie_layered_agents():
    report = {
        'selected_top': 'alu', 'top_candidates': ['alu'],
        'module_details': [{'name': 'alu', 'ports': [
            {'name': 'operand_a', 'direction': 'input', 'width': 32},
            {'name': 'operand_b', 'direction': 'input', 'width': 32},
            {'name': 'opcode', 'direction': 'input', 'width': 4},
            {'name': 'result', 'direction': 'output', 'width': 32},
            {'name': 'zero_flag', 'direction': 'output', 'width': 1},
        ]}],
        'hierarchy': [],
        'feature_analysis': {'features': []},
        'semantic_analysis': {'modules': [{'module': 'alu', 'procedural_block_count': 0,
            'state_machine_candidates': [], 'write_candidates': [], 'continuous_assignments': []}]},
    }
    model = build_dut_model(report)
    options = propose_architectures(model)
    assert len(options) == 1
    assert options[0]['id'] == 'combinational_unit'
    assert 'virtual_sequencer' not in str(options[0])
    assert any(c['name'] == 'directed_driver' for c in options[0]['components'])

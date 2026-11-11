"""DUT-specific verification reasoning. Local deterministic evidence + optional Ollama."""
from __future__ import annotations
import json, re, urllib.request, urllib.error
from collections import defaultdict

SIGNAL_GROUPS = {
    "clock_reset": [r"clk", r"clock", r"rst", r"reset"],
    "request_stream": [r"req", r"request", r"valid", r"ready", r"payload", r"data", r"last", r"keep", r"strb"],
    "completion_stream": [r"cpl", r"completion", r"rsp", r"response"],
    "tlp_packet": [r"tlp", r"fmt", r"tag", r"length", r"first_be", r"last_be"],
    "dll_control": [r"dllp", r"ack", r"nak", r"seq", r"replay", r"lcrc", r"crc", r"credit", r"fc_"],
    "phy_pipe": [r"pipe", r"phy", r"txdata", r"rxdata", r"txvalid", r"rxvalid", r"elecidle", r"powerdown", r"polarity"],
    "link_training": [r"ltssm", r"train", r"ordered_set", r"lane", r"link_up", r"link_state"],
    "backend_memory": [r"backend", r"dma", r"mem", r"addr", r"write", r"read", r"byte_enable"],
    "combinational_datapath": [r"operand", r"alu", r"opcode", r"result", r"carry", r"borrow", r"overflow", r"zero_flag", r"compare"],
    "interrupt_status": [r"interrupt", r"msi", r"msix", r"error", r"status", r"fatal"],
}

def _groups(ports):
    result=defaultdict(list)
    for p in ports:
        name=p.get('name','')
        low=name.lower()
        matched=[g for g, pats in SIGNAL_GROUPS.items() if any(re.search(x,low) for x in pats)]
        if not matched: matched=['unclassified']
        for g in matched: result[g].append({**p, 'direction':p.get('direction','unknown')})
    return dict(result)

def _top(report):
    top=report.get('selected_top')
    mods=report.get('module_details',[])
    if not top and report.get('top_candidates'): top=report['top_candidates'][0]
    return next((m for m in mods if m.get('name')==top), None)

def build_dut_model(report, mapped_requirements=None, spec_revision=''):
    top=_top(report) or {}
    ports=top.get('ports',[])
    groups=_groups(ports)
    features=report.get('feature_analysis',{}).get('features',[])
    sem=report.get('semantic_analysis',{}).get('modules',[])
    sem_by={m.get('module'):m for m in sem}
    top_sem=sem_by.get(top.get('name'),{})
    hierarchy=report.get('hierarchy',[])
    children=[e for e in hierarchy if e.get('parent')==top.get('name')]
    state_machines=top_sem.get('state_machine_candidates',[])
    reqs=mapped_requirements or []
    status_counts={}
    for r in reqs: status_counts[r.get('mapping_status','not_mapped')]=status_counts.get(r.get('mapping_status','not_mapped'),0)+1
    interfaces=[]
    for group, ps in groups.items():
        ins=[p['name'] for p in ps if p.get('direction')=='input']
        outs=[p['name'] for p in ps if p.get('direction')=='output']
        interfaces.append({'id':group,'name':group.replace('_',' ').title(),'signals':ps,'dut_inputs':ins,'dut_outputs':outs,
            'driver_candidate':bool(ins),'monitor_candidate':bool(outs),
            'confidence':'medium' if group!='unclassified' else 'low'})
    return {
      'dut_top':top.get('name','unknown'),'source_file':top.get('source_file',''),
      'port_count':len(ports),'ports':ports,'interface_candidates':interfaces,
      'hierarchy':{'direct_children':children,'child_count':len(children)},
      'features':features,'state_machines':state_machines,
      'semantic_evidence':{'procedural_blocks':top_sem.get('procedural_block_count',0),'write_candidates':top_sem.get('write_candidates',[]),'continuous_assignments':top_sem.get('continuous_assignments',[])},
      'requirement_mapping_counts':status_counts,'requirement_count':len(reqs),
      'specification_revision':spec_revision or 'not supplied',
      'analysis_gaps':[
        'Port-name grouping is a hypothesis. Confirm signal semantics and protocol direction before enabling a driver.',
        'The current scanner does not perform full SystemVerilog elaboration or resolve every instance connection.',
        'A pin-level PCIe PHY agent requires a real PIPE/PHY pin interface. A TLP or backend interface is not a serial PCIe pin interface.',
        'Specification clauses and parameter values must be imported and reviewed before compliance expectations are generated.'
      ]}

def propose_architectures(model):
    """Return architecture candidates sized to the observed DUT structure.

    Architecture count and topology are derived from interface groups, hierarchy,
    sequential logic and protocol feature evidence. Signal-name matches remain
    hypotheses and do not authorize active stimulus.
    """
    groups = {x['id']: x for x in model.get('interface_candidates', [])}
    active_groups = [g for g in groups if g not in ('clock_reset', 'unclassified')]
    features = {str(x).lower() for x in model.get('features', [])}
    fsm = model.get('state_machines', [])
    hierarchy_count = model.get('hierarchy', {}).get('child_count', 0)
    port_count = model.get('port_count', 0)
    sem = model.get('semantic_evidence', {})
    sequential = bool(fsm or sem.get('procedural_blocks', 0) or 'clock_reset' in groups)
    protocol_heavy = bool(features.intersection({
        'handshake', 'buffering', 'arbitration', 'integrity_check',
        'retry_recovery', 'credit_flow', 'packet_formatting',
        'backend_interface', 'clock_domain'
    }))

    def candidate(id, name, when, components, rationale, risks):
        return {
            'id': id, 'name': name, 'when_to_use': when,
            'components': components, 'advantages': rationale, 'risks': risks,
            'evidence': {
                'dut_top': model.get('dut_top'), 'port_count': port_count,
                'interface_groups': active_groups, 'direct_child_count': hierarchy_count,
                'sequential_candidate': sequential, 'state_machine_candidates': len(fsm),
                'protocol_feature_candidates': sorted(features),
            },
            'implementation_status': 'proposal_only_passive_scaffold_currently_generated',
        }

    passive_monitor = {'name': 'dut_monitor', 'role': 'Observe DUT pins and publish sampled transactions', 'mode': 'passive'}
    scoreboard = {'name': 'scoreboard', 'role': 'Compare observations with an independently approved reference model', 'mode': 'requires_reference_model'}
    reset_monitor = {'name': 'reset_monitor', 'role': 'Observe reset sequencing; do not drive unconfirmed polarity', 'mode': 'passive'}

    # A small combinational datapath does not need PCIe-style layered agents.
    if not sequential and not protocol_heavy and len(active_groups) <= 1 and hierarchy_count <= 2:
        return [candidate(
            'combinational_unit', 'Compact combinational DUT environment',
            'Use for a small combinational block such as an ALU, encoder, decoder or arithmetic unit.',
            [
                {'name': 'directed_driver', 'role': 'Apply reviewed operand and control vectors', 'mode': 'active_after_port_mapping'},
                passive_monitor, scoreboard,
            ],
            ['One compact transaction path; no virtual sequencer or protocol-layer agents',
             'Can use a reference function when the RTL operation and truth table are established'],
            ['Input-to-output mapping and combinational latency must be confirmed',
             'A reference model must be independently derived or reviewed'],
        )]

    # Sequential single-interface blocks need one agent and a state/reset monitor.
    if len(active_groups) <= 1 and not protocol_heavy and hierarchy_count <= 4:
        return [candidate(
            'single_interface', 'Single-interface sequential environment',
            'Use for a register block, counter, timer, controller or small state machine.',
            [
                {'name': 'dut_agent', 'role': 'One driver/sequencer and monitor for the confirmed DUT interface', 'mode': 'active_after_signal_mapping'},
                reset_monitor, scoreboard,
            ],
            ['Small topology matched to one functional interface',
             'State and reset checks can be added without unnecessary virtual sequencing'],
            ['Clock/reset semantics and legal state transitions need review',
             'No driver is enabled from signal names alone'],
        )]

    # Multiple independent protocol boundaries justify layered agents.
    layered_components = [reset_monitor]
    for group in active_groups:
        layered_components.append({
            'name': group + '_agent',
            'role': 'Candidate driver/monitor for the ' + group.replace('_', ' ') + ' boundary',
            'mode': 'active_after_interface_contract_review',
        })
    layered_components.extend([passive_monitor, scoreboard])
    options = [candidate(
        'layered', 'Layered multi-interface environment',
        'Use when the DUT has multiple independent interface groups or substantial protocol logic.',
        layered_components,
        ['Separates independently verified boundaries',
         'Supports per-interface backpressure, error injection and coverage'],
        ['Each interface needs resolved connections, clocking and protocol semantics'],
    )]
    if len(active_groups) >= 3 or hierarchy_count >= 6 or len(fsm) >= 2:
        options.append(candidate(
            'coordinated_layered', 'Layered environment with virtual-sequence coordination',
            'Use only when end-to-end scenarios must coordinate several agents or state machines.',
            layered_components + [{'name': 'virtual_sequencer', 'role': 'Coordinate approved sequences across agents', 'mode': 'enabled_after_agent_implementation'}],
            ['Coordinates cross-interface transactions and recovery scenarios',
             'Supports system-level scenarios across multiple protocol boundaries'],
            ['Higher implementation and debug cost',
             'Requires each underlying agent and transaction model to be implemented first'],
        ))
    options.append(candidate(
        'passive_observation', 'Passive observation-first environment',
        'Use when interface semantics or connectivity are not yet sufficiently resolved.',
        [reset_monitor, passive_monitor, scoreboard],
        ['Safe structural starting point', 'Does not drive unverified DUT inputs'],
        ['Cannot prove stimulus-response behavior without approved drivers and an oracle'],
    ))
    return options

def _ollama(prompt, model, url, timeout=90):
    payload=json.dumps({'model':model,'prompt':prompt,'stream':False,'format':'json'}).encode()
    req=urllib.request.Request(url.rstrip('/')+'/api/generate',data=payload,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as resp: data=json.loads(resp.read().decode())
    return data.get('response','')

def generate_intelligence(model, architectures, requirements, ollama_enabled=False, ollama_model='qwen2.5-coder:7b', ollama_url='http://localhost:11434'):
    """Produce a DUT-specific report. Local model is advisory; facts remain evidence-backed."""
    features=[f.get('feature') for f in model.get('features',[])]
    fsm=model.get('state_machines',[])
    groups=model.get('interface_candidates',[])
    evidence={
      'dut':model['dut_top'],'ports':model['port_count'],'features':features,
      'interfaces':[{'id':g['id'],'inputs':g['dut_inputs'],'outputs':g['dut_outputs']} for g in groups],
      'direct_children':[e.get('child') for e in model['hierarchy']['direct_children']],
      'fsm':fsm,'requirements':[{'id':r.get('requirement_id'),'statement':r.get('statement'),'status':r.get('mapping_status')} for r in requirements]
    }
    result={'dut_specific_findings':[], 'architecture_recommendation':None,'alternatives':architectures,
      'verification_gaps':model['analysis_gaps'],'evidence_snapshot':evidence,'reasoning_engine':'deterministic evidence analysis',
      'model_status':'not_used'}
    if model['port_count']==0:
        result['dut_specific_findings'].append('No top-level ports were parsed. Active pin-level stimulus cannot be designed until the top module and port declarations are resolved.')
    for g in groups:
        if g['id']!='unclassified':
            result['dut_specific_findings'].append('%s: %d candidate signals; DUT inputs=%d, outputs=%d.'%(g['name'],len(g['signals']),len(g['dut_inputs']),len(g['dut_outputs'])))
    if fsm:
        for s in fsm: result['dut_specific_findings'].append('State-machine candidate %s has %d case labels: %s.'%(s.get('selector'),len(s.get('case_labels',[])),', '.join(s.get('case_labels',[]))))
    if not features: result['dut_specific_findings'].append('No known feature patterns were detected. This is an analysis gap, not proof that the DUT has no functionality.')
    if ollama_enabled:
        prompt=('Act as a senior RTL design verification architect. Analyze only this JSON evidence. '
          'Do not invent PCIe compliance rules, signal semantics, timing, or missing RTL. '
          'Return JSON with keys: summary, recommended_architecture_id, rationale, dut_specific_test_priorities, '
          'signal_mapping_questions, risks, next_actions. State uncertainty. Select an architecture id only from options. '
          'Evidence:\n'+json.dumps({'model':evidence,'architectures':architectures,'requirements':evidence['requirements']},indent=2))
        try:
            raw=_ollama(prompt,ollama_model,ollama_url)
            advisory=json.loads(raw)
            result['local_model_analysis']=advisory
            result['reasoning_engine']='deterministic evidence + local Ollama advisory'
            result['model_status']='success'
            chosen=advisory.get('recommended_architecture_id')
            result['architecture_recommendation']=next((x for x in architectures if x['id']==chosen),None)
        except Exception as exc:
            result['model_status']='unavailable_or_invalid_response'
            result['model_error']=str(exc)
    if result['architecture_recommendation'] is None:
        # The first candidate is selected by DUT structure above. No fixed
        # PCIe-style architecture is imposed on a simple combinational block.
        result['architecture_recommendation']=architectures[0] if architectures else None
        result['recommendation_basis']='Evidence-based structural classification; review signal mappings and limitations.'
    return result

"""DUT-specific verification reasoning. Local deterministic evidence + optional Ollama."""
from __future__ import annotations
import json, re, urllib.request, urllib.error
from collections import defaultdict

SIGNAL_GROUPS = {
    "clock_reset": [r"clk", r"clock", r"rst", r"reset"],
    "request_stream": [r"req", r"request", r"valid", r"ready", r"payload", r"data", r"last", r"keep", r"strb"],
    "completion_stream": [r"cpl", r"completion", r"rsp", r"response"],
    "tlp_packet": [r"tlp", r"fmt", r"type", r"opcode", r"tag", r"length", r"first_be", r"last_be"],
    "dll_control": [r"dllp", r"ack", r"nak", r"seq", r"replay", r"lcrc", r"crc", r"credit", r"fc_"],
    "phy_pipe": [r"pipe", r"phy", r"txdata", r"rxdata", r"txvalid", r"rxvalid", r"elecidle", r"powerdown", r"polarity"],
    "link_training": [r"ltssm", r"train", r"ordered_set", r"lane", r"link_up", r"link_state"],
    "backend_memory": [r"backend", r"dma", r"mem", r"addr", r"write", r"read", r"byte_enable"],
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
    groups={x['id']:x for x in model.get('interface_candidates',[])}
    opts=[]
    def add(id,name,when,agents,pros,risks):
        opts.append({'id':id,'name':name,'when_to_use':when,'agents':agents,'advantages':pros,'risks':risks})
    base=[{'name':'clock_reset_agent','role':'Drive and monitor confirmed clock/reset pins','mode':'active_after_signal_confirmation'},
          {'name':'dut_observer','role':'Capture DUT status and state progression','mode':'passive'}]
    if 'request_stream' in groups or 'tlp_packet' in groups:
        base += [{'name':'request_interface_agent','role':'Drive DUT input request/packet interface and monitor handshake','mode':'active_after_protocol_mapping'},
                 {'name':'response_interface_agent','role':'Monitor DUT response/completion interface','mode':'passive'}]
    if 'dll_control' in groups:
        base += [{'name':'data_link_agent','role':'Drive/monitor confirmed ACK, NAK, sequence and flow-control pins','mode':'active_after_protocol_mapping'}]
    if 'phy_pipe' in groups or 'link_training' in groups:
        base += [{'name':'pipe_phy_agent','role':'Drive/monitor PIPE-level PHY interface and link training','mode':'active_after_pipe_model_review'}]
    if 'backend_memory' in groups:
        base += [{'name':'backend_memory_agent','role':'Model the DUT-facing backend request/response interface','mode':'active_after_handshake_mapping'}]
    add('layered','Layered interface agents', 'Use when the DUT exposes multiple independently verifiable interfaces.',base,
        ['Separates stimulus and checking by interface boundary','Supports independent backpressure and error injection'],
        ['Requires accurate signal direction, clocking and handshake mapping'])
    add('single_virtual','Single virtual-sequencer environment', 'Use when scenarios must coordinate requests, backend responses and link events.',
        base+[{'name':'virtual_sequencer','role':'Coordinate traffic across interface agents','mode':'active_after_agent_approval'}],
        ['Coordinates cross-interface scenarios','Good for end-to-end transaction flows'],
        ['More complex sequencing and reset synchronization'])
    add('passive','Passive observation-first environment','Use when interface semantics are not yet confirmed or the DUT is incomplete.',
        [{'name':'clock_reset_observer','role':'Observe clock/reset','mode':'passive'}, {'name':'protocol_monitors','role':'Observe candidate interfaces without driving them','mode':'passive'}, {'name':'state_progress_monitor','role':'Track observed FSM/status progress','mode':'passive'}],
        ['Safe first step; does not drive unverified pins','Useful to validate signal mapping'],
        ['Cannot prove stimulus-response behavior until active drivers are approved'])
    # Tailor alternatives based on discovered interfaces.
    if 'phy_pipe' not in groups:
        for opt in opts:
            opt['risks'].append('No PIPE/PHY interface was detected. Do not claim physical pin-level PCIe stimulus for this DUT top.')
    return opts

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
        # Prefer layered if multiple interfaces exist; otherwise passive until semantics are confirmed.
        nonempty=sum(1 for g in groups if g['id'] not in ('clock_reset','unclassified'))
        preferred='layered' if nonempty>=2 else 'passive'
        result['architecture_recommendation']=next(x for x in architectures if x['id']==preferred)
        result['recommendation_basis']='Deterministic interface-count heuristic; review alternatives.'
    return result

"""Evidence-based first-pass PCIe architecture discovery."""
from __future__ import annotations
import re

PCIe_TERMS = re.compile(r"\b(pcie|tlp|dllp|ltssm|pipe|lcrc|ecrc|replay|flow.?control)\b", re.I)
RULES = {
 "transaction_layer": [
  (r"\btlp_packet_t\b", "TLP packet type is used"),
  (r"\btlp_(?:valid|ready)\b", "TLP valid/ready interface is present"),
  (r"\breq_(?:valid|ready|map_addr|length_dw|requester_id|tag|first_be|last_be)\b", "Decoded transaction request interface is present"),
  (r"\brx_meta\b|\brx_data_present\b", "Decoded receive metadata/data interface is present"),
  (r"\bpcie_(?:tx_control|rx_control|tx_data_path|rx_data_path|completer)\b", "Transaction formatting, receive, or completion block is instantiated"),
 ],
 "data_link_layer": [
  (r"\bdll_packet_t\b", "DLL packet type is used"),
  (r"\blink_(?:tx|rx)_(?:valid|ready|packet)\b", "Packetized link TX/RX interface is present"),
  (r"\b(?:ack|nak|replay|sequence_error|crc_error)\b", "ACK/NAK, replay, sequence, or CRC logic evidence is present"),
  (r"\bpcie_(?:data_link|dll_tx|dll_rx|fc_tx|fc_rx|fc_dllp_tx)\b", "Data-link function block is instantiated"),
  (r"\bfc_(?:initialized|protocol_error|dllp|credits)\b", "Flow-control sideband or credit logic is present"),
 ],
 "physical_layer": [
  (r"\bltssm\b", "LTSSM signal or state model is present"),
  (r"\bpipe_(?:tx|rx|clk|reset|status|pclk)\b", "PIPE-like interface signal is present"),
  (r"\b(?:ordered_set|training_sequence|ts1|ts2|electrical_idle|receiver_detect)\b", "Physical-layer training/ordered-set evidence is present"),
  (r"\bpcie_(?:phy|pipe|ltssm)\w*\b", "PHY/PIPE/LTSSM block is instantiated"),
 ]}

def _hits(text, rules):
 return [description for pattern, description in rules if re.search(pattern,text,re.I)]

def discover_pcie(report: dict) -> dict:
 modules=report.get('module_details',[])
 names=[m.get('name','') for m in modules]
 hierarchy=report.get('hierarchy',[])
 text='\n'.join([m.get('name','')+' '+' '.join(p.get('name','')+' '+p.get('width','') for p in m.get('ports',[])) for m in modules])
 text += '\n'+'\n'.join(f"{e.get('parent','')} {e.get('child','')} {e.get('instance','')}" for e in hierarchy)
 text += '\n'+'\n'.join(report.get('_source_text',[]))
 protocol_hits=sorted(set(PCIe_TERMS.findall(text)))
 pcie_specific = bool(re.search(r'pcie[_:]|\btlp[_:]|\bdllp[_:]|\bltssm[_:]|\bpipe[_:]', text, re.I))
 is_pcie=bool(protocol_hits) or pcie_specific or any('pcie' in n.lower() for n in names)
 if not is_pcie:
  return {'protocol':{'value':'unknown','confidence':'low','evidence':[]},'device_role':{'value':'unknown','confidence':'low','evidence':[]},'generation':{'value':'unknown','confidence':'low','evidence':[],'note':'Generation cannot be inferred from generic TLP/DLL structure.'},'layers':{},'boundaries':[],'recommended_scope':[],'limitations':['No strong PCIe-specific structural evidence was found.']}
 layers={}
 for layer,rules in RULES.items():
  hits=_hits(text,rules)
  status='structural_evidence_found' if len(hits)>=3 else ('possible_or_partial_evidence' if hits else 'not_observed')
  confidence='high' if len(hits)>=3 else ('medium' if hits else 'low')
  layers[layer]={'status':status,'confidence':confidence,'evidence':hits,'interpretation':'Relevant structure is visible. Functional implementation is not proven.' if hits else 'No matching structural evidence was found in the scanned source.'}
 role_evidence=[]
 if re.search(r'\bbackend_(?:req|rsp)|\bCOMPLETER_ID\b|\bpcie_completer\b',text,re.I): role_evidence.append('Backend completion service or completer identity is exposed')
 if re.search(r'\breq_map_addr\b|\breq_requester_id\b|\breq_tag\b',text,re.I): role_evidence.append('Local transaction request interface is exposed')
 role='PCIe controller / endpoint-oriented function (tentative)' if role_evidence else 'unknown'
 boundaries=[]
 if re.search(r'\blink_(?:tx|rx)_(?:valid|ready|packet)\b|\bdll_packet_t\b',text,re.I):
  boundaries.append({'boundary':'Packetized link interface','interpretation':'The design exposes a packetized interface at or near the Data Link Layer boundary.','evidence':'link_tx/link_rx valid-ready packet signals or DLL packet type','external_side':'PHY/codec adapter is outside this interface unless separately included in hierarchy'})
 if re.search(r'\bpipe_(?:tx|rx|clk|reset|status|pclk)\b|\bltssm\b',text,re.I):
  boundaries.append({'boundary':'PIPE / Physical Layer interface','interpretation':'A PIPE-like or LTSSM interface is visible.','evidence':'PIPE/LTSSM signal pattern','external_side':'Requires manual confirmation of actual PHY integration'})
 recommendations=[
  {'area':'Transaction Layer','priority':'high','reason':'Verify request acceptance/rejection, TLP formatting, byte enables, tags, completions, and RX metadata/data alignment.'},
  {'area':'Data Link Layer','priority':'high','reason':'Verify sequence numbering, LCRC, ACK/NAK, replay, flow-control initialization, credits, and backpressure.'},
  {'area':'Physical Layer','priority':'conditional','reason':'Plan LTSSM, link training, speed/width negotiation, or PIPE checks only if these functions are inside the DUT boundary.'},
  {'area':'Cross-layer','priority':'high','reason':'Check TLP-to-DLL handoff, RX DLL-to-TL handoff, reset propagation, and end-to-end ready/valid behavior.'}]
 return {'protocol':{'value':'PCIe','confidence':'high' if len(protocol_hits)>=4 else 'medium','evidence':protocol_hits[:20]},'device_role':{'value':role,'confidence':'medium' if len(role_evidence)>=2 else 'low','evidence':role_evidence},'generation':{'value':'unknown','confidence':'low','evidence':[],'note':'TLP/DLL structure does not identify a PCIe generation. Require explicit specification or generation-specific evidence.'},'layers':layers,'boundaries':boundaries,'recommended_scope':recommendations,'limitations':['Static structural discovery only. Detected blocks are not proven functional.','A missing signal pattern does not prove that a layer is absent; names and coding styles can differ.','Macros, packages, interfaces, generate elaboration, parameter overrides, and conditional compilation can hide or alter structure.','PCIe generation and device role remain unknown unless explicit evidence supports them.']}

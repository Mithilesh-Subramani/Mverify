"""Native Mverify desktop workbench. Tkinter is used to avoid a browser runtime."""
from __future__ import annotations
import json, threading, traceback, urllib.request, urllib.error, hashlib
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from mverify.core.config import load_config
from mverify.core.logging_setup import configure_logging
from mverify.core.project_scanner import scan_project
from mverify.storage.database import initialize_database, save_scan
from mverify.core.spec_engine import extract_spec_text, extract_candidate_requirements, load_requirements_csv, map_requirements
from mverify.core.requirement_intelligence import apply_auto_triage
from mverify.core.design_intelligence import build_dut_model, propose_architectures, generate_intelligence
from mverify.core.uvm_generator import generate_uvm_project
from mverify.core.testcase_engine import generate_testcases

def _format_value(value, indent=0):
    """Render structured Mcore output as readable engineering notes."""
    pad="  "*indent
    if isinstance(value, dict):
        lines=[]
        for key,val in value.items():
            label=key.replace("_"," ").strip().capitalize()
            if isinstance(val,(dict,list)):
                lines.append(f"{pad}{label}:")
                lines.append(_format_value(val,indent+1))
            else:
                lines.append(f"{pad}{label}: {val}")
        return "\n".join(x for x in lines if x)
    if isinstance(value,list):
        if not value:return pad+"(none reported)"
        lines=[]
        for item in value:
            if isinstance(item,(dict,list)):
                lines.append(pad+"•")
                lines.append(_format_value(item,indent+1))
            else: lines.append(pad+"• "+str(item))
        return "\n".join(lines)
    return pad+str(value)

def format_mcore_response(data, raw=False):
    if raw:return json.dumps(data,indent=2,ensure_ascii=False)
    if not isinstance(data,dict):return str(data)
    if "results" in data and isinstance(data["results"],list):
        lines=["RAG RETRIEVAL RESULTS", "="*24]
        results=data["results"]
        if not results:lines.append("No matching indexed evidence was found.")
        for i,item in enumerate(results,1):
            lines += [f"\n{i}. {item.get('topic','Evidence')}",f"   Source: {item.get('source','unknown')}",
                      f"   Relevance score: {item.get('score','n/a')}",
                      "   Evidence:", "   "+str(item.get("content","")).replace("\n","\n   ")]
        return "\n".join(lines)
    result=data.get("result",data)
    if isinstance(result,dict):
        lines=["MCORE ENGINEERING ANALYSIS", "="*28]
        for key in ("design_understanding","confirmed_facts","inferences","assumptions","unknowns","requirement_analysis"):
            if result.get(key) is not None:
                lines += ["\n"+key.replace("_"," ").upper(), _format_value(result.get(key),1)]
        strategy=result.get("verification_strategy")
        if strategy:
            lines += ["\nVERIFICATION STRATEGY",_format_value(strategy,1)]
        for key in ("risks","validation_plan","questions_for_engineer"):
            if result.get(key):lines += ["\n"+key.replace("_"," ").upper(),_format_value(result[key],1)]
        confidence=result.get("confidence")
        if confidence:lines += ["\nCONFIDENCE",_format_value(confidence,1)]
        if data.get("retrieved_sources"):
            lines += ["\nRETRIEVED SOURCES",_format_value(data["retrieved_sources"],1)]
        lines += ["\nVALIDATION NOTE",str(data.get("validation_status","Review all claims against source RTL and specification."))]
        return "\n".join(lines)
    return _format_value(data)

class MverifyDesktop(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mverify | RTL Engineering Workbench")
        self.geometry("1450x900")
        self.minsize(1100, 700)
        self.config_data = load_config()
        configure_logging(self.config_data.log_dir)
        initialize_database(self.config_data.database_path)
        self.report = None; self.requirements = []; self.architectures = []
        self.model = None; self.intelligence = None; self.testcases = []; self.last_uvm_output = None
        self._build()
        self._log("Workspace ready. Analysis stays local to this machine.")

    def _build(self):
        style = ttk.Style(self)
        try: style.theme_use("clam")
        except tk.TclError: pass
        style.configure("AppTitle.TLabel", font=("TkDefaultFont", 20, "bold"))
        style.configure("Metric.TLabel", font=("TkDefaultFont", 15, "bold"))
        style.configure("Muted.TLabel", foreground="#64748b")
        root = ttk.Frame(self, padding=12); root.pack(fill="both", expand=True)
        header = ttk.Frame(root); header.pack(fill="x")
        ttk.Label(header, text="Mverify", style="AppTitle.TLabel").pack(side="left")
        ttk.Label(header, text="RTL DESIGN • STRUCTURAL INTELLIGENCE • VERIFICATION", style="Muted.TLabel").pack(side="left", padx=18, pady=(8,0))
        proj = ttk.LabelFrame(root, text="Active project", padding=8); proj.pack(fill="x", pady=(10,8))
        self.project_var = tk.StringVar()
        ttk.Entry(proj, textvariable=self.project_var).pack(side="left", fill="x", expand=True, padx=(0,6))
        ttk.Button(proj, text="Open project", command=self._browse).pack(side="left")
        self.top_var = tk.StringVar()
        ttk.Label(proj, text="DUT top").pack(side="left", padx=(12,4))
        ttk.Entry(proj, textvariable=self.top_var, width=22).pack(side="left")
        ttk.Button(proj, text="Scan design", command=self._scan).pack(side="left", padx=(8,0))
        self.progress = ttk.Progressbar(root, mode="indeterminate"); self.progress.pack(fill="x", pady=(0,8))
        self.metrics = ttk.Frame(root); self.metrics.pack(fill="x", pady=(0,8))
        self.metric_labels = {}
        for key, title in (("files","PROJECT FILES"),("modules","RTL MODULES"),("instances","HIERARCHY INSTANCES"),("warnings","ANALYSIS WARNINGS")):
            card = ttk.LabelFrame(self.metrics, text=title, padding=8); card.pack(side="left", fill="x", expand=True, padx=(0,6))
            lab = ttk.Label(card, text="—", style="Metric.TLabel"); lab.pack(anchor="w"); self.metric_labels[key] = lab
        panes = ttk.Panedwindow(root, orient="horizontal"); panes.pack(fill="both", expand=True)
        left = ttk.Frame(panes, padding=(0,0,8,0)); right = ttk.Frame(panes)
        panes.add(left, weight=1); panes.add(right, weight=4)
        ttk.Label(left,text="PROJECT EXPLORER",font=("TkDefaultFont",10,"bold")).pack(anchor="w")
        self.file_tree = ttk.Treeview(left, columns=("kind",), show="tree headings", selectmode="browse")
        self.file_tree.heading("#0",text="File"); self.file_tree.heading("kind",text="Type")
        self.file_tree.column("#0",width=230); self.file_tree.column("kind",width=90,stretch=False)
        self.file_tree.pack(fill="both",expand=True,pady=6); self.file_tree.bind("<<TreeviewSelect>>",self._open_selected_file)
        self.tabs = ttk.Notebook(right); self.tabs.pack(fill="both",expand=True)
        self.analysis_tab=ttk.Frame(self.tabs,padding=8); self.source_tab=ttk.Frame(self.tabs,padding=8)
        self.topology_tab=ttk.Frame(self.tabs,padding=8); self.spec_tab=ttk.Frame(self.tabs,padding=8)
        self.intel_tab=ttk.Frame(self.tabs,padding=8); self.uvm_tab=ttk.Frame(self.tabs,padding=8)
        self.tests_tab=ttk.Frame(self.tabs,padding=8); self.mcore_tab=ttk.Frame(self.tabs,padding=8)
        for tab,label in ((self.analysis_tab,"Analysis"),(self.source_tab,"RTL Source"),(self.topology_tab,"Topology"),(self.spec_tab,"Specification"),(self.intel_tab,"Verification Plan"),(self.uvm_tab,"UVM Generator"),(self.tests_tab,"Test Cases"),(self.mcore_tab,"Mcore")):
            self.tabs.add(tab,text=label)
        self.scan_text=self._text(self.analysis_tab)
        self.source_title=ttk.Label(self.source_tab,text="Select a source file in the project explorer",style="Muted.TLabel"); self.source_title.pack(anchor="w")
        self.source_text=self._text(self.source_tab)
        topo_bar=ttk.Frame(self.topology_tab); topo_bar.pack(fill="x")
        ttk.Label(topo_bar,text="RTL hierarchy, generated UVM topology and runtime simulator topology.",style="Muted.TLabel").pack(side="left")
        ttk.Button(topo_bar,text="Show generated UVM topology",command=self._show_generated_topology).pack(side="left",padx=5)
        ttk.Button(topo_bar,text="Load simulator log",command=self._load_uvm_log).pack(side="left",padx=5)
        self.topology_text=self._text(self.topology_tab)
        self._build_spec(); self._build_intel(); self._build_uvm(); self._build_tests(); self._build_mcore()
        activity=ttk.LabelFrame(root,text="Activity log",padding=5); activity.pack(fill="x",pady=(8,0))
        self.log=tk.Text(activity,height=4,wrap="word"); self.log.pack(fill="x")
        self.status=tk.StringVar(value="Ready | No project scanned")
        ttk.Label(root,textvariable=self.status,style="Muted.TLabel").pack(anchor="w",pady=(4,0))

    def _text(self,parent):
        f=ttk.Frame(parent); f.pack(fill="both",expand=True)
        w=tk.Text(f,wrap="none",font=("TkFixedFont",10),undo=False)
        sy=ttk.Scrollbar(f,orient="vertical",command=w.yview); sx=ttk.Scrollbar(f,orient="horizontal",command=w.xview)
        w.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
        w.grid(row=0,column=0,sticky="nsew"); sy.grid(row=0,column=1,sticky="ns"); sx.grid(row=1,column=0,sticky="ew")
        f.rowconfigure(0,weight=1); f.columnconfigure(0,weight=1)
        return w
    def _set(self,w,value,readonly=True):
        w.configure(state="normal"); w.delete("1.0","end"); w.insert("1.0",value)
        if readonly:w.configure(state="disabled")
    def _log(self,msg): self.log.insert("end",msg+"\n"); self.log.see("end")
    def _browse(self):
        p=filedialog.askdirectory(title="Select RTL project directory")
        if p:self.project_var.set(p)
    def _bg(self,label,fn,done):
        self.status.set(label); self.progress.start(10)
        def worker():
            try:r=fn(); err=None
            except Exception as e:r=None; err=f"{e}\n{traceback.format_exc()}"
            self.after(0,lambda:self._finish(label,r,err,done))
        threading.Thread(target=worker,daemon=True).start()
    def _finish(self,label,result,error,done):
        self.progress.stop()
        if error:
            self.status.set("Operation failed"); self._log(error); messagebox.showerror("Mverify",error.splitlines()[0])
        else:
            self.status.set("Ready"); done(result)
    def _scan(self):
        raw=self.project_var.get().strip()
        if not raw or not Path(raw).expanduser().is_dir():messagebox.showwarning("Project required","Select an existing project folder.");return
        path=Path(raw).expanduser().resolve(); top=self.top_var.get().strip() or None
        def work():
            r=scan_project(path,top); sid=save_scan(self.config_data.database_path,str(path),r); return r,sid
        def done(data):
            self.report,sid=data; summary=self.report.get("summary",{})
            for k,v in (("files",self.report.get("project_inventory",{}).get("total_files",summary.get("rtl_files",0))),("modules",summary.get("modules",0)),("instances",summary.get("hierarchy_instances",0)),("warnings",summary.get("warnings",0))):self.metric_labels[k].configure(text=str(v))
            self.top_var.set(self.report.get("selected_top") or (self.report.get("top_candidates") or [""])[0])
            self._populate_tree(path)
            self._set(self.scan_text,json.dumps({k:self.report.get(k) for k in ("project_dir","summary","project_inventory","build_inputs","source_selection","module_details","hierarchy","top_candidates","selected_top","warnings","elaboration","toolchain","analysis_scope","universal_design_model","adaptive_verification_plan")},indent=2))
            self._set(self.topology_text,json.dumps(self.report.get("topology",{}),indent=2))
            self._log(f"Scan {sid} complete: {summary.get('rtl_files',0)} RTL files, {summary.get('modules',0)} modules.")
            self.tabs.select(self.analysis_tab)
        self._bg("Scanning project…",work,done)
    def _populate_tree(self,root):
        self.file_tree.delete(*self.file_tree.get_children()); self.path_by_id={}
        inventory=self.report.get("project_inventory",{}).get("categories",{})
        for cat,details in inventory.items():
            parent=self.file_tree.insert("","end",text=cat.replace("_"," ").title(),values=(details.get("count",0),),open=True)
            for f in details.get("files",[]):
                rel=Path(f).relative_to(root).as_posix(); item=self.file_tree.insert(parent,"end",text=rel,values=(Path(f).suffix or "file",))
                self.path_by_id[item]=Path(f)
    def _open_selected_file(self,event=None):
        item=self.file_tree.focus(); path=getattr(self,"path_by_id",{}).get(item)
        if not path:return
        try:
            data=path.read_text(encoding="utf-8",errors="replace")
            if len(data)>1_000_000:data=data[:1_000_000]+"\n\n[Preview truncated at 1 MB]"
            self.source_title.configure(text=str(path)); self._set(self.source_text,data)
            self.tabs.select(self.source_tab)
        except OSError as e:messagebox.showerror("Cannot read file",str(e))
    def _build_spec(self):
        bar=ttk.Frame(self.spec_tab);bar.pack(fill="x")
        ttk.Button(bar,text="Load specification + auto compare",command=self._load_spec).pack(side="left")
        ttk.Button(bar,text="Re-run automatic comparison",command=self._auto_compare).pack(side="left",padx=6)
        ttk.Button(bar,text="Map approved requirements",command=self._map).pack(side="left")
        self.spec_status=ttk.Label(self.spec_tab,text="Scan the project before loading a specification.");self.spec_status.pack(anchor="w",pady=6)
        self.spec_text=self._text(self.spec_tab)
    def _load_spec(self):
        if not self.report:messagebox.showwarning("Scan first","Scan the RTL project first.");return
        p=filedialog.askopenfilename(filetypes=[("Specification","*.txt *.md *.rst *.csv *.pdf *.docx"),("All files","*.*")])
        if not p:return
        def work():
            path=Path(p); req=load_requirements_csv(path) if path.suffix.lower()==".csv" else extract_candidate_requirements(extract_spec_text(path),path.name)
            for x in req:x.setdefault("clause","")
            premap=map_requirements(req,self.report)
            reviewed=apply_auto_triage(req,premap)
            by_id={x.get("requirement_id"):x for x in premap}
            for row in reviewed:
                row["rtl_mapping"] = by_id.get(row.get("requirement_id"), {})
            return reviewed,premap
        def done(data):
            self.requirements,self.mapped=data;self.spec_path=p
            self._show_requirement_review()
            self._log(f"Loaded and automatically assessed {len(self.requirements)} requirement candidates from {Path(p).name}.")
        self._bg("Extracting and comparing specification to RTL…",work,done)
    def _show_requirement_review(self):
        counts={"approved":0,"needs_review":0,"rejected":0}
        for row in self.requirements: counts[row.get("review_status","needs_review")]=counts.get(row.get("review_status","needs_review"),0)+1
        self.spec_status.configure(text=(f"{len(self.requirements)} candidates | auto-approved: {counts['approved']} | "
                                         f"manual review: {counts['needs_review']} | rejected: {counts['rejected']} | "
                                         "Edit review_status for manual override, then map approved requirements."))
        self._set(self.spec_text,json.dumps(self.requirements,indent=2))
    def _auto_compare(self):
        if not self.report:messagebox.showwarning("Scan first","Scan RTL first.");return
        try: rows=json.loads(self.spec_text.get("1.0","end"))
        except json.JSONDecodeError as e:messagebox.showerror("Invalid JSON",str(e));return
        if not isinstance(rows,list):messagebox.showwarning("Invalid data","Requirement data must be a JSON list.");return
        premap=map_requirements(rows,self.report)
        reviewed=apply_auto_triage(rows,premap)
        by_id={x.get("requirement_id"):x for x in premap}
        for row in reviewed: row["rtl_mapping"]=by_id.get(row.get("requirement_id"),{})
        self.requirements=reviewed;self.mapped=premap;self._show_requirement_review()
        self._log("Automatic specification-to-RTL comparison completed. Approval is traceability triage, not proof of compliance.")
    def _map(self):
        if not self.report:messagebox.showwarning("Scan first","Scan RTL first.");return
        try: approved=json.loads(self.spec_text.get("1.0","end"))
        except json.JSONDecodeError as e:messagebox.showerror("Invalid JSON",str(e));return
        self.requirements=approved if isinstance(approved,list) else self.requirements
        selected=[dict(x) for x in self.requirements if x.get("review_status")=="approved"]
        if not selected:messagebox.showwarning("No approved requirements","Set review_status to approved for reviewed requirements.");return
        self.mapped=map_requirements(selected,self.report);self._set(self.spec_text,json.dumps(self.mapped,indent=2));self._log(f"Mapped {len(self.mapped)} approved requirements.")
    def _build_intel(self):
        bar=ttk.Frame(self.intel_tab);bar.pack(fill="x")
        ttk.Label(bar,text="Specification revision").pack(side="left");self.revision=tk.StringVar();ttk.Entry(bar,textvariable=self.revision,width=24).pack(side="left",padx=5)
        self.ollama=tk.BooleanVar(value=True);ttk.Checkbutton(bar,text="Use local Ollama",variable=self.ollama).pack(side="left",padx=5)
        self.model_name=tk.StringVar(value="qwen2.5-coder:14b");ttk.Entry(bar,textvariable=self.model_name,width=22).pack(side="left",padx=5)
        ttk.Button(bar,text="Analyze DUT",command=self._analyze).pack(side="left",padx=6)
        self.intel_text=self._text(self.intel_tab)
    def _analyze(self):
        if not self.report:messagebox.showwarning("Scan first","Scan the RTL project first.");return
        req=getattr(self,"mapped",[])
        def work():
            model=build_dut_model(self.report,req,self.revision.get()); arch=propose_architectures(model)
            intel=generate_intelligence(model,arch,req,self.ollama.get(),self.model_name.get());return model,arch,intel
        def done(data):
            self.model,self.architectures,self.intelligence=data;self._set(self.intel_text,json.dumps({"dut_model":self.model,"intelligence":self.intelligence},indent=2));self._refresh_arch()
            self._log("DUT-specific verification intelligence completed.")
        self._bg("Analyzing DUT…",work,done)
    def _build_uvm(self):
        bar=ttk.Frame(self.uvm_tab);bar.pack(fill="x")
        self.arch_combo=ttk.Combobox(bar,state="readonly",width=42);self.arch_combo.pack(side="left")
        ttk.Button(bar,text="Show architecture",command=self._show_arch).pack(side="left",padx=5)
        self.approve=tk.BooleanVar(value=False);ttk.Checkbutton(bar,text="I reviewed this topology proposal",variable=self.approve).pack(side="left",padx=5)
        ttk.Button(bar,text="Generate UVM scaffold",command=self._generate).pack(side="left",padx=5)
        ttk.Button(bar,text="Load simulator log",command=self._load_uvm_log).pack(side="left",padx=5)
        self.arch_text=self._text(self.uvm_tab)
    def _refresh_arch(self):
        names=[f"{x['id']} — {x['name']}" for x in self.architectures];self.arch_combo["values"]=names
        if names:self.arch_combo.current(0);self._show_arch()
    def _selected_arch(self):
        i=self.arch_combo.current();return self.architectures[i] if 0<=i<len(self.architectures) else None
    def _show_arch(self):
        a=self._selected_arch()
        if a:self._set(self.arch_text,json.dumps(a,indent=2))
    def _generate(self):
        a=self._selected_arch()
        if not self.report or not a:messagebox.showwarning("Analyze first","Scan and analyze the DUT first.");return
        if not self.approve.get():messagebox.showwarning("Review required","Review and approve the architecture proposal first.");return
        top=self.report.get("selected_top") or self.top_var.get().strip()
        if not top:messagebox.showerror("Top module required","Select a DUT top.");return
        out=Path(self.report["project_dir"])/"mverify_uvm_generated"
        def done(result):
            self.last_uvm_output=Path(result["output_dir"])
            preview=self.last_uvm_output/"uvm_topology.txt"
            content=preview.read_text() if preview.exists() else json.dumps(result,indent=2)
            self._set(self.arch_text,content)
            self._set(self.topology_text,content)
            self.tabs.select(self.topology_tab)
            self._log(f"Generated {result['files']} files and {result['tests']} selectable observation/scenario stubs in {result['output_dir']}.")
            messagebox.showinfo("UVM scaffold generated",f"{result['output_dir']}\nGenerated topology preview is now shown in the Topology tab. Runtime topology is printed by UVM when the test reaches end_of_elaboration_phase.")
        self._bg("Generating UVM scaffold…",
                 lambda:generate_uvm_project(self.report,out,top,architecture=a,requirements=self.requirements),
                 done)

    def _show_generated_topology(self):
        if not self.last_uvm_output:
            messagebox.showinfo("No generated topology","Generate a UVM scaffold first.")
            return
        preview=self.last_uvm_output/"uvm_topology.txt"
        if not preview.is_file():
            messagebox.showwarning("Topology preview missing",str(preview))
            return
        self._set(self.topology_text,preview.read_text(encoding="utf-8",errors="replace"))
        self.tabs.select(self.topology_tab)

    def _load_uvm_log(self):
        filename=filedialog.askopenfilename(title="Select VCS/Questa simulator log",
            filetypes=[("Simulation logs","*.log *.txt"),("All files","*.*")])
        if not filename:
            return
        try:
            lines=Path(filename).read_text(encoding="utf-8",errors="replace").splitlines()
            hits=[i for i,line in enumerate(lines) if "MVERIFY_TOPOLOGY" in line or "uvm_test_top" in line or "mverify_env" in line]
            if not hits:
                excerpt=("No UVM topology markers found. Check that the generated test compiled and ran.\n"
                         "Expected marker: MVERIFY_TOPOLOGY. Expected tree names include mverify_env and dut_agent.")
            else:
                lo=max(0,hits[0]-3); hi=min(len(lines),hits[-1]+120)
                excerpt="\n".join(lines[lo:hi])
                if len(excerpt)>50000: excerpt=excerpt[:50000]+"\n... log excerpt truncated ..."
            self._set(self.topology_text,excerpt)
            self.tabs.select(self.topology_tab)
            self._log(f"Loaded runtime UVM topology/log excerpt: {filename}")
        except OSError as exc:
            messagebox.showerror("Cannot read simulator log",str(exc))
    def _build_tests(self):
        bar=ttk.Frame(self.tests_tab);bar.pack(fill="x")
        ttk.Button(bar,text="Generate scenario catalog",command=self._generate_tests).pack(side="left")
        self.tests_text=self._text(self.tests_tab)
    def _generate_tests(self):
        if not self.report:messagebox.showwarning("Scan first","Scan the project first.");return
        self.testcases=generate_testcases(self.report);self._set(self.tests_text,json.dumps(self.testcases,indent=2));self._log(f"Generated {len(self.testcases)} candidate verification scenarios. Review before use.")
    def _build_mcore(self):
        bar=ttk.Frame(self.mcore_tab);bar.pack(fill="x")
        ttk.Label(bar,text="Mcore API").pack(side="left")
        self.mcore_url=tk.StringVar(value="http://127.0.0.1:8765")
        ttk.Entry(bar,textvariable=self.mcore_url,width=34).pack(side="left",padx=5)
        ttk.Button(bar,text="Check service",command=self._check_mcore).pack(side="left")
        ttk.Button(bar,text="Index RTL into RAG",command=self._index_rag).pack(side="left",padx=5)
        ttk.Label(self.mcore_tab,text="Ollama model").pack(anchor="w",pady=(8,2))
        self.mcore_model=tk.StringVar(value="qwen2.5-coder:14b")
        ttk.Entry(self.mcore_tab,textvariable=self.mcore_model,width=28).pack(anchor="w")
        ttk.Label(self.mcore_tab,text="RAG query").pack(anchor="w",pady=(8,2))
        querybar=ttk.Frame(self.mcore_tab);querybar.pack(fill="x")
        self.rag_query=tk.StringVar()
        ttk.Entry(querybar,textvariable=self.rag_query).pack(side="left",fill="x",expand=True)
        ttk.Button(querybar,text="Search RAG",command=self._search_rag).pack(side="left",padx=5)
        ttk.Button(querybar,text="Ask Mcore",command=self._ask_mcore).pack(side="left")
        ttk.Label(self.mcore_tab,text="Ask Mcore automatically retrieves evidence from the active project only. Hybrid vector + lexical retrieval is used when the Ollama embedding model is available; otherwise it falls back to lexical search. Search RAG is a retrieval diagnostic. Verify all conclusions against RTL and specifications.",style="Muted.TLabel").pack(anchor="w",pady=8)
        self.mcore_text=self._text(self.mcore_tab)

    def _mcore_request(self, endpoint, payload=None, timeout=30):
        url=self.mcore_url.get().rstrip("/") + endpoint
        data=None if payload is None else json.dumps(payload).encode("utf-8")
        req=urllib.request.Request(url,data=data,headers={"Content-Type":"application/json"} if data is not None else {})
        with urllib.request.urlopen(req,timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _check_mcore(self):
        def work():
            return self._mcore_request("/health",timeout=5)
        def done(data):
            self._set(self.mcore_text,json.dumps(data,indent=2))
            self._log("Mcore service connected.")
        self._bg("Checking Mcore…",work,done)

    def _project_id(self):
        root=str(Path(self.report.get("project_dir", "")).expanduser().resolve())
        return hashlib.sha256(root.encode("utf-8")).hexdigest()[:24]

    def _index_rag(self):
        if not self.report:
            messagebox.showwarning("Scan first","Scan the RTL project before indexing.")
            return
        files=self.report.get("files",[])
        project_id=self._project_id()
        def work():
            self._mcore_request("/knowledge/project/clear",{"project_id":project_id},timeout=15)
            results=[]
            for filename in files:
                path=Path(filename)
                try:
                    content=path.read_text(encoding="utf-8",errors="replace")
                except OSError:
                    continue
                if not content.strip():
                    continue
                payload={"source":str(path),"topic":"rtl_source","text":content[:2_000_000],"project_id":project_id}
                results.append({"file":str(path),"result":self._mcore_request("/knowledge/ingest",payload,timeout=30)})
            status=self._mcore_request("/knowledge/project/status",{"project_id":project_id},timeout=15)
            return {"indexed_files":len(results),"results":results,"project_status":status,
                    "note":"Project-scoped hybrid retrieval. Vector embeddings are used when the configured Ollama embedding model is available; otherwise lexical retrieval is used."}
        self._bg("Indexing RTL into Mcore knowledge store…",work,
                 lambda d:(self._set(self.mcore_text,json.dumps(d,indent=2)),self._log(f"RAG indexed {d['indexed_files']} RTL files.")))

    def _search_rag(self):
        query=self.rag_query.get().strip()
        if not query:
            messagebox.showwarning("Query required","Enter a question or search phrase.")
            return
        self._bg("Searching Mcore knowledge…",
                 lambda:self._mcore_request("/knowledge/search",{"query":query,"limit":10,"project_id":self._project_id()}),
                 lambda d:(self._set(self.mcore_text,format_mcore_response(d)),self._log("Mcore RAG search completed.")))

    def _ask_mcore(self):
        query=self.rag_query.get().strip()
        if not query:
            messagebox.showwarning("Question required","Enter an engineering question.")
            return
        if not self.report:
            messagebox.showwarning("Scan first","Scan the project first.")
            return
        project_id=self._project_id()
        def work():
            # Prevent stale cross-project context. If this project has never been
            # indexed, build its index automatically before asking the model.
            status=self._mcore_request("/knowledge/project/status",{"project_id":project_id},timeout=15)
            if not status.get("chunks"):
                self._mcore_request("/knowledge/project/clear",{"project_id":project_id},timeout=15)
                for filename in self.report.get("files",[]):
                    path=Path(filename)
                    try: content=path.read_text(encoding="utf-8",errors="replace")
                    except OSError: continue
                    if content.strip():
                        self._mcore_request("/knowledge/ingest",{
                            "source":str(path),"topic":"rtl_source","text":content[:2_000_000],
                            "project_id":project_id
                        },timeout=45)
            top=self.report.get("selected_top")
            modules=self.report.get("module_details",[])
            dut=next((m for m in modules if m.get("name")==top),{})
            evidence={
                "dut_top":top,
                "ports":dut.get("ports",[]),
                "selected_module":dut,
                "all_module_names":[m.get("name") for m in modules],
                "hierarchy":[e for e in self.report.get("hierarchy",[]) if e.get("parent")==top],
                "project_summary":self.report.get("summary",{}),
                "feature_analysis":self.report.get("feature_analysis",{}),
                "semantic_analysis":self.report.get("semantic_analysis",{}),
                "universal_design_model":self.report.get("universal_design_model",{}),
                "adaptive_verification_plan":self.report.get("adaptive_verification_plan",{}),
                "analysis_scope":self.report.get("analysis_scope",{}),
                "source_files":self.report.get("files",[]),
            }
            return self._mcore_request("/reason/engineering",{
                "task":query,"project_id":project_id,
                "project_context":{"project_dir":self.report.get("project_dir"),"project_id":project_id,"dut_top":top},
                "rtl_evidence":evidence,
                "spec_evidence":getattr(self,"mapped",[]),
                "tool_evidence":self.report.get("toolchain",{}),
                "knowledge_limit":12,
                "model":self.mcore_model.get().strip() or "qwen2.5-coder:14b"
            },timeout=360)
        self._bg("Mcore: retrieving current-project evidence and reasoning…",work,
                 lambda d:(self._set(self.mcore_text,format_mcore_response(d)),self._log("Mcore reasoning completed using current-project evidence.")))

if __name__ == "__main__":
    MverifyDesktop().mainloop()

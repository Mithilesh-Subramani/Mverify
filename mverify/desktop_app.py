"""Native Tk desktop application for Mverify. No browser or web server is used."""
from __future__ import annotations
import json, threading, traceback
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from mverify.core.config import load_config
from mverify.core.logging_setup import configure_logging
from mverify.core.project_scanner import scan_project
from mverify.storage.database import initialize_database, save_scan
from mverify.core.spec_engine import extract_spec_text, extract_candidate_requirements, load_requirements_csv, map_requirements
from mverify.core.design_intelligence import build_dut_model, propose_architectures, generate_intelligence
from mverify.core.uvm_generator import generate_uvm_project
from mverify.core.testcase_engine import generate_testcases

class MverifyDesktop(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mverify — RTL Design Verification")
        self.geometry("1180x820")
        self.minsize(900, 650)
        self.config_data = load_config()
        configure_logging(self.config_data.log_dir)
        initialize_database(self.config_data.database_path)
        self.report = None
        self.model = None
        self.architectures = []
        self.intelligence = None
        self.requirements = []
        self.spec_path = None
        self._build()
        self._log("Mverify desktop is ready. All analysis runs locally.")

    def _build(self):
        style=ttk.Style(self)
        try: style.theme_use("clam")
        except tk.TclError: pass
        style.configure("Title.TLabel", font=("TkDefaultFont", 18, "bold"))
        style.configure("Section.TLabel", font=("TkDefaultFont", 12, "bold"))
        outer=ttk.Frame(self, padding=12); outer.pack(fill="both", expand=True)
        ttk.Label(outer,text="Mverify",style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer,text="Native desktop RTL verification workbench • Local processing").pack(anchor="w",pady=(0,10))
        project=ttk.LabelFrame(outer,text="RTL project",padding=8); project.pack(fill="x")
        self.project_var=tk.StringVar()
        ttk.Entry(project,textvariable=self.project_var).pack(side="left",fill="x",expand=True,padx=(0,6))
        ttk.Button(project,text="Browse…",command=self._browse_project).pack(side="left")
        self.top_var=tk.StringVar()
        ttk.Label(project,text="Top module").pack(side="left",padx=(12,4))
        ttk.Entry(project,textvariable=self.top_var,width=24).pack(side="left")
        ttk.Button(project,text="Scan RTL",command=self._scan).pack(side="left",padx=(8,0))
        self.progress=ttk.Progressbar(outer,mode="indeterminate")
        self.progress.pack(fill="x",pady=6)
        self.tabs=ttk.Notebook(outer); self.tabs.pack(fill="both",expand=True)
        self.scan_tab=ttk.Frame(self.tabs,padding=8); self.spec_tab=ttk.Frame(self.tabs,padding=8)
        self.intel_tab=ttk.Frame(self.tabs,padding=8); self.uvm_tab=ttk.Frame(self.tabs,padding=8); self.tests_tab=ttk.Frame(self.tabs,padding=8); self.mcore_tab=ttk.Frame(self.tabs,padding=8)
        self.tabs.add(self.scan_tab,text="DUT Analysis")
        self.tabs.add(self.spec_tab,text="Specification")
        self.tabs.add(self.intel_tab,text="Verification Intelligence")
        self.tabs.add(self.uvm_tab,text="UVM Architecture")
        self.tabs.add(self.tests_tab,text="Test Cases")
        self.tabs.add(self.mcore_tab,text="Mcore AI Core")
        self.scan_text=self._text_tab(self.scan_tab)
        self.spec_text=self._text_tab(self.spec_tab)
        self.intel_text=self._text_tab(self.intel_tab)
        self._build_spec_controls(); self._build_intel_controls(); self._build_uvm_controls(); self._build_test_controls(); self._build_mcore_controls()
        log_frame=ttk.LabelFrame(outer,text="Activity",padding=5); log_frame.pack(fill="x",pady=(8,0))
        self.log=tk.Text(log_frame,height=5,wrap="word"); self.log.pack(fill="x")
        self.status=tk.StringVar(value="Ready")
        ttk.Label(outer,textvariable=self.status).pack(anchor="w")

    def _text_tab(self,parent):
        frame=ttk.Frame(parent); frame.pack(fill="both",expand=True)
        widget=tk.Text(frame,wrap="word",height=20)
        scroll=ttk.Scrollbar(frame,command=widget.yview); widget.configure(yscrollcommand=scroll.set)
        widget.pack(side="left",fill="both",expand=True); scroll.pack(side="right",fill="y")
        widget.configure(state="disabled")
        return widget

    def _set_text(self,w,value):
        w.configure(state="normal"); w.delete("1.0","end"); w.insert("1.0",value); w.configure(state="disabled")

    def _log(self,msg):
        self.log.insert("end",msg+"\n"); self.log.see("end")

    def _browse_project(self):
        p=filedialog.askdirectory(title="Select RTL project directory")
        if p: self.project_var.set(p)

    def _run_bg(self,label,fn,done):
        self.status.set(label); self.progress.start(10)
        def worker():
            try: result=fn(); error=None
            except Exception as exc: result=None; error=f"{exc}\n{traceback.format_exc()}"
            self.after(0,lambda:self._finish(label,result,error,done))
        threading.Thread(target=worker,daemon=True).start()

    def _finish(self,label,result,error,done):
        self.progress.stop()
        if error:
            self.status.set("Failed"); self._log(error)
            messagebox.showerror("Mverify error",error.splitlines()[0])
        else:
            self.status.set("Ready"); done(result)

    def _scan(self):
        raw=self.project_var.get().strip()
        if not raw: messagebox.showwarning("Project required","Select an RTL project folder first."); return
        path=Path(raw).expanduser()
        if not path.is_dir(): messagebox.showerror("Invalid folder","The selected RTL folder does not exist."); return
        def work():
            rep=scan_project(path,self.top_var.get().strip() or None)
            sid=save_scan(self.config_data.database_path,str(path),rep)
            return rep,sid
        def done(data):
            self.report,sid=data
            s=self.report.get("summary",{})
            self._set_text(self.scan_text,json.dumps({
                "scan_id":sid,"project":self.report.get("project_dir"),
                "selected_top":self.report.get("selected_top"),
                "top_candidates":self.report.get("top_candidates"),
                "summary":s,"feature_analysis":self.report.get("feature_analysis"),
                "semantic_analysis":self.report.get("semantic_analysis"),
                "architecture_discovery":self.report.get("architecture_discovery"),
                "hierarchy":self.report.get("hierarchy"),
                "warnings":self.report.get("warnings")},indent=2))
            self._log(f"RTL scan complete. Scan ID {sid}; {s.get('rtl_files',0)} RTL files.")
            self._refresh_top_options()
            self.tabs.select(self.scan_tab)
        self._run_bg("Scanning RTL…",work,done)

    def _build_spec_controls(self):
        bar=ttk.Frame(self.spec_tab); bar.pack(fill="x")
        ttk.Button(bar,text="Load specification…",command=self._load_spec).pack(side="left")
        ttk.Button(bar,text="Map reviewed requirements",command=self._map_requirements).pack(side="left",padx=6)
        self.spec_text.pack_info() if False else None
        self.spec_status=ttk.Label(self.spec_tab,text="Scan RTL before loading and mapping requirements.")
        self.spec_status.pack(anchor="w",pady=6)

    def _load_spec(self):
        if not self.report: messagebox.showwarning("Scan required","Scan the RTL project first."); return
        p=filedialog.askopenfilename(filetypes=[("Specifications","*.txt *.md *.rst *.csv *.pdf *.docx"),("All files","*.*")])
        if not p:return
        def work():
            path=Path(p)
            candidates=load_requirements_csv(path) if path.suffix.lower()==".csv" else extract_candidate_requirements(extract_spec_text(path),path.name)
            for x in candidates: x.setdefault("clause","")
            mapped=map_requirements(candidates,self.report)
            return candidates,mapped
        def done(data):
            self.requirements,self.mapped_candidates=data
            self.spec_path=p
            self._set_text(self.spec_text,json.dumps(self.requirements,indent=2))
            self.spec_status.configure(text=f"{len(self.requirements)} candidate requirements loaded. Review statuses in the JSON view; approve only verified candidates.")
            self._log(f"Loaded specification: {Path(p).name}; {len(self.requirements)} candidate requirements.")
        self._run_bg("Extracting specification…",work,done)

    def _map_requirements(self):
        if not self.report: messagebox.showwarning("Scan required","Scan RTL first."); return
        approved=[dict(x) for x in self.requirements if x.get("review_status")=="approved"]
        if not approved:
            messagebox.showwarning("No approved requirements","Set review_status to approved in the requirements JSON view is not editable yet. Use a CSV with review_status=approved, or approve requirements in the next editor release.")
            return
        self.mapped=map_requirements(approved,self.report)
        self._set_text(self.spec_text,json.dumps(self.mapped,indent=2))
        self._log(f"Mapped {len(self.mapped)} approved requirements.")

    def _build_intel_controls(self):
        bar=ttk.Frame(self.intel_tab); bar.pack(fill="x")
        self.revision=tk.StringVar()
        ttk.Label(bar,text="Spec revision").pack(side="left")
        ttk.Entry(bar,textvariable=self.revision,width=42).pack(side="left",padx=5)
        self.use_ollama=tk.BooleanVar(value=True)
        ttk.Checkbutton(bar,text="Use local Ollama",variable=self.use_ollama).pack(side="left",padx=5)
        self.model_name=tk.StringVar(value="qwen2.5-coder:7b")
        ttk.Entry(bar,textvariable=self.model_name,width=22).pack(side="left",padx=5)
        ttk.Button(bar,text="Analyze DUT & design strategy",command=self._analyze).pack(side="left",padx=5)

    def _analyze(self):
        if not self.report: messagebox.showwarning("Scan required","Scan the RTL project first."); return
        def work():
            mapped=getattr(self,"mapped",[])
            enriched=[{**x,"spec_revision":self.revision.get().strip()} for x in mapped]
            model=build_dut_model(self.report,enriched,self.revision.get().strip())
            arch=propose_architectures(model)
            intel=generate_intelligence(model,arch,enriched,self.use_ollama.get(),self.model_name.get().strip(),"http://localhost:11434")
            return model,arch,intel
        def done(data):
            self.model,self.architectures,self.intelligence=data
            self._set_text(self.intel_text,json.dumps({"dut_model":self.model,"architecture_options":self.architectures,"intelligence":self.intelligence},indent=2))
            self._refresh_architectures()
            self._log("DUT-specific verification analysis complete.")
            self.tabs.select(self.intel_tab)
        self._run_bg("Analyzing DUT…",work,done)

    def _build_uvm_controls(self):
        self.arch_var=tk.StringVar()
        ttk.Label(self.uvm_tab,text="Select architecture option",style="Section.TLabel").pack(anchor="w")
        self.arch_combo=ttk.Combobox(self.uvm_tab,textvariable=self.arch_var,state="readonly")
        self.arch_combo.pack(fill="x",pady=5)
        self.arch_detail=tk.Text(self.uvm_tab,height=16,wrap="word"); self.arch_detail.pack(fill="both",expand=True)
        self.arch_combo.bind("<<ComboboxSelected>>",self._show_arch)
        self.approve=tk.BooleanVar()
        ttk.Checkbutton(self.uvm_tab,text="I reviewed and approve this architecture",variable=self.approve).pack(anchor="w",pady=6)
        ttk.Button(self.uvm_tab,text="Generate approved UVM project",command=self._generate).pack(anchor="w")
        ttk.Label(self.uvm_tab,text="Generated code is an editable scaffold. Active pin-level PCIe stimulus requires confirmed interface models and signal semantics.",wraplength=850).pack(anchor="w",pady=8)


    def _build_test_controls(self):
        bar=ttk.Frame(self.tests_tab); bar.pack(fill="x")
        ttk.Button(bar,text="Generate test cases",command=self._generate_testcases).pack(side="left")
        ttk.Button(bar,text="Ask Mcore for suggestions",command=self._ask_mcore_suggestions).pack(side="left",padx=6)
        ttk.Button(bar,text="Queue example for Mcore review",command=self._queue_mcore_example).pack(side="left")
        ttk.Label(self.tests_tab,text="Generated = deterministic structural cases. Suggested = heuristic/AI proposals. Review expected results before treating any case as functional verification.",wraplength=900).pack(anchor="w",pady=6)
        self.test_text=self._text_tab(self.tests_tab)

    def _generate_testcases(self):
        if not self.report: messagebox.showwarning("Scan required","Scan the DUT project first."); return
        self.testcases=generate_testcases(self.report,getattr(self,"mapped",[]))
        self._set_text(self.test_text,json.dumps(self.testcases,indent=2))
        self._log("Generated %d structural test cases and %d suggested scenarios."%(len(self.testcases["generated"]),len(self.testcases["suggested"])))
        self.tabs.select(self.tests_tab)


    def _ask_mcore_suggestions(self):
        if not self.report: messagebox.showwarning("Scan required","Scan the DUT project first."); return
        import urllib.request
        cases=getattr(self,"testcases",None) or generate_testcases(self.report,getattr(self,"mapped",[]))
        evidence={"top":self.report.get("selected_top"),"summary":self.report.get("summary"),"modules":[{"name":m.get("name"),"ports":m.get("ports",[])} for m in self.report.get("module_details",[])],"hierarchy":self.report.get("hierarchy",[]),"test_cases":cases}
        prompt=("Act as a senior RTL verification engineer. Suggest additional DUT-specific test scenarios from the supplied evidence. Do not invent protocol semantics, numeric limits, or expected results. Return JSON with key suggestions containing objects with name, rationale, stimulus, checks, required_specification, confidence, and limitations. Mark all items as proposals requiring engineer review. Evidence:\n"+json.dumps(evidence,indent=2))
        url=self.mcore_url.get().rstrip("/")
        def work():
            payload=json.dumps({"prompt":prompt,"model":self.model_name.get().strip() or "qwen2.5-coder:7b"}).encode()
            req=urllib.request.Request(url+"/reason",data=payload,headers={"Content-Type":"application/json"})
            with urllib.request.urlopen(req,timeout=180) as r: return json.loads(r.read().decode())
        def done(data):
            self.mcore_suggestions=data.get("result",{}).get("suggestions",[])
            cases.setdefault("suggested",[]).extend([{**x,"id":"MCORE-%03d"%(i+1),"kind":"suggested","source":"Mcore/Qwen","status":"needs_engineer_review","oracle":"not_available_until_requirement_review"} for i,x in enumerate(self.mcore_suggestions)])
            self.testcases=cases; self._set_text(self.test_text,json.dumps(cases,indent=2)); self._log("Mcore returned %d additional suggested scenarios."%len(self.mcore_suggestions))
        self._run_bg("Requesting Mcore suggestions…",work,done)

    def _queue_mcore_example(self):
        if not getattr(self,"testcases",None): messagebox.showwarning("No test cases","Generate test cases first."); return
        import urllib.request
        url=self.mcore_url.get().rstrip("/")
        payload=json.dumps({"task_type":"verification_scenario_generation","source_project":self.report.get("project_dir") if self.report else None,"input":{"dut_top":self.report.get("selected_top") if self.report else None,"test_cases":self.testcases},"target":{"note":"Candidate scenario set; engineer review and simulation validation are still required."},"evidence":{"scan_summary":self.report.get("summary") if self.report else {},"requirements":getattr(self,"mapped",[])},"consent":False,"notes":"Queued from Mverify. Pending review; not eligible for training."}).encode()
        def work():
            req=urllib.request.Request(url+"/training/submit",data=payload,headers={"Content-Type":"application/json"})
            with urllib.request.urlopen(req,timeout=15) as r:return json.loads(r.read().decode())
        def done(data):
            self._log("Mcore training candidate queued: %s (%s)."%(data.get("id"),data.get("status")))
            messagebox.showinfo("Queued for review","Example saved to Mcore as pending review. It is not used for training.")
        self._run_bg("Queueing Mcore example…",work,done)

    def _build_mcore_controls(self):
        frame=ttk.Frame(self.mcore_tab); frame.pack(fill="x")
        ttk.Label(frame,text="Mcore local API").grid(row=0,column=0,sticky="w")
        self.mcore_url=tk.StringVar(value="http://127.0.0.1:8765")
        ttk.Entry(frame,textvariable=self.mcore_url,width=38).grid(row=0,column=1,padx=6)
        ttk.Button(frame,text="Check Mcore",command=self._check_mcore).grid(row=0,column=2)
        ttk.Label(self.mcore_tab,text="Mcore is a separate local service. It can use Qwen through Ollama for retrieval-grounded reasoning. Training examples remain pending review until explicitly approved.",wraplength=900).pack(anchor="w",pady=8)
        actions=ttk.Frame(self.mcore_tab); actions.pack(fill="x",pady=4)
        ttk.Button(actions,text="Refresh training queue",command=self._refresh_mcore_queue).pack(side="left")
        self.training_id=tk.StringVar()
        ttk.Label(actions,text="Example ID").pack(side="left",padx=(10,3))
        ttk.Entry(actions,textvariable=self.training_id,width=38).pack(side="left")
        self.training_consent=tk.BooleanVar(value=False)
        ttk.Checkbutton(actions,text="I approve data use for training",variable=self.training_consent).pack(side="left",padx=6)
        ttk.Button(actions,text="Approve selected",command=self._approve_mcore_example).pack(side="left")
        ttk.Button(actions,text="Reject selected",command=self._reject_mcore_example).pack(side="left",padx=4)
        self.mcore_text=self._text_tab(self.mcore_tab)

    def _check_mcore(self):
        import urllib.request
        url=self.mcore_url.get().rstrip("/")+"/health"
        def work():
            with urllib.request.urlopen(url,timeout=5) as r: return json.loads(r.read().decode())
        def done(data):
            self._set_text(self.mcore_text,json.dumps(data,indent=2)); self._log("Mcore API connection successful.")
        self._run_bg("Checking Mcore…",work,done)


    def _mcore_request(self,path,payload=None):
        import urllib.request
        url=self.mcore_url.get().rstrip("/") + path
        if payload is None:
            req=urllib.request.Request(url)
        else:
            req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req,timeout=30) as r:
            return json.loads(r.read().decode())

    def _refresh_mcore_queue(self):
        def work(): return self._mcore_request("/training/examples")
        def done(data):
            examples=data.get("examples",[])
            self._set_text(self.mcore_text,json.dumps(data,indent=2))
            self._log("Mcore training queue: %d examples."%len(examples))
        self._run_bg("Loading Mcore training queue…",work,done)

    def _approve_mcore_example(self):
        eid=self.training_id.get().strip()
        if not eid:
            messagebox.showwarning("Example ID required","Select or enter an example ID from the training queue."); return
        if not self.training_consent.get():
            messagebox.showwarning("Consent required","Confirm that this data is permitted for model training."); return
        def work(): return self._mcore_request("/training/approve",{"id":eid,"consent":True})
        def done(data):
            self._log("Mcore example approved for training dataset: "+eid)
            self._refresh_mcore_queue()
        self._run_bg("Approving Mcore example…",work,done)

    def _reject_mcore_example(self):
        eid=self.training_id.get().strip()
        if not eid:
            messagebox.showwarning("Example ID required","Enter an example ID from the training queue."); return
        def work(): return self._mcore_request("/training/reject",{"id":eid,"reason":"Rejected by engineer in Mverify."})
        def done(data):
            self._log("Mcore example rejected: "+eid)
            self._refresh_mcore_queue()
        self._run_bg("Rejecting Mcore example…",work,done)

    def _refresh_top_options(self):
        if self.report and self.report.get("selected_top"): self.top_var.set(self.report["selected_top"])

    def _refresh_architectures(self):
        names=[f"{x['id']} — {x['name']}" for x in self.architectures]
        self.arch_combo["values"]=names
        if names:self.arch_combo.current(0); self._show_arch()

    def _selected_arch(self):
        idx=self.arch_combo.current()
        return self.architectures[idx] if 0<=idx<len(self.architectures) else None

    def _show_arch(self,event=None):
        a=self._selected_arch()
        if not a:return
        self.arch_detail.delete("1.0","end")
        self.arch_detail.insert("1.0",json.dumps(a,indent=2))

    def _generate(self):
        arch=self._selected_arch()
        if not self.report or not arch: messagebox.showwarning("Analysis required","Scan and analyze the DUT first."); return
        if not self.approve.get(): messagebox.showwarning("Approval required","Review and approve the architecture first."); return
        top=self.report.get("selected_top") or (self.report.get("top_candidates") or [None])[0]
        if not top: messagebox.showerror("Top module missing","Select a DUT top module and scan again."); return
        out=Path(self.report["project_dir"])/"mverify_uvm_generated"
        def work(): return generate_uvm_project(self.report,out,top,architecture=arch)
        def done(r):
            self._log(f"Generated {r['files']} files at {r['output_dir']}")
            messagebox.showinfo("UVM project generated",f"Output:\n{r['output_dir']}\nFiles: {r['files']}")
        self._run_bg("Generating UVM project…",work,done)

if __name__=="__main__":
    app=MverifyDesktop()
    app.mainloop()

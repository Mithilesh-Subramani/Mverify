"""Optional QLoRA/SFT starter for approved Mcore JSONL.

Requires separately installed torch, transformers, datasets, peft, trl and bitsandbytes.
This script is deliberately not invoked by the API. Use a compatible base model and
run evaluation before registering any resulting adapter.
"""
import argparse, json
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig
from trl import SFTTrainer, SFTConfig

def main():
 p=argparse.ArgumentParser(); p.add_argument('--base-model',required=True); p.add_argument('--dataset',required=True); p.add_argument('--output',required=True); p.add_argument('--max-seq-length',type=int,default=2048); a=p.parse_args()
 def format_row(row):
  return {"text":"### Engineering task\\n"+json.dumps(row.get('input',{}),ensure_ascii=False)+"\\n### Approved target\\n"+json.dumps(row.get('target',{}),ensure_ascii=False)+"\\n### Evidence\\n"+json.dumps(row.get('evidence',{}),ensure_ascii=False)}
 ds=load_dataset('json',data_files=a.dataset,split='train').map(format_row)
 tok=AutoTokenizer.from_pretrained(a.base_model,trust_remote_code=False)
 if tok.pad_token is None:tok.pad_token=tok.eos_token
 q=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_compute_dtype='bfloat16',bnb_4bit_use_double_quant=True)
 model=AutoModelForCausalLM.from_pretrained(a.base_model,quantization_config=q,device_map='auto',trust_remote_code=False)
 cfg=SFTConfig(output_dir=a.output,max_seq_length=a.max_seq_length,per_device_train_batch_size=1,gradient_accumulation_steps=8,learning_rate=2e-4,num_train_epochs=1,logging_steps=10,save_steps=100,report_to='none')
 trainer=SFTTrainer(model=model,args=cfg,train_dataset=ds,processing_class=tok,peft_config=LoraConfig(r=16,lora_alpha=32,lora_dropout=0.05,target_modules='all-linear',task_type='CAUSAL_LM'))
 trainer.train(); trainer.save_model(a.output); tok.save_pretrained(a.output)
 print('Adapter saved. Run the Mcore benchmark and regression suite before deployment.')
if __name__=='__main__':main()

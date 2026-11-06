import os,json,time
os.environ.setdefault('PYTORCH_ENABLE_MPS_FALLBACK','1')
from pathlib import Path
import torch
from transformers import AutoConfig,AutoTokenizer,Qwen3_5ForCausalLM
R=Path(__file__).resolve().parent
ID='Qwen/Qwen3.5-0.8B';REV='2fc06364715b967f1860aea9cf38778875588b17'
def load():
    torch.set_grad_enabled(False);torch.set_num_threads(8);torch.manual_seed(314159)
    t=AutoTokenizer.from_pretrained(ID,revision=REV)
    c=AutoConfig.from_pretrained(ID,revision=REV).text_config;c._attn_implementation='eager'
    m=Qwen3_5ForCausalLM(c).eval();m.requires_grad_(False)
    return m,t

def prefix(t,q):return t.apply_chat_template([{'role':'user','content':q}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
def generate(m,t,q):
    x=t(prefix(t,q),return_tensors='pt').to(m.device);start=time.time()
    y=m.generate(**x,do_sample=False,max_new_tokens=96,pad_token_id=t.eos_token_id,eos_token_id=t.eos_token_id)
    ids=y[0,x.input_ids.shape[-1]:]
    return {'text':t.decode(ids,skip_special_tokens=True),'tokens':len(ids),'ended':int(ids[-1])==t.eos_token_id,'seconds':round(time.time()-start,2)}
if __name__=='__main__':
    m,t=load();m.to('mps' if torch.backends.mps.is_available() else 'cpu')
    out=[]
    for case in json.loads((R/'problems.json').read_text()):
        row={'model':'random','id':case['id'],**generate(m,t,case['prompt'])};out.append(row)
        (R/'random.json').write_text(json.dumps(out,indent=2));print(case['id'],flush=True)

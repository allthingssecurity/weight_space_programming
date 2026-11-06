"""Bounded, gradient-free edits of RANDOM Qwen text weights. Never loads a pretrained model."""
import os,json,time,hashlib
from pathlib import Path
os.environ.setdefault('PYTORCH_ENABLE_MPS_FALLBACK','1')
import torch
from transformers import AutoConfig,AutoTokenizer,Qwen3_5ForCausalLM
from safetensors.torch import save_file
R=Path(__file__).resolve().parent
ID='Qwen/Qwen3.5-0.8B'; REV='2fc06364715b967f1860aea9cf38778875588b17'
# Written before any outputs were inspected. Not fed to the edit construction.
TESTS=[
 {'id':'fae','prompt':'In ABAP, a SELECT uses FOR ALL ENTRIES IN lt_keys. What happens if lt_keys is empty? Explain the risk and show a guard.', 'criterion':'Explains that the WHERE condition is ignored when the driver is empty; checks IS NOT INITIAL before SELECT.'},
 {'id':'table','prompt':'An ABAP cache needs frequent lookup by a complete unique key, no positional access, and no ordering. Which internal table category fits and why?', 'criterion':'Recommends HASHED TABLE and explains full unique-key access.'},
 {'id':'mutation','prompt':'In ABAP, explain how LOOP AT itab INTO DATA(wa) differs from LOOP AT itab ASSIGNING FIELD-SYMBOL(<row>) when a component is changed inside the loop.', 'criterion':'INTO copies to a work area; ASSIGNING aliases the table row; changing the work area alone does not update the table.'},
 {'id':'search','prompt':'Review this ABAP: SORT lt_rows BY a b. READ TABLE lt_rows WITH KEY b = 7 BINARY SEARCH. Is it reliable? Explain and propose a correction.', 'criterion':'Binary search on b alone does not match ascending leading sort key a,b; sort by b or use a matching key/access method.'},
 {'id':'code_sum','prompt':'Write an ABAP method body that receives it_values TYPE STANDARD TABLE OF i WITH EMPTY KEY and returns rv_sum TYPE i, summing only positive entries. No database access.', 'criterion':'Initializes sum, iterates input, filters > 0, accumulates; valid ABAP syntax.'},
 {'id':'code_dedupe','prompt':'Write ABAP that takes an existing standard table lt_numbers of integers, sorts it ascending, then removes duplicate values. Explain the necessary order of the operations.', 'criterion':'SORT lt_numbers followed by DELETE ADJACENT DUPLICATES FROM lt_numbers; explains adjacency.'},
 {'id':'transfer','prompt':'An ABAP developer replaces a copied work area with a field symbol for performance. Later code changes a field on it, and previously unchanged table contents now change too. Diagnose the semantic regression.', 'criterion':'Recognizes aliasing versus copying and explains mutation of the original row.'},
 {'id':'english','prompt':'Explain in one sentence what a variable is in programming.', 'criterion':'A coherent basic definition; language sanity check.'},
]
(R/'tests.json').write_text(json.dumps(TESTS,indent=2))
torch.set_grad_enabled(False);torch.set_num_threads(8);torch.manual_seed(314159)
tok=AutoTokenizer.from_pretrained(ID,revision=REV)
cfg=AutoConfig.from_pretrained(ID,revision=REV).text_config
cfg._attn_implementation='eager'
model=Qwen3_5ForCausalLM(cfg).eval() # Random initialization, NOT from_pretrained.
model.requires_grad_(False)
device='mps' if torch.backends.mps.is_available() else 'cpu'
model.to(device)
print('Random model initialized:',sum(p.numel() for p in model.parameters()),flush=True)

def inputs(text):
    s=tok.apply_chat_template([{'role':'user','content':text}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
    return tok(s,return_tensors='pt').to(device)

def generate(q):
    x=inputs(q);t=time.time()
    y=model.generate(**x,do_sample=False,max_new_tokens=96,pad_token_id=tok.eos_token_id)
    ids=y[0,x.input_ids.shape[1]:]
    return {'text':tok.decode(ids,skip_special_tokens=True),'ids':ids.cpu().tolist(),'tokens':len(ids),'seconds':round(time.time()-t,2)}
# Hand-specified ABAP vocabulary, not answers to test questions.
lexicon=['DATA','TYPES','METHOD','ENDMETHOD','CLASS','ENDCLASS','IF','ENDIF','LOOP','ENDLOOP','RETURN','VALUE','TYPE','TABLE','WITH','KEY','IMPORTING','RETURNING','SELECT','FROM','WHERE','INTO','ASSIGNING','READ','SORT','DELETE','INITIAL','STANDARD','SORTED','HASHED','UNIQUE','FIELD-SYMBOL','sy-subrc','ABAP']
ids=sorted({i for s in lexicon for i in tok.encode(s,add_special_tokens=False)})
E=model.model.embed_tokens.weight
old_rows=E[ids].clone()
proj=model.model.layers[15].mlp.down_proj
old_W=proj.weight.clone()
xs=[];hs=[]
# Generic forward probes, no correct answers, loss, fitting, or held-out prompts.
for q in ['Write ABAP code.','Explain ABAP programming.','Review a program.','Describe a method.']:
    def pre(m,a):xs.append(a[0].detach().float().cpu().reshape(-1,a[0].shape[-1]))
    def post(m,a,o):hs.append((o[0] if isinstance(o,tuple) else o).detach().float().cpu())
    handles=[proj.register_forward_pre_hook(pre),model.model.layers[15].register_forward_hook(post)]
    model(**inputs(q),use_cache=False,logits_to_keep=1)
    for h in handles:h.remove()
X=torch.cat(xs);mu=X.mean(0);ix=(mu.abs()/(X.std(0)+1e-6)).topk(64).indices
# In a random model these output-token vectors encode identities, not learned semantics.
d=old_rows.mean(0).cpu();d=d/d.norm()
scale=torch.cat([h.reshape(-1,h.shape[-1]) for h in hs]).norm(dim=-1).mean()
delta=scale*d[:,None]*mu[ix][None,:]/mu[ix].square().sum()
save_file({'columns':ix.contiguous(),'delta':delta.contiguous(),'lexical_token_ids':torch.tensor(ids)},str(R/'patch.safetensors'))
conditions=[('random',0,1),('residual_1',1,1),('residual_3',3,1),('lexical_3',0,3),('combined',1,3)]
meta={'model_architecture':ID,'config_tokenizer_revision':REV,'seed':314159,'parameters':sum(p.numel() for p in model.parameters()),'pretrained_weights_loaded':False,'tokenizer_is_preexisting':True,'gradient_enabled':False,'training':False,'device':device,'dtype':'float32','conditions':conditions,'lexicon':lexicon,'lexical_rows':len(ids),'sparse_edit_elements':delta.numel(),'max_new_tokens':96,'do_sample':False,'test_sha256':hashlib.sha256((R/'tests.json').read_bytes()).hexdigest()}
(R/'metadata.json').write_text(json.dumps(meta,indent=2))
results=[]
for name,strength,boost in conditions:
    proj.weight.copy_(old_W);proj.weight[:,ix.to(device)]=old_W[:,ix.to(device)]+strength*delta.to(device)
    E[ids]=old_rows*boost
    for item in TESTS:
        out={'condition':name,'test_id':item['id'],'prompt':item['prompt'],**generate(item['prompt'])}
        results.append(out);(R/'results.json').write_text(json.dumps(results,indent=2))
        print(json.dumps({k:v for k,v in out.items() if k!='ids'}),flush=True)
print('Completed all fixed conditions.',flush=True)

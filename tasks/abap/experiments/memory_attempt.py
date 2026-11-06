"""Direct gated associative-memory writes into the last MLP of random Qwen.
No optimizer or loss minimization. Reference examples are used explicitly.
This is supervised memory installation, NOT zero-data learning or pretrained expertise.
"""
import os,json,time,argparse
from pathlib import Path
os.environ.setdefault('PYTORCH_ENABLE_MPS_FALLBACK','1')
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer,AutoConfig,Qwen3_5ForCausalLM
from safetensors.torch import save_file
ap=argparse.ArgumentParser();ap.add_argument('--uniform',action='store_true');ap.add_argument('--expanded',action='store_true');ap.add_argument('--refined',action='store_true');ap.add_argument('--affine',action='store_true');ap.add_argument('--soft',action='store_true');args=ap.parse_args()
R=Path(__file__).resolve().parent/('soft_memory' if args.soft else 'affine_memory' if args.affine else 'refined_memory' if args.refined else 'expanded_memory' if args.expanded else 'uniform_memory' if args.uniform else 'direct_memory');R.mkdir(exist_ok=True)
ID='Qwen/Qwen3.5-0.8B';REV='2fc06364715b967f1860aea9cf38778875588b17'
BANK=[
('Explain empty FOR ALL ENTRIES in ABAP.', 'If the driver table is empty, the WHERE condition is ignored. Guard the SELECT with IF lt_keys IS NOT INITIAL. Otherwise an unexpectedly large result may be read.'),
('Which ABAP table supports fast full unique-key lookup?', 'A HASHED TABLE WITH UNIQUE KEY is suitable for frequent complete-key lookups when primary index access and ordering are unnecessary.'),
('Compare INTO and ASSIGNING in an ABAP table loop.', 'INTO copies a row into a work area. ASSIGNING makes the field symbol refer to the original row. Changing the work area alone does not change the table; changing the assigned row does.'),
('What ordering does ABAP BINARY SEARCH require?', 'The standard table must be sorted ascending by the search key. Searching only a non-leading component of a different sort key is unreliable. Sort by the searched fields or use a matching table key.'),
('Show ABAP to add positive integers from it_values to rv_sum.', 'CLEAR rv_sum.\nLOOP AT it_values INTO DATA(lv_value).\n  IF lv_value > 0.\n    rv_sum = rv_sum + lv_value.\n  ENDIF.\nENDLOOP.'),
('Remove duplicate integers from lt_numbers in ABAP.', 'SORT lt_numbers.\nDELETE ADJACENT DUPLICATES FROM lt_numbers.\nSorting groups equal values together so adjacent duplicate removal can remove them.'),
('What is a variable?', 'A variable is a named storage location or binding that holds a value used by a program.'),
]

if args.expanded:
    alternatives=[
      ['What is the empty-driver hazard of FOR ALL ENTRIES?', 'How should I guard an ABAP FOR ALL ENTRIES SELECT?', 'Why can FOR ALL ENTRIES unexpectedly read every database row?'],
      ['Which internal table is best for unique-key caching?', 'Explain when to use HASHED TABLE.', 'I need fast complete unique-key access without ordering. Which ABAP table should I use?'],
      ['Does changing an INTO work area update the original internal table?', 'What is the effect of modifying an ASSIGNING field symbol?', 'Explain copied rows versus aliased rows in an ABAP loop.'],
      ['Explain the sorting prerequisite of BINARY SEARCH.', 'Why is binary search unreliable with the wrong field ordering?', 'What must match between SORT and READ TABLE BINARY SEARCH?'],
      ['Show a loop adding only positive numbers in ABAP.', 'Sum values greater than zero from it_values into rv_sum.', 'Give ABAP code for positive-only integer accumulation.'],
      ['How do I deduplicate a standard integer table?', 'Give ABAP code to remove adjacent equal integers after sorting.', 'Explain SORT then DELETE ADJACENT DUPLICATES.'],
      ['Define a programming variable.', 'What does the term variable mean in programming?', 'Explain named storage for program values.'],
    ]
    original_bank=list(BANK)
    BANK += [(q,answer) for (_,answer),qs in zip(original_bank,alternatives) for q in qs]

# Deliberately contrasting and compositional questions. Never used to construct memory weights.
UNSEEN=[
('empty_rephrase','The keys table has zero rows before a FOR ALL ENTRIES query. Does the query necessarily return zero rows? Explain.'),
('nonempty','A FOR ALL ENTRIES driver contains three rows. Is its WHERE condition ignored just because FOR ALL ENTRIES is present?'),
('copy_rephrase','I change wa-amount after LOOP AT lt_data INTO wa. Why is lt_data unchanged?'),
('alias_rephrase','After LOOP AT lt_data ASSIGNING <item>, I change <item>-amount. Is a separate MODIFY needed to update that row?'),
('wrong_order','I sorted an ABAP standard table by company then document. Can I safely use BINARY SEARCH on document alone?'),
('right_order','I sorted an ABAP standard table ascending by document. Can I use BINARY SEARCH with a key consisting only of document?'),
('rename_code','Write ABAP to sum positive entries from it_amounts into rv_total. Use lv_amount as the loop variable.'),
('negative_code','Write ABAP to sum only negative integers from it_values into rv_sum.'),
('combined','An ABAP program changes a copied loop work area and then runs FOR ALL ENTRIES using an empty table. Explain both independent bugs.'),
('ordering','I need duplicates and ordered range traversal, rather than full unique-key lookup. Should I choose a hashed table? Explain.'),
]
(R/'memory_reference.json').write_text(json.dumps(BANK,indent=2));(R/'memory_unseen.json').write_text(json.dumps(UNSEEN,indent=2))
torch.set_grad_enabled(False);torch.set_num_threads(8);torch.manual_seed(314159)
tok=AutoTokenizer.from_pretrained(ID,revision=REV)
cfg=AutoConfig.from_pretrained(ID,revision=REV).text_config;cfg._attn_implementation='eager'
model=Qwen3_5ForCausalLM(cfg).eval();model.requires_grad_(False)
# Reserve a constant residual coordinate, using existing weights only.
E=model.model.embed_tokens.weight;E[:,0]=1
for layer in model.model.layers:
    layer.mlp.down_proj.weight[0,:]=0
    if layer.block_type=='linear_attention':layer.linear_attn.out_proj.weight[0,:]=0
    else:layer.self_attn.o_proj.weight[0,:]=0
if args.uniform:
    # Program one attention block to average token features into a separate context bank.
    # All remaining random residual transformations are disabled by zeroing output matrices.
    E[:,512:]=0
    for layer in model.model.layers:
        layer.mlp.down_proj.weight.zero_()
        if layer.block_type=='linear_attention':layer.linear_attn.out_proj.weight.zero_()
        else:layer.self_attn.o_proj.weight.zero_()
    attn=model.model.layers[3].self_attn
    attn.q_proj.weight.zero_();attn.k_proj.weight.zero_();attn.v_proj.weight.zero_()
    attn.v_proj.weight[:512,:512]=torch.eye(512)
    attn.v_proj.weight[:,0]=0 # Exclude the constant coordinate from the context average.
    # Eight query heads, two value heads, four repeats each; output gate sigmoid(0)=0.5.
    attn.o_proj.weight[512:768,:256]=20*torch.eye(256)
    attn.o_proj.weight[768:1024,1024:1280]=20*torch.eye(256)
model.lm_head.weight[:,0]=1 # tied embeddings; common logit offset does not select a token
D='mps' if torch.backends.mps.is_available() else 'cpu';model.to(D)
mlp=model.model.layers[-1].mlp
if args.affine:
    mlp.gate_proj=torch.nn.Linear(1024,3584,bias=True,device=D)
    mlp.up_proj=torch.nn.Linear(1024,3584,bias=True,device=D)
# Remove random final MLP while collecting keys; its input is unaffected.
mlp.down_proj.weight.zero_()
def prefix(q):return tok.apply_chat_template([{'role':'user','content':q}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
keys=[];values=[]
for q,a in BANK:
    p=tok.encode(prefix(q),add_special_tokens=False)
    answer=tok.encode(a,add_special_tokens=False)+[tok.eos_token_id]
    ids=p+answer
    capture=[]
    h=mlp.register_forward_pre_hook(lambda m,args:capture.append(args[0].detach().cpu()))
    model(input_ids=torch.tensor([ids],device=D),use_cache=False,logits_to_keep=1)
    h.remove()
    keys.append(capture[0][0,len(p)-1:len(p)+len(answer)-1])
    values.extend(answer)
K=torch.cat(keys);V=torch.tensor(values);N=len(V)
assert N<mlp.gate_proj.weight.shape[0]
# Undo RMS scaling via invariant coordinate; explicit prototype detector.
raw=K/K[:,0:1]; norms=raw.square().sum(-1)
projections=raw@raw.T/norms[None,:]
if args.affine: projections=K@K.T/K.square().sum(-1)[None,:]
conflict=projections.masked_fill(V[:,None]==V[None,:],-float('inf')).max(0).values
print('Memory tokens',N,'conflicting prototypes above self-match',int((conflict>=1).sum()),flush=True)
save_file({'normalized_keys':K.contiguous(),'target_tokens':V.contiguous()},str(R/'memory_keys.safetensors'))
original_gate=mlp.gate_proj.weight.clone();original_up=mlp.up_proj.weight.clone()
results=[]
# Predetermined variants, retained in full. No test-based automatic optimization.
variants=[('memory_80',.8,80),('memory_95',.95,160),('memory_99',.99,400),('memory_margin',None,400)]
if args.expanded: variants=[('expanded_85',.85,160),('expanded_95',.95,160),('expanded_margin',None,400)]
if args.refined: variants=[('refined_88',.88,240),('refined_90',.90,240),('refined_92',.92,240)]
if args.affine: variants=[('affine_98',.98,400),('affine_995',.995,800),('affine_999',.999,1600),('affine_margin',None,2000)]
if args.soft: variants=[('soft_50',1.1,50),('soft_100',1.1,100),('soft_150',1.1,150)]
for name,threshold,sharpness in variants:
    t=torch.full((N,),threshold) if threshold is not None else ((conflict+1)/2).clamp(.8,.999)
    gate=raw/norms[:,None];gate[:,0]-=t;gate*=sharpness
    exact=(K*gate).sum(-1)
    activation=F.silu(exact)
    direction=E[V.to(D)].detach().cpu().clone();direction[:,0]=0
    direction=direction/direction.norm(dim=-1,keepdim=True)
    mlp.gate_proj.weight.zero_();mlp.up_proj.weight.zero_();mlp.down_proj.weight.zero_()
    mlp.gate_proj.weight[:N]=gate.to(D)
    mlp.up_proj.weight[:N,0]=(1/K[:,0]).to(D)
    mlp.down_proj.weight[:,:N]=(direction.T*(30/activation.clamp_min(.01))[None,:]).to(D)
    if args.affine:
        if threshold is None: t=((conflict+1)/2).clamp(.9,.999999)
        gate=sharpness*K/K.square().sum(-1,keepdim=True)
        bias=-sharpness*t
        activation=F.silu((K*gate).sum(-1)+bias)
        mlp.gate_proj.weight.zero_();mlp.gate_proj.bias.zero_()
        mlp.up_proj.weight.zero_();mlp.up_proj.bias.zero_()
        mlp.gate_proj.weight[:N]=gate.to(D);mlp.gate_proj.bias[:N]=bias.to(D)
        mlp.up_proj.bias[:N]=1
        mlp.down_proj.weight[:,:N]=(direction.T*(30/activation.clamp_min(.0001))[None,:]).to(D)
    if args.soft:
        # z is negative: SiLU(z)*z approximates z^2 exp(z), a smooth positive
        # similarity kernel. RMS normalization supplies scale normalization.
        mlp.up_proj.weight.copy_(mlp.gate_proj.weight)
        mlp.up_proj.bias.copy_(mlp.gate_proj.bias)
        amplitude={50:1e6,100:1e12,150:1e18}[sharpness]
        mlp.down_proj.weight[:,:N]=(direction.T*amplitude).to(D)
    # Keep coordinate 0 constant; output directions already have 0 there.
    queries=[('memorized_'+str(i),q) for i,(q,a) in enumerate(BANK[:7])]+UNSEEN
    for tag,q in queries:
        ins=tok(prefix(q),return_tensors='pt').to(D)
        out=model.generate(**ins,do_sample=False,max_new_tokens=96,pad_token_id=tok.eos_token_id,eos_token_id=tok.eos_token_id)
        ids=out[0,ins.input_ids.shape[-1]:]
        row={'variant':name,'id':tag,'prompt':q,'text':tok.decode(ids,skip_special_tokens=True),'tokens':len(ids)}
        results.append(row);(R/'memory_results.json').write_text(json.dumps(results,indent=2));print(json.dumps(row),flush=True)
    save_file({k:p.detach().cpu().contiguous() for k,p in mlp.named_parameters()},str(R/(name+'.safetensors')))
print('Memory experiments complete.',flush=True)

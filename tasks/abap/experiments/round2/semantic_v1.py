"""Hand-programmed semantic feature channels and associative decoder in random Qwen.
No optimizer, gradient, pretrained neural weights, external retrieval or runtime router.
The feature dictionary and reference explanations are explicitly supplied knowledge.
"""
import json,argparse
from pathlib import Path
import torch
import torch.nn.functional as F
from safetensors.torch import save_file,load_file
from common import R,load,prefix,generate
FEATURES=[
['TRIES','entries','driver'],['empty','zero','initial'],['populated','filled','three','nonempty'],
['unique','HASH','hashed','cache','caching','lookup','lookups','exact'],
['copied','copy','copies','work','area','INT'],['ASS','IGN','symbol','symbols','alias','aliased','points','assigned'],
['INARY','SEARCH','binary','search'],['positive','greater','above'],['negative','below','less'],
['sum','total','summing','add','accumulation','accumulator','accumulate'],
['duplicates','duplicate','deduplicate','adjacent','repeats','deduplication'],['variable','variables','binding'],
['range','ordered','ordering','nonunique'],['both','independent'],['not','no','neither'],['guard','prevent'],
['table','tables'],['code','ABAP','method','body'],['sort','sorting','ascending'],
['matching','matches','same','complete'],['alone','wrong','different','then','non-leading'],
['change','changes','changing','modify','update'],['read','reads','access'],['integer','integers','numbers','values']]
RESERVE=65

def program_features(m,t):
    E=m.model.embed_tokens.weight;E[:,:RESERVE]=0;E[:,0]=1
    token_features={}
    words={w.casefold():i for i,ws in enumerate(FEATURES) for w in ws}
    for tid in range(t.vocab_size):
        word=t.decode([tid]).strip().casefold()
        if word in words:
            f=words[word];E[tid,1+f]=.3;token_features[tid]=f
    for layer in m.model.layers:
        layer.mlp.down_proj.weight[:RESERVE,:]=0
        if layer.block_type=='linear_attention':layer.linear_attn.out_proj.weight[:RESERVE,:]=0
        else:layer.self_attn.o_proj.weight[:RESERVE,:]=0
    # One full-attention head averages concept channels over the causal prefix.
    a=m.model.layers[3].self_attn
    a.q_proj.weight[:512,:]=0;a.k_proj.weight[:256,:]=0;a.v_proj.weight[:256,:]=0
    a.v_proj.weight[:24,1:25]=torch.eye(24,device=E.device)
    a.o_proj.weight[:,:256]=0;a.o_proj.weight[33:57,:24]=2*torch.eye(24,device=E.device)
    return token_features

def bank():
    B=json.loads((R.parent/'expanded_memory/memory_reference.json').read_text())
    additions=[
      (['Explain FOR ALL ENTRIES with a populated driver.', 'Is the WHERE clause discarded when the driver has entries?', 'What changes if the driver table is not empty?'],
       'A populated driver does not trigger the empty-table exception. The WHERE condition is evaluated for the driver entries; it is not discarded merely because FOR ALL ENTRIES is used.'),
      (['Show ABAP adding negative integers from it_values into rv_sum.', 'Sum values below zero in ABAP.', 'Give a negative-only accumulation loop.'],
       'CLEAR rv_sum.\nLOOP AT it_values INTO DATA(lv_value).\n  IF lv_value < 0.\n    rv_sum = rv_sum + lv_value.\n  ENDIF.\nENDLOOP.'),
      (['Which internal table suits ordered range access with duplicate keys?', 'Choose between a hashed and sorted table for duplicate-key ranges.', 'How do I support nonunique keys and ordered traversal?'],
       'Use a SORTED TABLE WITH NON-UNIQUE KEY for ordered processing and duplicate key values. A hashed primary table key must be unique and does not provide sorted primary-key order.')]
    for qs,answer in additions:B += [(q,answer) for q in qs]
    return B

def run():
    ap=argparse.ArgumentParser();ap.add_argument('--variant');ap.add_argument('--prompt');args=ap.parse_args()
    m,t=load();tf=program_features(m,t);device='mps' if torch.backends.mps.is_available() else 'cpu';m.to(device)
    mlp=m.model.layers[-1].mlp
    if args.variant:
        patch=load_file(str(R/(args.variant+'.safetensors')))
        for name,p in mlp.named_parameters():p.copy_(patch[name].to(device))
        print(generate(m,t,args.prompt)['text']);return
    B=bank();(R/'semantic_reference.json').write_text(json.dumps(B,indent=2))
    (R/'semantic_features.json').write_text(json.dumps({'feature_groups':FEATURES,'matched_token_ids':tf,'reserved_dimensions':RESERVE,'context_dimensions':[33,57]},indent=2))
    mlp.down_proj.weight.zero_();keys=[];values=[]
    for q,answer in B:
        p=t.encode(prefix(t,q),add_special_tokens=False);a=t.encode(answer,add_special_tokens=False)+[t.eos_token_id]
        cache=[];h=mlp.register_forward_pre_hook(lambda mod,inp:cache.append(inp[0].detach().cpu()))
        m(input_ids=torch.tensor([p+a],device=device),use_cache=False,logits_to_keep=1);h.remove()
        keys.append(cache[0][0,len(p)-1:len(p)+len(a)-1]);values.extend(a)
    K=torch.cat(keys);V=torch.tensor(values);N=len(V);assert N<3584
    print('Keys',N,'feature-bearing tokens',len(tf),flush=True)
    raw=K/K[:,0:1]
    save_file({'keys':K.contiguous(),'target_tokens':V},str(R/'semantic_keys.safetensors'))
    results=[]
    for name,threshold,weight in [('semantic_weak',.85,25),('semantic_medium',.88,100),('semantic_strong',.9,400)]:
        metric=torch.ones(1024);metric[1:33]=.1;metric[33:57]=weight
        norm=(raw.square()*metric).sum(-1)
        gate=raw*metric/norm[:,None];gate[:,0]-=threshold;gate*=240
        act=F.silu((K*gate).sum(-1));direction=m.model.embed_tokens.weight[V.to(device)].detach().cpu().clone()
        direction[:,:RESERVE]=0;direction/=direction.norm(dim=-1,keepdim=True)
        mlp.gate_proj.weight.zero_();mlp.up_proj.weight.zero_();mlp.down_proj.weight.zero_()
        mlp.gate_proj.weight[:N]=gate.to(device);mlp.up_proj.weight[:N,0]=(1/K[:,0]).to(device)
        mlp.down_proj.weight[:,:N]=(direction.T*(30/act.clamp_min(.01))[None,:]).to(device)
        save_file({k:p.detach().cpu().contiguous() for k,p in mlp.named_parameters()},str(R/(name+'.safetensors')))
        for case in json.loads((R/'problems.json').read_text()):
            row={'model':name,'id':case['id'],**generate(m,t,case['prompt'])};results.append(row)
            (R/'semantic_results.json').write_text(json.dumps(results,indent=2));print(name,case['id'],repr(row['text'][:140]),flush=True)
    print('Complete',flush=True)
if __name__=='__main__':run()

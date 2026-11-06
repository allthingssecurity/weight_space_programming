import json,argparse
import torch
import torch.nn.functional as F
from safetensors.torch import save_file,load_file
from common import R,load,prefix,generate
from semantic import program_features,bank,RESERVE

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--variant');ap.add_argument('--prompt');a=ap.parse_args()
    m,t=load();program_features(m,t);marker=t.encode(prefix(t,'Probe'),add_special_tokens=False)[-1];m.model.embed_tokens.weight[marker,63]=1;device='mps' if torch.backends.mps.is_available() else 'cpu';m.to(device)
    mlp=m.model.layers[-1].mlp
    mlp.gate_proj=torch.nn.Linear(1024,3584,bias=True,device=device);mlp.up_proj=torch.nn.Linear(1024,3584,bias=True,device=device)
    configs=[('routed_512',512,100),('routed_512_margin',512,100)]
    if a.variant:
        _,gain,_=next(x for x in configs if x[0]==a.variant)
        m.model.layers[3].self_attn.o_proj.weight[33:57,:24]=gain*torch.eye(24,device=device)
        weights=load_file(str(R/(a.variant+'.safetensors')))
        for k,p in mlp.named_parameters():p.copy_(weights[k].to(device))
        print(generate(m,t,a.prompt)['text']);return
    B=bank();results=[]
    (R/'routed_config.json').write_text(json.dumps({'variants':configs,'architecture_change':'Added biases in final MLP gate/up projections: 7168 scalar parameters.','pretrained_neural_weights':False,'reference_count':len(B),'knowledge_source':'Hand-written feature dictionary and reference answers; no optimization.'},indent=2))
    for name,gain,threshold in configs:
        m.model.layers[3].self_attn.o_proj.weight[33:57,:24]=gain*torch.eye(24,device=device)
        mlp.down_proj.weight.zero_();K=[];V=[];starts=[]
        for q,answer in B:
            starts.append(len(V));p=t.encode(prefix(t,q),add_special_tokens=False);ans=t.encode(answer,add_special_tokens=False)+[t.eos_token_id]
            cache=[];h=mlp.register_forward_pre_hook(lambda mod,inp:cache.append(inp[0].detach().cpu()))
            m(input_ids=torch.tensor([p+ans],device=device),use_cache=False,logits_to_keep=1);h.remove()
            K.append(cache[0][0,len(p)-1:len(p)+len(ans)-1]);V.extend(ans)
        K=torch.cat(K);V=torch.tensor(V);N=len(V)
        temperature=threshold
        gate=temperature*K/K.square().sum(-1,keepdim=True);bias=torch.full((N,),-temperature-5)
        act=F.silu((K*gate).sum(-1)+bias)
        direction=m.model.embed_tokens.weight[V.to(device)].detach().cpu().clone();direction[:,:RESERVE]=0;direction/=direction.norm(dim=-1,keepdim=True)
        mlp.gate_proj.weight.zero_();mlp.gate_proj.bias.zero_();mlp.up_proj.weight.zero_();mlp.up_proj.bias.zero_();mlp.down_proj.weight.zero_()
        mlp.gate_proj.weight[:N]=gate.to(device);mlp.gate_proj.bias[:N]=bias.to(device);mlp.up_proj.weight[:N,0]=1;mlp.up_proj.weight[:N,63]=-1
        mlp.up_proj.weight[starts,0]=0;mlp.up_proj.weight[starts,63]=1
        mlp.down_proj.weight[:,:N]=(-direction.T*1e17).to(device)
        # Compile one contrastive concept detector per answer family for response start.
        # This replaces prototype matching at the first token only. All routing remains
        # inside model parameters, and continuation uses the existing neural memory.
        raw=K/K[:,0:1]
        answers=list(dict.fromkeys(answer for q,answer in B))
        groups=[[starts[i] for i,(q,answer) in enumerate(B) if answer==a] for a in answers]
        centers=torch.stack([raw[g,33:57].mean(0) for g in groups])
        unit=centers/centers.norm(dim=-1,keepdim=True).clamp_min(1e-8)
        contrasts=unit-(unit.sum(0)[None,:]-unit)/(len(unit)-1)
        mlp.gate_proj.weight[starts]=0;mlp.gate_proj.bias[starts]=0
        mlp.up_proj.weight[starts]=0;mlp.up_proj.bias[starts]=0
        mlp.down_proj.weight[:,starts]=0
        for group,w in zip(groups,contrasts):
            row=group[0];gatevec=torch.zeros(1024);gatevec[33:57]=100*w
            if name.endswith('margin'):
                positive=raw[group,33:57]@w
                others=[i for i in starts if i not in group]
                negative=raw[others,33:57]@w
                boundary=(positive.min()+negative.max())/2
                gatevec[0]=-100*boundary
            mlp.gate_proj.weight[row]=gatevec.to(device)
            mlp.up_proj.weight[row,63]=1
            mlp.down_proj.weight[:,row]=(direction[row]*1e17).to(device)
        save_file({k:p.detach().cpu().contiguous() for k,p in mlp.named_parameters()},str(R/(name+'.safetensors')))
        probe=t(prefix(t,B[0][0]),return_tensors='pt').to(device)
        assert torch.isfinite(m(**probe,logits_to_keep=1).logits).all(), 'Nonfinite logits'
        for case in json.loads((R/'problems.json').read_text()):
            row={'model':name,'id':case['id'],**generate(m,t,case['prompt'])};results.append(row)
            (R/'routed_results.json').write_text(json.dumps(results,indent=2));print(name,case['id'],repr(row['text'][:150]),flush=True)
    print('Complete',flush=True)
if __name__=='__main__':main()

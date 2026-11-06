import json,argparse
import torch
import torch.nn.functional as F
from safetensors.torch import save_file,load_file
from common import R,load,prefix,generate
from semantic import program_features,bank,RESERVE

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--variant');ap.add_argument('--prompt');a=ap.parse_args()
    m,t=load();program_features(m,t);device='mps' if torch.backends.mps.is_available() else 'cpu';m.to(device)
    mlp=m.model.layers[-1].mlp
    mlp.gate_proj=torch.nn.Linear(1024,3584,bias=True,device=device);mlp.up_proj=torch.nn.Linear(1024,3584,bias=True,device=device)
    configs=[('concept_128',128,.9),('concept_512',512,.9),('concept_512_broad',512,.75),('concept_2048',2048,.95)]
    if a.variant:
        _,gain,_=next(x for x in configs if x[0]==a.variant)
        m.model.layers[3].self_attn.o_proj.weight[33:57,:24]=gain*torch.eye(24,device=device)
        weights=load_file(str(R/(a.variant+'.safetensors')))
        for k,p in mlp.named_parameters():p.copy_(weights[k].to(device))
        print(generate(m,t,a.prompt)['text']);return
    B=bank();results=[]
    (R/'concept_config.json').write_text(json.dumps({'variants':configs,'architecture_change':'Added biases in final MLP gate/up projections: 7168 scalar parameters.','pretrained_neural_weights':False,'reference_count':len(B),'knowledge_source':'Hand-written feature dictionary and reference answers; no optimization.'},indent=2))
    for name,gain,threshold in configs:
        m.model.layers[3].self_attn.o_proj.weight[33:57,:24]=gain*torch.eye(24,device=device)
        mlp.down_proj.weight.zero_();K=[];V=[]
        for q,answer in B:
            p=t.encode(prefix(t,q),add_special_tokens=False);ans=t.encode(answer,add_special_tokens=False)+[t.eos_token_id]
            cache=[];h=mlp.register_forward_pre_hook(lambda mod,inp:cache.append(inp[0].detach().cpu()))
            m(input_ids=torch.tensor([p+ans],device=device),use_cache=False,logits_to_keep=1);h.remove()
            K.append(cache[0][0,len(p)-1:len(p)+len(ans)-1]);V.extend(ans)
        K=torch.cat(K);V=torch.tensor(V);N=len(V)
        gate=400*K/K.square().sum(-1,keepdim=True);bias=torch.full((N,),-400*threshold)
        act=F.silu((K*gate).sum(-1)+bias)
        direction=m.model.embed_tokens.weight[V.to(device)].detach().cpu().clone();direction[:,:RESERVE]=0;direction/=direction.norm(dim=-1,keepdim=True)
        mlp.gate_proj.weight.zero_();mlp.gate_proj.bias.zero_();mlp.up_proj.weight.zero_();mlp.up_proj.bias.zero_();mlp.down_proj.weight.zero_()
        mlp.gate_proj.weight[:N]=gate.to(device);mlp.gate_proj.bias[:N]=bias.to(device);mlp.up_proj.bias[:N]=1
        mlp.down_proj.weight[:,:N]=(direction.T*(3000/act.clamp_min(.01))[None,:]).to(device)
        save_file({k:p.detach().cpu().contiguous() for k,p in mlp.named_parameters()},str(R/(name+'.safetensors')))
        for case in json.loads((R/'problems.json').read_text()):
            row={'model':name,'id':case['id'],**generate(m,t,case['prompt'])};results.append(row)
            (R/'concept_results.json').write_text(json.dumps(results,indent=2));print(name,case['id'],repr(row['text'][:150]),flush=True)
    print('Complete',flush=True)
if __name__=='__main__':main()

import json
import torch
from safetensors.torch import load_file
from common import R,load,generate
m,t=load();m.model.embed_tokens.weight[:,0]=1
for l in m.model.layers:
 l.mlp.down_proj.weight[0,:]=0
 if l.block_type=='linear_attention':l.linear_attn.out_proj.weight[0,:]=0
 else:l.self_attn.o_proj.weight[0,:]=0
m.to('mps' if torch.backends.mps.is_available() else 'cpu');mlp=m.model.layers[-1].mlp
rows=[]
for name,file in [('retained_recall','direct_memory/memory_95.safetensors'),('retained_transfer','refined_memory/refined_88.safetensors')]:
 p=load_file(str(R.parent/file))
 for k,v in mlp.named_parameters():v.copy_(p[k].to(m.device))
 for c in json.loads((R/'problems.json').read_text()):
  row={'model':name,'id':c['id'],**generate(m,t,c['prompt'])};rows.append(row)
  (R/'retained_results.json').write_text(json.dumps(rows,indent=2));print(name,c['id'],repr(row['text'][:140]),flush=True)

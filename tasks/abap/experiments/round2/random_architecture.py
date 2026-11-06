import json,torch
from common import R,load,generate
m,t=load();layer=m.model.layers[-1].mlp
layer.gate_proj=torch.nn.Linear(1024,3584,bias=True)
layer.up_proj=torch.nn.Linear(1024,3584,bias=True)
m.requires_grad_(False);m.eval().to('mps' if torch.backends.mps.is_available() else 'cpu')
rows=[]
for c in json.loads((R/'problems.json').read_text()):
 x={'model':'random_matching_architecture','id':c['id'],**generate(m,t,c['prompt'])};rows.append(x)
 (R/'random_architecture.json').write_text(json.dumps(rows,indent=2));print(c['id'],flush=True)

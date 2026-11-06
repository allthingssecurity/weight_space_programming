"""Rebuild the random foundation deterministically and apply saved memory weights.
No reference answers are read during inference.
"""
import os,argparse
os.environ.setdefault('PYTORCH_ENABLE_MPS_FALLBACK','1')
from pathlib import Path
import torch
from transformers import AutoConfig,AutoTokenizer,Qwen3_5ForCausalLM
from safetensors.torch import load_file
p=argparse.ArgumentParser();p.add_argument('prompt');p.add_argument('--variant',default='direct_memory/memory_95.safetensors');p.add_argument('--export',action='store_true');a=p.parse_args()
R=Path(__file__).resolve().parent
ID='Qwen/Qwen3.5-0.8B';REV='2fc06364715b967f1860aea9cf38778875588b17'
torch.set_grad_enabled(False);torch.set_num_threads(8);torch.manual_seed(314159)
tok=AutoTokenizer.from_pretrained(ID,revision=REV)
cfg=AutoConfig.from_pretrained(ID,revision=REV).text_config;cfg._attn_implementation='eager'
m=Qwen3_5ForCausalLM(cfg).eval();m.requires_grad_(False)
m.model.embed_tokens.weight[:,0]=1
for layer in m.model.layers:
    layer.mlp.down_proj.weight[0,:]=0
    if layer.block_type=='linear_attention':layer.linear_attn.out_proj.weight[0,:]=0
    else:layer.self_attn.o_proj.weight[0,:]=0
if Path(a.variant).parts[0] in ['uniform_memory','affine_memory','soft_memory']:
    E=m.model.embed_tokens.weight;E[:,512:]=0
    for layer in m.model.layers:
        layer.mlp.down_proj.weight.zero_()
        if layer.block_type=='linear_attention':layer.linear_attn.out_proj.weight.zero_()
        else:layer.self_attn.o_proj.weight.zero_()
    attn=m.model.layers[3].self_attn
    attn.q_proj.weight.zero_();attn.k_proj.weight.zero_();attn.v_proj.weight.zero_()
    attn.v_proj.weight[:512,:512]=torch.eye(512);attn.v_proj.weight[:,0]=0
    attn.o_proj.weight[512:768,:256]=20*torch.eye(256)
    attn.o_proj.weight[768:1024,1024:1280]=20*torch.eye(256)
patch=load_file(str(R/a.variant))
mlp=m.model.layers[-1].mlp
if 'gate_proj.bias' in patch:
    mlp.gate_proj=torch.nn.Linear(1024,3584,bias=True)
    mlp.up_proj=torch.nn.Linear(1024,3584,bias=True)
for name,param in mlp.named_parameters():param.copy_(patch[name])
if a.export and 'gate_proj.bias' in patch: raise ValueError('Affine architectures require this custom runner; standard Qwen export would drop biases.')
if a.export:
    m.save_pretrained(R/'recall-only-checkpoint');tok.save_pretrained(R/'recall-only-checkpoint')
device='mps' if torch.backends.mps.is_available() else 'cpu';m.to(device)
x=tok(tok.apply_chat_template([{'role':'user','content':a.prompt}],tokenize=False,add_generation_prompt=True,enable_thinking=False),return_tensors='pt').to(device)
y=m.generate(**x,max_new_tokens=96,do_sample=False,pad_token_id=tok.eos_token_id,eos_token_id=tok.eos_token_id)
print(tok.decode(y[0,x.input_ids.shape[-1]:],skip_special_tokens=True))

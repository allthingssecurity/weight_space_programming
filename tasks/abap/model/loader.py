"""Reconstruct the selected fixed neural model; no answer-bank dependency."""
import torch
from pathlib import Path
from safetensors.torch import load_file
from architecture import program_features
from common import load,prefix
ROOT=Path(__file__).resolve().parent

def load_model():
    model,tokenizer=load()
    program_features(model,tokenizer)
    marker=tokenizer.encode(prefix(tokenizer,'Probe'),add_special_tokens=False)[-1]
    model.model.embed_tokens.weight[marker,63]=1
    device='mps' if torch.backends.mps.is_available() else 'cpu'
    model.to(device)
    mlp=model.model.layers[-1].mlp
    mlp.gate_proj=torch.nn.Linear(1024,3584,bias=True,device=device)
    mlp.up_proj=torch.nn.Linear(1024,3584,bias=True,device=device)
    model.model.layers[3].self_attn.o_proj.weight[33:57,:24]=512*torch.eye(24,device=device)
    weights=load_file(str(ROOT/'routed_512.safetensors'))
    for name,param in mlp.named_parameters():param.copy_(weights[name].to(device))
    model.requires_grad_(False)
    return model.eval(),tokenizer

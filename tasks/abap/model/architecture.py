"""Fixed weight construction; no reference answers or per-prompt router."""
import torch

FEATURES=[
['TRIES','entries','driver'],['empty','zero','initial'],['populated','filled','three','nonempty'],
['unique','HASH','hashed','cache','caching','lookup','lookups','exact'],
['copied','copy','copies','work','area','INT','INTO'],['ASS','IGN','ASSIGN','ASSIGNING','symbol','symbols','alias','aliased','points','assigned'],
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

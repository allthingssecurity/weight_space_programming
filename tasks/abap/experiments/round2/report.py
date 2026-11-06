import json,html
from pathlib import Path
from common import R
cases=json.loads((R/'problems.json').read_text());base={x['id']:x for x in json.loads((R/'random.json').read_text())}
rows=[]
for f in ['semantic_results.json','concept_results.json','kernel_results.json','phase_results.json','retained_results.json','routed_results.json','random_architecture.json']:
 if (R/f).exists():rows+=json.loads((R/f).read_text())
models=list(dict.fromkeys(x['model'] for x in rows))
review=json.loads((R/'review.json').read_text()) if (R/'review.json').exists() else {'selected_model':models[-1],'assessments':{},'status':'Evaluation in progress; scores not final.'}
selected=review['selected_model'];index={(x['model'],x['id']):x for x in rows}
def esc(s):
 return html.escape(''.join(c if ord(c)>=32 or c in '\n\t' else '\\u%04x'%ord(c) for c in s))
def score(model,key):return review.get('assessments',{}).get(model,{}).get(key,{}).get('rating','Not reviewed')
def output(x):return '<pre>'+esc(x['text'])+'</pre><small>'+str(x['tokens'])+' tokens; '+('ended normally' if x['ended'] else 'reached 96-token cap')+'</small>'
s=['''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>ABAP: random versus edited weights</title><style>body{max-width:1200px;margin:48px auto;padding:0 24px;background:#f7f5f1;color:#26272a;font:17px/1.6 system-ui,sans-serif}h1{font-size:38px;line-height:1.1}h2{font-size:24px;margin-top:42px}table{width:100%;border-collapse:collapse;table-layout:fixed}td,th{padding:16px;border:1px solid #d8d1c6;vertical-align:top;text-align:left}th{background:#e8e1d7}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:350px;overflow:auto;font:14px/1.6 ui-monospace,monospace}td{background:#fff}small{color:#666}.note{background:#eee5d9;border-left:4px solid #95614b;padding:18px}summary{cursor:pointer;font-weight:600;padding:12px}a{color:#704834}.tag{font-weight:700;color:#7e4939}@media(max-width:700px){body{padding:0 12px}td,th{padding:8px}pre{font-size:12px}}</style><p class="tag">DIRECT WEIGHT PROGRAMMING · SECOND ROUND</p><h1>The same ABAP problems.<br>Random weights versus edited weights.</h1>''']
s.append('<p class="note">'+esc(review.get('status',''))+'</p>')
s.append(f'<p>Showing <b>{esc(selected)}</b> against the untouched random Qwen text model. Every pair has the exact same prompt, tokenizer, chat template, greedy decoding, float32 precision, and 96-token output limit. Seed: 314159. No pretrained neural weights or optimizer. The edited models contain explicitly supplied ABAP concepts and reference answers.</p>')
s.append('<p>25 fixed problems: 7 supplied-answer recall cases, 10 previous development cases, and 8 newly written transfer cases. The author knew the problems, and multiple candidates were evaluated on them; this is exploratory development, not a blind benchmark. Exact recall is not evidence of expert understanding. No SAP compiler or independent grader was used.</p>')
s.append('<h2>Candidate overview</h2><table><tr><th>Model</th><th>Outputs</th><th>Exact reference recall</th><th>Reviewed correct answers</th></tr>')
for model in ['random']+models:
 data=list(base.values()) if model=='random' else [x for x in rows if x['model']==model]
 exact=sum(x['text'].strip()==c['reference'] for c in cases if 'reference' in c for x in data if x['id']==c['id'])
 assessed=review.get('assessments',{}).get(model,{})
 passes=sum(x['rating']=='Correct' for x in assessed.values())
 s.append(f'<tr><td>{esc(model)}</td><td>{len(data)}/25</td><td>{exact}/7</td><td>{passes}/{len(assessed)} reviewed</td></tr>')
s.append('</table>')
for n,c in enumerate(cases,1):
 b=base[c['id']];a=index.get((selected,c['id']))
 if a is None:continue
 s.append(f'<h2>{n}. {esc(c["id"])}</h2><p><small>{esc(c["split"])}</small></p><p><b>Problem:</b> {esc(c["prompt"])}</p>')
 s.append(f'<table><tr><th>Before · random weights<br><small>{esc(score("random",c["id"]))}</small></th><th>After · {esc(selected)}<br><small>{esc(score(selected,c["id"]))}</small></th></tr><tr><td>{output(b)}</td><td>{output(a)}</td></tr></table>')
 assessment=review.get('assessments',{}).get(selected,{}).get(c['id'],{})
 if assessment.get('reason'):s.append('<p class="note">'+esc(assessment['reason'])+'</p>')
 if c.get('criterion'):s.append('<p><small>Expected: '+esc(c['criterion'])+'</small></p>')
 s.append('<details><summary>Other edited candidates on this exact problem</summary>')
 for model in models:
  if model==selected:continue
  x=index.get((model,c['id']))
  if x:s.append('<h3>'+esc(model)+'</h3>'+output(x))
 s.append('</details>')
s.append('<h2>What was programmed?</h2><p>Handwritten ABAP vocabulary features were placed into reserved embedding dimensions. One attention head was set to average those features over the preceding tokens. Reserved residual channels carry them to the final layer, where explicit prototype detectors select next-token directions from the supplied reference examples. Later candidates amplify the concept channels, use smooth similarity kernels, separate response-start memories from continuation memories, and compile contrastive concept detectors for the first response token. Bias-based candidates add 7,168 parameters to the final MLP; those are architecture variants, not pure edits to the original parameter set.</p><p>Reference facts and code are supplied by the assistant, not discovered by the random model. The neural model has no external answer lookup, keyword router, or reference text at generation time. Knowledge is encoded in its weights. This does not by itself provide compositional reasoning.</p>')
s.append('<p><a href="problems.json">Exact problems</a> · <a href="random.json">Random outputs</a> · <a href="review.json">Review details</a> · <a href="README.txt">Reproduce and run</a> · <a href="../comparison.html">Previous 25 variants</a> · <a href="../../model/model_recipe.json">Selected model recipe</a></p></html>')
(R/'comparison.html').write_text(''.join(s))
print('Wrote report:',len(rows),'edited outputs,',len(base),'random outputs')

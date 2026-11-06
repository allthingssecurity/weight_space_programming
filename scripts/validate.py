"""Validate task manifests and the published ABAP evidence without downloading a model."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def load(p):return json.loads(p.read_text())
def main():
    tasks=list((ROOT/'tasks').glob('*/task.json'));assert tasks,'No tasks found'
    for path in tasks:
        spec=load(path);folder=path.parent
        assert spec['id']==folder.name
        for key in ['model_manifest','evaluation_problems','evaluation_review','comparison']:
            assert (folder/spec[key]).is_file(),f'Missing {key}: {folder/spec[key]}'
        cases=load(folder/spec['evaluation_problems']);review=load(folder/spec['evaluation_review'])
        ids=[x['id'] for x in cases];assert len(ids)==len(set(ids))
        assert all(set(a)==set(ids) for a in review['assessments'].values())
        if spec['id']=='abap':
            round2=folder/'experiments/round2'
            assert hashlib.sha256((round2/'problems.json').read_bytes()).hexdigest()==(round2/'problems.sha256').read_text().strip()
            for f in ['random.json','random_architecture.json']:
                rows=load(round2/f);assert len(rows)==25 and {x['id'] for x in rows}==set(ids)
            rows=[x for x in load(round2/'routed_results.json') if x['model']=='routed_512']
            assert len(rows)==25 and {x['id'] for x in rows}==set(ids)
            assert sum(x['rating']=='Correct' for x in review['assessments']['routed_512'].values())==18
            for name in ['random','random_matching_architecture']:
                assert sum(x['rating']=='Correct' for x in review['assessments'][name].values())==0
            by={x['id']:x for x in rows}
            assert sum(by[x['id']]['text'].strip()==x['reference'] for x in cases if 'reference' in x)==7
            weights=load(folder/spec['model_manifest']);assert len(weights['sha256'])==64
            artifact=folder/'model'/weights['file']
            if artifact.exists():
                assert artifact.stat().st_size==weights['bytes']
                assert hashlib.sha256(artifact.read_bytes()).hexdigest()==weights['sha256']
        print('Validated:',spec['id'])
if __name__=='__main__':main()

"""Run the fixed selected ABAP model, with no reference-answer access."""
import argparse
from pathlib import Path
from loader import load_model
from common import generate
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('prompt');a=p.parse_args()
    if not (Path(__file__).resolve().parent/'routed_512.safetensors').exists():
        p.error('Weights are missing. Run tasks/abap/model/download_weights.py first.')
    model,tokenizer=load_model()
    print(generate(model,tokenizer,a.prompt)['text'])

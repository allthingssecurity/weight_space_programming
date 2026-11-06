Same-problem comparison: original random weights, matching-architecture random
control, and edited candidates. See ../../README.md for setup and reproduction.

The selected model is routed_512. review.json contains the unblinded static
assessments: 18/25 correct, including 7 supplied-answer recall cases.
The remaining 18 prompts have 11 correct answers. Expert ability is not achieved.

problems.json is the exact fixed set; problems.sha256 records its hash.
random.json and random_architecture.json contain the two random controls.
routed_results.json contains the selected variant and a margin variant.
All other *_results.json files preserve the alternative candidates.
The routed_numeric_failure directory is an excluded numerical-failure trial.

Run report.py with the repository's Python environment to rebuild comparison.html.
Selected-model inference uses ../../model/run.py and the release-weight manifest.

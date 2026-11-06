# Repository guidance

- Put each new user task in its own `tasks/<task-id>/` directory. Do not mix its data, model, or results into another task.
- Preserve prior raw results. New rounds belong in separate directories.
- Record the random seed, model/config revision, decoding settings, supplied reference knowledge, and any architecture changes.
- Compare random and edited models on identical prompts and settings. Separate supplied-answer recall from transfer tests.
- Do not describe memorization, lexical overlap, or unblinded development scores as expert understanding or an independent benchmark.
- Do not introduce training, pretrained neural weights, or external inference-time answer retrieval without clearly addressing the user's constraints.
- Keep environments, caches, credentials, and generated model binaries out of Git. Selected weight artifacts belong in versioned releases with hashes.
- Run `python3 scripts/validate.py` before publishing changes. For model changes, also run an appropriate actual inference check.

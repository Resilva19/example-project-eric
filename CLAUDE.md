@AGENTS.md

# Claude Code Specific Notes

- When editing R scripts, always read the file first to understand context.
- Preserve extensive teaching comments -- this is a pedagogical repository.
- Each R script loads `.env` and sets `data_dir` at the top via `dotenv`.
- Do not create new files unless necessary. Prefer editing existing files.
- Do not remove comments or teaching notes from the code.

## Python Environment

This project uses the conda environment `example-project`.

**Always run Python using the full path:**
```
C:\Users\ruisilva\AppData\Local\miniconda3\envs\example-project\python.exe
```

**Or use `conda run` to execute scripts:**
```
conda run -n example-project python script.py
```

Never use bare `python` commands — always use one of the two approaches above.

# Beer Game Simulation

A simple beer game simulation.

## Setup

```bash
uv sync
```

## Performing a Comparison

To compare the rule-based (mechanistic) approach with the Generative Agent-Based Modeling (GABM) approach:

1. **Run Mechanistic Simulation:**
   ```bash
   export PYTHONPATH=$PYTHONPATH:. && uv run src/main.py --mode mechanistic --output results_mech.csv
   ```

2. **Run GABM Simulation** (ensure Ollama is running):
   ```bash
   export LLM_ENDPOINT="http://localhost:11434/v1" && export LLM_MODEL="mistral:latest" && export PYTHONPATH=$PYTHONPATH:. && uv run src/main.py --mode gabm --output results_gabm.csv
   ```

3. **Visualize Comparison:**
   ```bash
   uv run scripts/plot_results.py results_mech.csv results_gabm.csv
   ```
   This will generate a `bullwhip_comparison.png` file showing the behavioral differences.

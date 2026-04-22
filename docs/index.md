---
title: Beer Game — Local LLM Benchmark
---

# Beer Game — Local LLM Benchmark

An implementation of Sterman's Beer Distribution Game used as a
quantitative benchmark for local language models running under Ollama.

## Documents

- **[Benchmark findings](./benchmark-findings.md)** — the main writeup:
  motivation, hardware, methodology, 5-model leaderboard, limitations,
  and a GABM / AutoGen appendix.
- **[Tournament summary](./tournament_summary.md)** — raw leaderboard
  table for quick reference.

## Leaderboard snapshot

| Rank | Model                  | Total cost (36-wk) |
|-----:|------------------------|-------------------:|
|   🥇 | `gpt-oss:20b`          | **$2,585** |
|   🥈 | `phi4:14b`             | $2,829 |
|   🥉 | `qwen3.5:9b`           | $5,651 |
|    4 | `gemma4:e4b-it-q4_K_M` | $7,536 |
|    5 | `mistral:latest`       | $8,377 |

Reference: Sterman anchor-and-adjust (rule-based) = **$3,128**;
`gpt-oss:20b` is the only local LLM in the roster to beat it.

## Source

[github.com/ipdelete/beer-game](https://github.com/ipdelete/beer-game)

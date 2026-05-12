| model                  | wall_seconds | total_cost | retailer | wholesaler | distributor | factory  |
|------------------------|-------------:|-----------:|---------:|-----------:|------------:|---------:|
| gpt-oss:20b            | 425          | 2585.00    | 578.00   | 1264.50    | 421.00      | 321.50   |
| deepseek-v4-flash†     | 1360         | 2789.50    | 883.50   | 1120.00    | 570.00      | 216.00   |
| phi4:14b               | 826          | 2828.50    | 1236.50  | 370.00     | 394.00      | 828.00   |
| qwen3.5:9b             | 859          | 5651.00    | 595.00   | 757.00     | 1294.00     | 3005.00  |
| gemma4:e4b-it-q4_K_M   | 510          | 7535.50    | 1731.00  | 3206.00    | 1540.50     | 1058.00  |
| mistral:latest         | 395          | 8377.00    | 384.50   | 2665.00    | 1573.00     | 3754.50  |

† **Not directly comparable to the Ollama roster.** Served by
[`antirez/ds4`](https://github.com/antirez/ds4) (`ds4-server`, Metal,
q4-imatrix, ~153 GB on disk) — a different inference runtime and a
substantially larger model than the 5-model Ollama cohort. ds4 also
benefits from KV-prefix reuse across the growing per-role transcripts,
which Ollama does not exploit. Listed for reference, not as a head-to-head.


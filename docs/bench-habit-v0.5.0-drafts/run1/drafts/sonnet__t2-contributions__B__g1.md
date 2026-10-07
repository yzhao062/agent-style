We present FlashKV, a runtime that pages and compresses the KV cache for long-context LLM serving. On Llama-3-70B running on one 8xH100 node, FlashKV reduces KV-cache memory by 55% at a 4k context and by 63% at 32k and 64k. The decoding speedup over vLLM grows with context length, from 1.10x at 4k to 1.87x at 32k. At 64k, vLLM runs out of memory while FlashKV still decodes (Table 2).

Note: Table 2 lists a 2.35x speedup at 64k, but vLLM runs out of memory there, so that ratio has no baseline. I left the figure out of the paragraph. Please confirm how it was measured before citing it.

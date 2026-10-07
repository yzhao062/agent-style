This paper makes two contributions. First, we design and implement FlashKV, a runtime for long-context LLM serving that pages the key-value (KV) cache and compresses it. Second, we evaluate FlashKV against vLLM by serving Llama-3-70B on one node of eight H100 GPUs at context lengths from 4k to 64k tokens (Table 2). Across these lengths, FlashKV reduces KV-cache memory by 55% to 63%. Its decoding speedup over vLLM grows with context length: 1.10× at 4k tokens, 1.48× at 16k, and 1.87× at 32k. At 64k tokens vLLM runs out of memory, while FlashKV still serves the same requests on the same node.

---

I left out the 2.35× speedup at 64k. vLLM ran out of memory at that length, so the table doesn't show what the 2.35× is measured against. If it compares to a different baseline, such as vLLM with CPU offloading or a smaller batch, name that baseline in Table 2 and I'll add the number back.

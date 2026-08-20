# Token Types & Cost Optimization in Agentic AI

*A theory companion to `guardrails_lab.ipynb` section 8. Read this before
running the hands-on token-measurement cells.*

---

## 1. Why "tokens" isn't one thing in an agentic system

In a simple chatbot, tokens are just "the text going in" and "the text
coming out." An **agent** — something that reasons over tool results,
retrieved documents, and its own prior turns across a loop — has several
*distinct* categories of tokens flowing through it, each with different
cost behavior and different levers to optimize. Treating them as one
undifferentiated pile is the most common reason agent costs surprise
people in production.

---

## 2. The token types

| Type | What it is | Why it matters for cost |
|---|---|---|
| **Prompt / input tokens** | System prompt + conversation history + the current turn | Grows every turn in a multi-step agent loop — usually the biggest cost driver over a session |
| **Completion / output tokens** | The model's generated answer, including structured output | Priced higher than input tokens on every current model tier |
| **Tool-definition tokens** | JSON schemas for every available tool, sent on *every* call whether or not that tool is used | Fixed overhead per call — invisible in your prompt but billed every time |
| **Tool-call / tool-result tokens** | The model's `tool_use` request, and the `tool_result` sent back to it | Often the largest contributor to context growth in a multi-step loop — a single database row or web page can be huge |
| **Extended-thinking / reasoning tokens** | Internal step-by-step reasoning some models produce before their visible answer | Billed as part of the exchange even though it isn't the final answer |
| **Cache-write vs. cache-read tokens** | The *same* content, billed differently depending on whether it's being stored in cache for the first time or read from an existing cache entry | Cache reads are billed far below normal input price — the core lever for repeated context |
| **Retrieved / RAG context tokens** | Documents pulled from a vector store or search step and injected into the prompt | Behaves like any other input token once in context, but easy to over-include "just in case" |
| **Multimodal tokens** | Images, PDFs, audio, converted to a token-equivalent cost | Independent of surrounding text length |
| **Inter-agent tokens** | Messages passed between a supervisor and sub-agents in a multi-agent architecture | Counted on *both* sides of the exchange — easy to undercount when estimating a multi-agent system's cost against a single-agent one |

---

## 3. Where the real cost/latency levers are

### 3.1 Prompt caching is the highest-leverage lever for agent loops
Mark your system prompt, tool definitions, and any large static context
with a cache breakpoint. A typical agent loop resends the *entire growing
conversation* on every turn — caching the stable prefix (system prompt +
tools + early history) means each new turn only pays full price for what's
actually new.

Cache pricing works as a multiplier on the base input rate:

| Cache operation | Multiplier | Notes |
|---|---|---|
| 5-minute cache write | 1.25x base input | Cache valid 5 minutes |
| 1-hour cache write | 2x base input | Cache valid 1 hour |
| Cache read (hit) | 0.1x base input | Same duration as the write it came from |

A cache pays for itself after **one** read (5-minute duration) or **two**
reads (1-hour duration) — after that, every additional read is pure
savings. This is why section 8.3 of the lab has you compare a cache-miss
call against a cache-hit call directly: the `cache_creation_input_tokens`
and `cache_read_input_tokens` fields in the response tell you exactly
which happened.

### 3.2 Route by task complexity, not by default to your biggest model
This is the pattern the lab already demonstrates structurally: a full
reasoning model for the agent's actual answer, but a cheap local
classifier (or a small/fast model) for guardrail judgments that don't
need deep reasoning. Section 1.2's local DeBERTa injection detector has
**zero marginal API token cost** — you pay for hosting it, not per
request — which is why section 8.5 shows the cost gap explicitly at
scale (1 million checks/day).

### 3.3 Keep extended-thinking budgets tight and purposeful
Extended thinking adds tokens billed as part of the exchange. For
guardrail-style judge calls — classification, not open-ended reasoning —
you generally want minimal or no extended thinking, since it adds cost
without adding value to a task that's really just "return this JSON."

### 3.4 Force structured, minimal outputs
The `ask_claude_judge()` pattern used throughout the lab — *"Respond with
ONLY this JSON, no other text"* — isn't just a code-cleanliness choice, it's
a direct token optimization: it caps output tokens to exactly what's
needed and eliminates the preamble/postamble a conversational response
would otherwise generate. Section 8.4 measures this difference directly.

### 3.5 Compact or summarize long-running agent context
Long agent loops (many tool calls in sequence) will eventually make
per-turn cost scale linearly with loop length if nothing is ever dropped.
Periodically summarizing older tool results/turns and discarding the raw
originals keeps this in check.

### 3.6 Retrieve, don't stuff
For anything knowledge-base-sized, retrieving only the relevant chunk
(RAG) beats including the whole document in every turn — a token-cost
decision as much as a quality one.

### 3.7 Cap output length deliberately per call type
A guardrail judge call needs maybe 100–300 tokens of output; a main agent
response might need 1000+. Setting `max_tokens` per purpose (as the lab
does throughout) avoids paying for runaway generation on calls that
should be short.

### 3.8 Use batch processing for non-real-time work
Bulk classification, offline evaluation, or backfilling guardrail checks
on historical data don't need real-time latency — batch processing
trades latency for meaningfully lower per-token cost, a good fit for
lab-style evaluation runs.

---

## 4. Worked example: reading a real `usage` object

Every `client.messages.create()` response carries a `usage` field. This is
what you're actually looking at in section 8 of the lab:

```python
{
  "input_tokens": 25,
  "cache_creation_input_tokens": 1150,   # first call: paying to write the cache
  "cache_read_input_tokens": 0,
  "output_tokens": 42
}
```

versus the same call repeated within the cache window:

```python
{
  "input_tokens": 25,
  "cache_creation_input_tokens": 0,
  "cache_read_input_tokens": 1150,       # second call: reading from cache, 0.1x price
  "output_tokens": 38
}
```

Turning this into a dollar figure just means applying the per-token-type
price to each field and summing — which is exactly what `calculate_cost()`
does in the lab notebook.

---

## 5. A word of caution on the numbers

Model prices, cache multipliers, and per-model tool-use overhead all
change as new model versions ship. The specific dollar figures in this
document and in the lab notebook were accurate at the time this was
written, pulled directly from Anthropic's official pricing page rather
than from memory — but **verify current numbers at
`platform.claude.com/docs/en/about-claude/pricing`** before using this for
real production budgeting. The *categories* of tokens and the *shape* of
each optimization strategy are stable; the numbers attached to them are not.

---

## 6. Pre-lab discussion questions

1. In a multi-step agent loop (several tool calls in sequence before a
   final answer), which token type do you expect to grow fastest across
   turns — and why does that make it the first thing worth optimizing?
2. Prompt caching only helps when the cached content is byte-for-byte
   identical across calls. What in a typical agent's system prompt is
   genuinely stable enough to cache, and what usually isn't?
3. The lab's local DeBERTa classifier has zero marginal API cost per
   check. What costs does it have instead, and under what request volume
   does that trade-off actually favor it over a Claude-as-judge call?
4. If an agent's tool definitions add a few hundred tokens to *every*
   call regardless of which tool gets used, what's the cost argument for
   loading tool schemas lazily (only when relevant) instead of always
   including your full toolset?
5. Why does capping `max_tokens` per call type (short for a judge, longer
   for a main answer) matter for cost even if the model would have
   naturally produced a shorter answer most of the time anyway?

---

## 7. Mapping theory → lab code

| Concept above | Section in `guardrails_lab.ipynb` |
|---|---|
| Reading `usage.input_tokens` / `usage.output_tokens` | 8.1 |
| Tool-definition token overhead | 8.2 |
| Cache write vs. cache read | 8.3 |
| Structured vs. conversational output cost | 8.4 |
| Model routing / local classifier vs. LLM judge at scale | 8.5, ties to section 1.2 |
| `calculate_cost()` helper | Start of section 8 |

When you're ready, open `guardrails_lab.ipynb` and run section 8 top to
bottom against your own API key to see these numbers for real.

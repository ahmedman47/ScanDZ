# ADR-0001: Use local models by default

Status: accepted (11 November 2026)

## Context
Invoices contain confidential business data. Hosted LLM APIs send documents to a third party,
may keep or reuse inputs, and have free-tier limits that change often.

## Options
1. Hosted LLM API by default: faster and stronger, but the data leaves the machine.
2. Local models with Ollama: slower and weaker, but private and free.

## Decision
Use local models by default (Ollama, currently qwen2.5:7b). External calls are only possible
through an explicit flag (allow_external), enforced in code by the egress guard.

## Consequences
- Extraction is slower and the model is weaker than a hosted one.
- I compensate with grounding checks, validation rules and human review.
- The public demo may need a hosted model; it will use synthetic documents only.
- If I change the model, I must re-run the evaluation and record the new model tag.
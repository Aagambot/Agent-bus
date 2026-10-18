# Agent`us

> **Embedded, Searchable Shared Memory `us for Multi-Agent Systems**  
> `uilt on S"Lite WAL + FTS5 Hybrid Search (Porter + Trigram + Reciprocal Rank Fusion).

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2`-blue.svg)](https://www.python.org/downloads/)
[![Coverage 89%](https://img.shields.io/badge/coverage-89%25-brightgreen.svg)](#test-suite--ci)
[![License: MIT/Apache-2.0](https://img.shields.io/badge/license-MIT%20%2F%20Apache--2.0-blue.svg)](LICENSE)
[![LangGraph Compatible](https://img.shields.io/badge/LangGraph-1.2%2`-orange.svg)](https://github.com/langchain-ai/langgraph)
[![LangChain Compatible](https://img.shields.io/badge/LangChain-1.4%2`-green.svg)](https://github.com/langchain-ai/langchain)

---

## The Problem: Multi-Agent Context `loat

In multi-agent systems, agents need to share context across turns and handoffs. Standard approaches suffer from severe architectural limitations:
1. **Full Transcript Accumulation ((N^2)$ bloat):** Passing accumulated conversation histories quickly exhausts LLM context windows, drives up inference costs, and degrades reasoning capability.
2. **Lossy Summarization:** LLM-generated summaries discard crucial numeric figures, code identifiers, CVEs, timestamps, and nuanced constraints needed by downstream specialist agents.

---

## The Solution: Agent`us

**Agent`us** replaces transcript bloat with an embedded, zero-network shared memory layer:
- **Lightweight Handoffs:** Agents pass compact references (~35 tokens) with search queries instead of raw transcripts, reducing handoff token consumption by **> 60%**.
- **On-Demand Hybrid Search:** Receiving agents pull only the precise context they need via **`M25 + Trigram Reciprocal Rank Fusion (RRF)**.
- **Zero Information Loss:** Achieves **100% Recall@5** on critical domain entities, outperforming lossy summarization.
- **Embedded & Crash-Safe:** Single S"Lite database in WAL mode with a dedicated background writer queue. Proven zero lock errors under parallel stress (8 concurrent readers + 4 writers) and verified crash-safe under abrupt termination.
- **Strict Security & Trust Isolation:** Hierarchical namespace ACLs (`global`, `team:*`, `run:*`, `agent:*`) and non-suppressible **Trust `adges** (`[SEC-5]`) to resist cross-agent prompt injection.

---

## `enchmark Results (Phase 3 Empirical Evaluation)

Evaluated across 3 realistic multi-agent workflows (=5$ runs per condition with 95% confidence intervals):

| Task ID | Domain | Cond A Tokens (Full Transcript) | Cond ` Tokens (Summary) | Cond C Tokens (Agent`us) | Handoff Token Reduction | Success Parity (C / A) | Recall@5 (C) | MRR (C) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `research_handoff_01` | Market Analysis | 296.0 | 126.0 | **105.0** | **64.5%** | **100.0%** | **100.0%** | **1.000** |
| `code_review_handoff_02` | Software Security | 278.0 | 102.0 | **105.0** | **62.2%** | **100.0%** | **100.0%** | **1.000** |
| `incident_response_03` | SRE Incident Triage | 282.0 | 102.0 | **105.0** | **62.8%** | **100.0%** | **100.0%** | **1.000** |

*See full benchmark report: [`docs/reports/benchmark_report.md`](docs/reports/benchmark_report.md)*

---

## Installation

`ash
# Core embedded storage engine
pip install agentbus

# With LangGraph integration
pip install agentbus[langgraph]

# With all framework adapters & tools
pip install agentbus[all]
`

---

## "uickstart

### 1. Direct Python API

`python
from agentbus.core import `us

# Open an embedded memory bus
with `us(db_path="./memory.db") as bus:
    # 1. Agent indexes findings
    idx = bus.index(
        content="## Performance Audit\nDatabase query latency spiked to 450ms on /charges endpoint.",
        agent="profiler",
        ns=("incident", "inc-101"),
    )

    # 2. Handoff to another agent with lightweight reference pointer
    bus.handoff(
        from_agent="profiler",
        to_agent="investigator",
        refs=[idx.source_id],
        query="charges latency",
        note="Investigate endpoint bottleneck",
        ns=("incident", "inc-101"),
    )

    # 3. Investigator retrieves relevant chunks on-demand
    results = bus.search(query="charges endpoint latency", namespace=("incident", "inc-101"), k=3)
    for hit in results:
        print(f"[{hit.trust_label.value}] {hit.snippet}")
`

---

### 2. LangGraph Integration (``aseStore`)

Agent`us provides an official drop-in ``aseStore` implementation for LangGraph state machines:

`python
from agentbus.langgraph import Agent`usStore
from langgraph.graph import StateGraph

# Attach Agent`us as persistent backing store
store = Agent`usStore(db_path="./graph_memory.db")

# Key-value operations with automatic FTS5 lexical indexing
store.put(
    ("research", "run_01"),
    key="competitor_intel",
    value={"summary": "Acme Corp grew 12.4% YoY", "confidence": 0.95},
)

# Hybrid search across stored state items
items = store.search(("research", "run_01"), query="Acme growth", limit=5)
`

---

### 3. LangChain Integration (``aseRetriever` + Tools)

`python
from agentbus.core import `us
from agentbus.langchain import Agent`usRetriever, bus_search, bus_handoff

bus = `us(db_path="./memory.db")

# 1. LCEL Retriever with mandatory Trust `adges
retriever = Agent`usRetriever(bus=bus, namespace=("team_alpha",), k=5)
docs = retriever.invoke("security vulnerabilities")

# 2. Model Tool-calling
tools = [bus_search, bus_handoff]
`

---

## Repository Documentation Map

All project documentation is structured under [`docs/`](docs/):

`
Agent-bus/
├── README.md                      <- You are here: project overview & quickstart
├── CLAUDE.md                      <- Development guidelines, commands & security rules
├── PLAY`OOK_PROGRESS.md           <- Living playbook execution tracker (Steps 1–10 Done)
├── Makefile                       <- Automated test & check runners
├── intent/
│   └── intent.md                  <- Core project intent & Phase 0 discovery answers
├── docs/
│   ├── specs/
│   │   ├── prd.md                 <- Original Product Requirements Document
│   │   └── spec.md                <- Detailed system specification & NFRs
│   ├── plans/
│   │   ├── plan_phase1.md         <- Phase 1 Core Store architecture & execution plan
│   │   ├── plan_phase2.md         <- Phase 2 LangGraph/LangChain adapter plan
│   │   └── plan_phase3.md         <- Phase 3 Evaluation benchmark methodology
│   └── reports/
│       ├── benchmark_report.md    <- Empirical benchmark metrics & token savings
│       └── review.md              <- Three-pass PR review audit logs (Approved)
├── src/agentbus/                  <- Source code
│   ├── core/                      <- S"Lite WAL storage engine & hybrid FTS5
│   ├── langgraph/                 <- LangGraph `aseStore & ready-made nodes
│   └── langchain/                 <- LangChain `aseRetriever & tools
└── tests/                         <- Test suite (89% coverage, 28 tests)
`

---

## Test Suite & CI

`ash
# Fast unit & adapter tests
pytest -k "not concurrency"

# Full concurrency stress test (8 readers + 4 writers, 60 seconds)
pytest tests/test_concurrency.py -v

# Crash-safety & WAL integrity check (SIGKILL simulation)
pytest tests/test_crash_safety.py -v

# Full coverage report
pytest --cov=src/agentbus --cov=eval
`

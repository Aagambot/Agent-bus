# AgentBus

> **Embedded, Searchable Shared Memory Bus for Multi-Agent Systems**  
> Built on SQLite WAL + FTS5 Hybrid Search (Porter + Trigram + Reciprocal Rank Fusion).

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests Passing](https://img.shields.io/badge/tests-28%20passed-brightgreen.svg)](#test-suite--ci)
[![Coverage 89%](https://img.shields.io/badge/coverage-89%25-brightgreen.svg)](#test-suite--ci)
[![SQLite WAL](https://img.shields.io/badge/storage-SQLite%20WAL%20(zero--lock)-success.svg)](#embedded-architecture)
[![LangGraph Compatible](https://img.shields.io/badge/LangGraph-1.2%2B-orange.svg)](https://github.com/langchain-ai/langgraph)
[![LangChain Compatible](https://img.shields.io/badge/LangChain-1.4%2B-green.svg)](https://github.com/langchain-ai/langchain)
[![License: MIT/Apache-2.0](https://img.shields.io/badge/license-MIT%20%2F%20Apache--2.0-blue.svg)](LICENSE)

---

## The Problem: Multi-Agent Context Bloat

In modern multi-agent systems, specialist agents must pass context to downstream agents. Standard approaches force developers into an unacceptable tradeoff:

```text
[Approach 1: Full Transcript Accumulation] (Quadratic Token Explosion)
Agent 1 ---> (History A: 300t) ---> Agent 2 ---> (History A+B: 900t) ---> Agent 3 ---> [!] Overflow
Tokens per handoff balloon at O(N^2), quickly saturating LLM context windows and multiplying inference bills.

[Approach 2: LLM Summarization] (Lossy Compression & Hallucination)
Agent 1 ---> (Summary: 110t)   ---> Agent 2 ---> (Summary: 110t)     ---> Agent 3 (Dropped CVE & 12.4% metric!)
33% of specific numbers, IDs, constraints, and timestamps are dropped or subtly hallucinated.
```

---

## The Solution: AgentBus

**AgentBus** replaces heavy prompt handoffs with an embedded, zero-network shared memory layer:

```text
AgentBus Architecture: Pointer Handoff + On-Demand Search

+-------------------+                   +-------------------+                   +-------------------+
|  Agent 1 (Alpha)  |---[35-tok Ref]--->|   Agent 2 (Beta)  |---[35-tok Ref]--->|  Agent 3 (Gamma)  |
|    Researcher     |                   |     Security      |                   |    Synthesizer    |
+---------+---------+                   +---------+---------+                   +---------+---------+
          | index()                               | search()                              | search()
          v                                       v                                       v
 =====================================================================================================
      Embedded AgentBus: SQLite WAL + FTS5 Hybrid Search (BM25 + Trigram RRF, Zero-Lock Engine)
 =====================================================================================================
```

- **Tiny Handoff Overhead (~35 tokens):** Agents pass compact reference pointers and targeted queries instead of raw transcripts.
- **100% Entity Retention:** Full documents and data records remain indexed in local storage; zero numbers or identifiers are dropped.
- **On-Demand Hybrid Search:** Downstream agents retrieve only the exact snippets required via reciprocal-rank fused BM25 + Trigram lexical search.
- **Zero Network Infrastructure:** Runs locally in-process via SQLite WAL mode with dedicated thread-safe single-writer queue.

---

## Graphic Data: How Much Better Is It?

Empirical benchmarks were executed across 3 realistic multi-agent workflows (N=5 runs per condition with 95% confidence intervals):

### 1. Handoff Token Overhead (Lower is Better)

AgentBus slashes handoff token consumption by **62% to 65%** compared to transcript passing:

```text
Task 1: Market Research Handoff
Condition A (Full Transcript) : [==============================] 296 tokens
Condition B (Lossy Summary)   : [============                  ] 126 tokens  (dropped critical numbers)
Condition C (AgentBus)        : [==========                    ] 105 tokens  [-64.5% reduction, ZERO loss]

Task 2: Security & Code Review
Condition A (Full Transcript) : [============================  ] 278 tokens
Condition B (Lossy Summary)   : [==========                    ] 102 tokens  (dropped CVE identifiers)
Condition C (AgentBus)        : [==========                    ] 105 tokens  [-62.2% reduction, ZERO loss]

Task 3: SRE Incident Response
Condition A (Full Transcript) : [============================= ] 282 tokens
Condition B (Lossy Summary)   : [==========                    ] 102 tokens  (dropped latency metrics)
Condition C (AgentBus)        : [==========                    ] 105 tokens  [-62.8% reduction, ZERO loss]
```

#### Detailed Token Measurements:
| Benchmark Task | Condition A (Transcript) | Condition B (Summary) | Condition C (AgentBus) | **AgentBus Token Savings** |
| :--- | :---: | :---: | :---: | :---: |
| **Market Research Handoff** | 296.0 +/- 0.0 tok | 126.0 tok | **105.0 +/- 0.0 tok** | **-64.5%** |
| **Security Audit & Code Review** | 278.0 +/- 0.0 tok | 102.0 tok | **105.0 +/- 0.0 tok** | **-62.2%** |
| **SRE Incident Response** | 282.0 +/- 0.0 tok | 102.0 tok | **105.0 +/- 0.0 tok** | **-62.8%** |
| **Average Across All Tasks** | **285.3 tok** | **110.0 tok** | **105.0 tok** | **-63.2%** |

---

### 2. Multi-Agent Context Scaling Over Time (O(N^2) vs O(1))

As the number of agent handoffs increases, passing transcripts blows up quadratically, while AgentBus handoffs remain flat:

```text
Total Tokens Transferred Across Handoff Steps:

Tokens
 15,000 |                                                         * Condition A (Transcripts: O(N^2))
        |                                                        /
 10,000 |                                                       /
        |                                                      /
  5,000 |                                            *        /
        |                                           /
  2,000 |                             *            /
        |                            /
  1,000 |               *           /             . Condition B (Summaries: ~1,100t, lossy)
    500 |  *           /           /             .
      0 +--+-----------+-----------+-------------+-----------------+--- Condition C (AgentBus: ~350t, lossless O(1))
         Hop 1       Hop 2       Hop 3         Hop 5             Hop 10
```

| Number of Handoffs | Condition A (Full Transcript) | Condition B (LLM Summary) | Condition C (AgentBus) | AgentBus Savings vs A |
| :---: | :---: | :---: | :---: | :---: |
| **1 Handoff** | ~300 tokens | ~110 tokens | **~35 tokens** | **-88.3%** |
| **3 Handoffs** | ~2,100 tokens | ~330 tokens | **~105 tokens** | **-95.0%** |
| **5 Handoffs** | ~5,500 tokens | ~550 tokens | **~175 tokens** | **-96.8%** |
| **10 Handoffs** | ~18,000+ tokens | ~1,100 tokens (heavily degraded) | **~350 tokens** | **-98.1%** |

---

### 3. Retrieval Precision & Fact Retention

AgentBus preserves 100% of critical numbers, CVEs, and identifiers while ensuring the receiving agent's top retrieved snippet answers the question immediately:

```text
Recall@5 (Ability to locate critical facts & numbers):
Condition A (Full Transcripts) : [====================] 100%  (High context cost & distractors)
Condition B (Lossy Summary)    : [=============.......]  67%  (33% of numbers & IDs permanently lost!)
Condition C (AgentBus)         : [====================] 100%  [ZERO factual loss, minimal context]

Mean Reciprocal Rank (MRR - Target entity ranked at #1 position):
Condition B (Lossy Summary)    : [==========..........] 0.500
Condition C (AgentBus)         : [====================] 1.000 (Target fact returned in rank #1 every time)
```

---

### 4. Comprehensive Feature & Architecture Comparison

| Architectural Dimension | Condition A: Full Transcript | Condition B: LLM Summary | Condition C: AgentBus |
| :--- | :---: | :---: | :---: |
| **Token Scaling** | Exponential O(N^2) | Linear O(N) | **Flat O(1) Reference Pointer** |
| **Information Retention** | 100% until context limits | ~67% (Lossy, drops details) | **100.0% Exact Retention** |
| **Target Fact Retrieval (Recall@5)** | 100.0% | 66.7% | **100.0%** |
| **Mean Reciprocal Rank (MRR)** | N/A (Linear Scan) | 0.500 | **1.000** |
| **Cross-Agent Prompt Injection** | **Vulnerable** (Raw text passed) | **Vulnerable** (Summary poisoning) | **Protected ([SEC-5] Enforced Badges)** |
| **Access Control (ACLs)** | None (All or nothing) | None (All or nothing) | **Hierarchical Namespaces (`team:*`, `run:*`)** |
| **Storage Architecture** | Ephemeral context memory | Ephemeral context memory | **Embedded SQLite WAL (Zero Lock Engine)** |
| **Network Infrastructure Required** | None | Extra LLM inference calls | **None (100% Embedded & Local)** |
| **Framework Integrations** | Ad-hoc strings | Ad-hoc strings | **LangGraph BaseStore + LangChain Retriever** |

*For complete benchmark methodology and raw test traces, see [`docs/reports/benchmark_report.md`](docs/reports/benchmark_report.md).*

---

## Workflow Sequence

```mermaid
sequenceDiagram
    autonumber
    actor A1 as Agent 1 (Researcher)
    actor A2 as Agent 2 (Synthesizer)
    participant Bus as AgentBus (SQLite WAL + FTS5)

    Note over A1,Bus: 1. Index findings locally
    A1->>Bus: index(content="Acme Corp reported 12.4% YoY growth...", agent="A1")
    Bus-->>A1: returns source_id="src_101"

    Note over A1,A2: 2. Lightweight Handoff (~35 tokens)
    A1->>A2: handoff(refs=["src_101"], query="Acme Corp growth", note="Check financials")

    Note over A2,Bus: 3. On-demand hybrid search
    A2->>Bus: search(query="Acme Corp growth", k=3)
    Bus-->>A2: [TRUST: verified] "Acme Corp reported 12.4% YoY growth..."
```

---

## Installation

```bash
# Core embedded storage engine
pip install agentbus

# With LangGraph integration
pip install agentbus[langgraph]

# With all framework adapters & tools
pip install agentbus[all]
```

---

## Quickstart

### 1. Direct Python API

```python
from agentbus.core import Bus

# Open an embedded memory bus
with Bus(db_path="./memory.db") as bus:
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
```

---

### 2. LangGraph Integration (`BaseStore`)

AgentBus provides an official drop-in `BaseStore` implementation for LangGraph state machines:

```python
from agentbus.langgraph import AgentBusStore
from langgraph.graph import StateGraph

# Attach AgentBus as persistent backing store
store = AgentBusStore(db_path="./graph_memory.db")

# Key-value operations with automatic FTS5 lexical indexing
store.put(
    ("research", "run_01"),
    key="competitor_intel",
    value={"summary": "Acme Corp grew 12.4% YoY", "confidence": 0.95},
)

# Hybrid search across stored state items
items = store.search(("research", "run_01"), query="Acme growth", limit=5)
```

---

### 3. LangChain Integration (`BaseRetriever` + Tools)

```python
from agentbus.core import Bus
from agentbus.langchain import AgentBusRetriever, bus_search, bus_handoff

bus = Bus(db_path="./memory.db")

# 1. LCEL Retriever with mandatory Trust Badges
retriever = AgentBusRetriever(bus=bus, namespace=("team_alpha",), k=5)
docs = retriever.invoke("security vulnerabilities")

# 2. Model Tool-calling
tools = [bus_search, bus_handoff]
```

---

## Repository Documentation Map

All project documentation is structured under [`docs/`](docs/):

```text
Agent-bus/
|-- README.md                      <- You are here: project overview, graphic data & quickstart
|-- CLAUDE.md                      <- Development guidelines, commands & security rules
|-- PLAYBOOK_PROGRESS.md           <- Living playbook execution tracker (Steps 1-10 Done)
|-- Makefile                       <- Automated test & check runners
|-- pyproject.toml                 <- Packaging and dependency configurations
|-- intent/
|   \-- intent.md                  <- Core project intent & Phase 0 discovery answers
|-- docs/
|   |-- specs/
|   |   |-- prd.md                 <- Original Product Requirements Document
|   |   \-- spec.md                <- Detailed system specification & NFRs
|   |-- plans/
|   |   |-- plan_phase1.md         <- Phase 1 Core Store architecture & execution plan
|   |   |-- plan_phase2.md         <- Phase 2 LangGraph/LangChain adapter plan
|   |   \-- plan_phase3.md         <- Phase 3 Evaluation benchmark methodology
|   \-- reports/
|       |-- benchmark_report.md    <- Empirical benchmark metrics & token savings
|       \-- review.md              <- Three-pass PR review audit logs (Approved)
|-- src/agentbus/                  <- Source code
|   |-- core/                      <- SQLite WAL storage engine & hybrid FTS5
|   |-- langgraph/                 <- LangGraph BaseStore & ready-made nodes
|   \-- langchain/                 <- LangChain BaseRetriever & tools
\-- tests/                         <- Test suite (89% coverage, 28 tests)
```

---

## Test Suite & CI

```bash
# Fast unit & adapter tests
pytest -k "not concurrency"

# Full concurrency stress test (8 readers + 4 writers, 60 seconds)
pytest tests/test_concurrency.py -v

# Crash-safety & WAL integrity check (SIGKILL simulation)
pytest tests/test_crash_safety.py -v

# Full coverage report
pytest --cov=src/agentbus --cov=eval
```

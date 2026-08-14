# Energy Intelligence RAG — Architecture

## 1. System Overview

The system uses a multi-agent architecture to answer natural-language questions over both structured energy-consumption data and unstructured documents.

```text
                              USER QUERY
                                  │
                                  ▼
                        ┌───────────────────┐
                        │   REFINER AGENT   │
                        │                   │
                        │ • Understand intent
                        │ • Resolve ambiguity
                        │ • Define metrics
                        │ • Convert vague terms
                        │   into technical criteria
                        └─────────┬─────────┘
                                  │
                           REFINED QUERY
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
          ┌──────────────────┐         ┌──────────────────┐
          │    DOCS AGENT    │         │    DATA AGENT    │
          │                  │         │                  │
          │ • RAG            │         │ • Query planning │
          │ • Document       │         │ • DuckDB queries │
          │   retrieval      │         │ • Data analysis  │
          │ • PDF/text       │         │ • Aggregation    │
          └────────┬─────────┘         └────────┬─────────┘
                   │                            │
                   │                            │
                   └─────────────┬──────────────┘
                                 ▼
                       ┌─────────────────────┐
                       │   RESPONSE AGENT    │
                       │                     │
                       │ • Original query    │
                       │ • Refined query     │
                       │ • Document evidence │
                       │ • Data results      │
                       │ • Generate response │
                       └──────────┬──────────┘
                                  │
                                  ▼
                                USER
```

---

## 2. Refiner Agent

The Refiner Agent is the entry point after the user's query.

Its responsibilities are:

* Understand the user's intent.
* Identify required information and operations.
* Resolve or expose ambiguity.
* Convert vague natural-language terms into measurable technical criteria.
* Identify whether the query requires document retrieval, structured data analysis, or both.
* Produce a highly specific query/plan for downstream agents.

### Example

User:

> "Find households with unusually high consumption."

The Refiner Agent should determine what "unusually high" means rather than allowing downstream components to make an arbitrary interpretation.

A refined query may define a statistical criterion such as:

```text
metric: daily_energy_mean
condition: value > household_mean + 2 × household_std
group_by: LCLid
```

If the ambiguity materially affects the result, the system can ask the user for clarification.

### Example structured output

```json
{
  "intent": "identify_high_consumption_households",
  "metric": "daily_energy_mean",
  "definition": {
    "type": "statistical_threshold",
    "condition": "value > household_mean + 2 * household_std"
  },
  "time_range": null,
  "group_by": ["LCLid"],
  "requires_docs": true,
  "requires_data": true
}
```

---

## 3. Docs Agent

The Docs Agent handles unstructured information.

### Responsibilities

* Perform Retrieval-Augmented Generation (RAG).
* Search relevant PDF and text documents.
* Retrieve relevant chunks.
* Return source evidence and metadata.
* Provide the retrieved information to the Response Agent.

### Output

The agent should return structured evidence rather than an unrestricted natural-language response.

Example:

```json
{
  "sources": [
    {
      "text": "Retrieved document content...",
      "source": "report.pdf",
      "page": 12,
      "relevance": 0.91
    }
  ]
}
```

---

## 4. Data Agent

The Data Agent handles structured energy-consumption data.

The system uses DuckDB for analytical queries over the large structured dataset.

### Responsibilities

* Convert the Refiner Agent's structured query plan into DuckDB queries.
* Execute one or more queries when required.
* Perform aggregations, filtering, comparisons, statistical analysis, and other deterministic operations.
* Return exact results to the Response Agent.

### Example

Refined query:

```text
metric: daily_energy_mean
group_by: LCLid
condition: value > household_mean + 2 × household_std
```

The Data Agent converts this into one or more DuckDB operations.

The LLM should generate a **query plan**, while the application validates and executes the resulting queries.

Example:

```json
{
  "queries": [
    {
      "purpose": "calculate_household_baseline",
      "sql": "..."
    },
    {
      "purpose": "identify_outliers",
      "sql": "..."
    }
  ]
}
```

This keeps numerical analysis deterministic and prevents the Response Agent from inventing numerical results.

---

## 5. Response Agent

The Response Agent is responsible for synthesizing the final response.

It receives:

```text
Original user query
        +
Refined query
        +
Retrieved document evidence
        +
DuckDB results
```

It then produces:

* A clear natural-language answer.
* Appropriate explanation of the methodology/interpretation.
* Evidence and sources.
* Relevant visualizations when applicable.
* Any assumptions made by the Refiner Agent.

### Example

```text
User:
"Find unusually high-consumption households."

Response:

"I interpreted 'unusually high' as daily mean consumption
exceeding the household's baseline by 2 standard deviations.

23 households matched this criterion.

[Visualization]

Sources:
- ...
```

The response should make the interpretation visible rather than silently hiding assumptions.

---

## 6. Agent Routing

The Refiner Agent determines which downstream agents are required.

### Data-only query

```text
User
 ↓
Refiner
 ↓
Data Agent
 ↓
Response Agent
 ↓
User
```

Example:

> "Which household had the highest average consumption in October?"

### Document-only query

```text
User
 ↓
Refiner
 ↓
Docs Agent
 ↓
Response Agent
 ↓
User
```

Example:

> "What does the energy-efficiency report say about conservation?"

### Combined query

```text
                         Refiner
                            │
                   ┌────────┴────────┐
                   ▼                 ▼
               Docs Agent        Data Agent
                   │                 │
                   └────────┬────────┘
                            ▼
                      Response Agent
                            │
                            ▼
                           User
```

Example:

> "According to the reports, why might households with high evening consumption show increased daily usage?"

---

## 7. Data Architecture

The energy dataset contains multiple levels of granularity:

```text
DAILY
~11 CSV blocks
~25,600 rows/block
        │
        └── Daily statistical summaries


HHBLOCK
~111 CSV blocks
~25,000 rows/block
        │
        └── 48 half-hour measurements per household/day


HALFHOURLY
~111 CSV blocks
~1.2M rows/block
        │
        └── Raw half-hourly measurements
```

The structured data is intended to be queried analytically rather than embedding every raw measurement.

A conceptual storage architecture is:

```text
                    ENERGY DATA
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
        DAILY         HHBLOCK       HALFHOURLY
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                    Parquet files
                         │
                         ▼
                       DuckDB
```

---

## 8. RAG Architecture

Embeddings are used for semantic retrieval of relevant unstructured information and selected structured semantic chunks.

The system should avoid generating embeddings for every raw half-hourly measurement.

Conceptually:

```text
Documents / semantic chunks
          │
          ▼
      Embeddings
          │
          ▼
     Vector Index
          │
          ▼
    Semantic Retrieval
          │
          ▼
       Docs Agent
```

DuckDB remains responsible for exact numerical operations over the structured energy data.

---

## 9. End-to-End Flow

```text
1. User submits natural-language query
              ↓
2. Refiner Agent understands intent
              ↓
3. Refiner resolves or exposes ambiguity
              ↓
4. Refined query/plan is generated
              ↓
5. Refined plan is routed to:
       ├── Docs Agent
       └── Data Agent
              ↓
6. Docs Agent performs RAG retrieval
              ↓
7. Data Agent generates and executes DuckDB queries
              ↓
8. Results from both agents are collected
              ↓
9. Response Agent receives:
       ├── Original query
       ├── Refined query
       ├── Document evidence
       └── Data results
              ↓
10. Response Agent generates final answer
              ↓
11. UI presents:
       ├── Answer
       ├── Sources/evidence
       └── Visualization when appropriate
```

## 10. Design Principles

1. **The LLM interprets; DuckDB calculates.**
2. **Ambiguity should be exposed rather than silently ignored.**
3. **Structured numerical results should come from deterministic queries.**
4. **RAG should retrieve evidence rather than replace analytical queries.**
5. **Only invoke the agents required for the current query.**
6. **The final response should expose important assumptions and sources.**
7. **Visualizations should be generated from actual retrieved/query results, not fabricated by the LLM.**

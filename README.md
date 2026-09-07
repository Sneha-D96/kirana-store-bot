# Kirana Store AI Autonomous Manager

An autonomous, multi-tool retail management agent built on LangGraph and Groq, designed to handle strict SQLite database grounding, oversell guards, ACID billing transactions, and real document artifacts.

## 1. The Harness and Why
This system uses **LangGraph** (`create_react_agent`) combined with LangChain and ChatOpenAI (`openai/gpt-oss-20b`) via Groq.
* **Why LangGraph?** Traditional LLM apps fail when handling multi-step retail transactions. LangGraph provides stateful, graph-based execution with a built-in `MemorySaver` checkpointer. This ensures conversation threads remain coherent across sessions, tracks tool outputs reliably, and allows strict sequential parsing of multi-command chat inputs.

## 2. Control Loop Architecture
The system operates through a structured ReAct control loop:
1. **Compound Message Splitting:** Incoming multi-command messages are parsed by splitting on `·` to guarantee strict sequential execution.
2. **Stateful Graph Invocation:** Each sub-command runs through the LangGraph engine maintaining session thread context via `MemorySaver`.
3. **Tool Dispatch & DB Grounding:** The model selects appropriate tools, executing raw SQL or ACID transactions directly on the SQLite backend.

## 3. Skill & Tool Design
* **`receive_stock`**: Registers incoming inventory or new items, rejecting entries missing Cost Price (CP), MRP, or GST.
* **`query_stock`**: Fetches inventory stock levels and pricing from the DB.
* **`check_low_stock`**: Flags items dipping below threshold levels.
* **`cut_bill`**: Executes multi-item billing with atomic inventory deduction and tax splitting.
* **`manage_khata`**: Manages customer credit ledgers (`add`, `pay`, `balance`).
* **`set_preference` / `get_preferences`**: Handles standing persistent settings.
* **`daily_close`**: Summarizes daily sales and payment splits.
* **`generate_latest_invoice_pdf`**: Compiles professional monochrome PDF invoices.
* **`generate_sales_deck`**: Builds PowerPoint slide decks with native charts and velocity metrics.

## 4. Solving Hard Technical Challenges
* **Grounding:** All prices, stock counts, and GST slabs are queried directly from the SQLite database; the model never hallucinates values.
* **Oversell Guard:** Built-in SQL transactions (`BEGIN TRANSACTION;`) and stock checks ensure billing requests exceeding stock are rolled back instantly at the tool layer.
* **GST Correctness:** Item totals are programmatically reverse-calculated into base prices and split evenly into CGST and SGST.
* **Multi-turn & Idempotency:** Carts and sequential flows are managed safely across messages without double-decrementing stock.
* **Concurrency Control:** SQLite transactions isolate operations to prevent race conditions during simultaneous sales or stock updates.
* **Guardrails:** Explicit validation blocks sales below cost, unauthorized deletions, or non-existent khata actions.
* **Real Artifacts:** Uses ReportLab and `python-pptx` to programmatically generate actual PDF invoices and PowerPoint analysis decks.
* **Session Memory:** Persistent tables (`preferences`, `khata`) store state outside the immediate context window so settings survive across chat restarts.
import os
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
import tools

@tool
def receive_stock(sku_name: str, quantity: int = 1, cost_price: float = 0.0, mrp: float = 0.0, gst_percent: float = -1.0) -> str:
    """Receive new stock or add a new product. 
    If the user hasn't provided cost, mrp, or gst, pass 0.0 or -1.0."""
    return tools.receive_stock(sku_name, quantity, cost_price, mrp, gst_percent)

@tool
def query_stock(sku_name: str = "") -> str:
    """Check remaining quantity or list inventory for a specific item name."""
    return tools.query_stock(sku_name)

@tool
def check_low_stock(threshold: int = 10) -> str:
    """Check what items are running out of stock."""
    return tools.check_low_stock(threshold)

@tool
def cut_bill(items: list, payment_mode: str = "UPI", customer_name: str = "") -> str:
    """Create a bill and deduct stock items."""
    return tools.cut_bill(items, payment_mode, customer_name)

@tool
def manage_khata(customer_name: str, action: str, amount: float = 0.0) -> str:
    """Manage customer credit ledger. Actions: 'add' (put on credit), 'pay' (customer paid), 'balance' (check debt)."""
    return tools.manage_khata(customer_name, action, amount)

@tool
def set_preference(key: str, value: str) -> str:
    """Save a standing store preference or default setting persistently."""
    return tools.set_preference(key, value)

@tool
def get_preferences() -> str:
    """Get all saved store preferences."""
    return tools.get_preferences()

@tool
def daily_close() -> str:
    """Summarize today's sales, tax collected, and cash vs UPI split."""
    return tools.daily_close()

@tool
def generate_latest_invoice_pdf() -> str:
    """Generate a clean PDF document invoice for the latest bill."""
    return tools.generate_latest_invoice_pdf()

@tool
def generate_sales_deck() -> str:
    """Generate a PowerPoint (PPTX) sales analysis deck."""
    return tools.generate_sales_deck()

llm = ChatOpenAI(
    api_key="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",
    base_url="https://api.groq.com/openai/v1",
    model="openai/gpt-oss-20b",
    temperature=0.1
)

toolkit = [
    receive_stock, query_stock, check_low_stock, cut_bill, 
    manage_khata, set_preference, get_preferences, daily_close,
    generate_latest_invoice_pdf, generate_sales_deck
]

saved_prefs = tools.get_preferences()

system_prompt = (
    "You are the autonomous AI manager for Kirana Store. "
    "You manage inventory, create bills, track customer credit (khata), and generate reports. "
    "MANDATORY RULE: Never answer inventory questions from memory; ALWAYS use the tools. "
    f"PERSISTENT PREFERENCES: [{saved_prefs}]\n\n"
    "CRITICAL RULES: \n"
    "1. AMBIGUITY & CLARIFICATION: If a request is genuinely ambiguous (e.g., 'add atta' or 'give me oil'), DO NOT guess the specific brand, variant, or quantity. Ask a natural clarifying question first.\n"
    "2. RECEIVE STOCK & NEW PRODUCTS: If `receive_stock` returns 'DATABASE REJECTED', relay that exact error to the user and ask for the missing values.\n"
    "3. BILLING VS INVOICES (CRITICAL): Use `cut_bill` ONLY when creating a new purchase with a list of items. If the user asks for a 'PDF', 'invoice', or says 'generate bill' immediately AFTER an order is completed, use `generate_latest_invoice_pdf`. Do NOT call `cut_bill` without items.\n"
    "4. REPORTS & DECKS: If the user asks for a 'deck', 'PPTX', 'presentation', or 'sales analysis', ALWAYS use the `generate_sales_deck` tool.\n"
    "5. EDIT BILL MID-BUILD: If the user modifies an order before finalizing, update your internal cart and then call `cut_bill`.\n"
    "6. KHATA: Map requests properly. 'Put 500 on Ramesh's credit' -> action='add'. 'Ramesh paid 300' -> action='pay'. 'Ramesh's balance' -> action='balance'.\n"
    "7. PREFERENCES: Always assume UPI as default payment unless preferences dictate otherwise. Save user preferences using `set_preference`.\n"
    "8. FORMATTING: When presenting a text bill, format EXACTLY like this (NO store name, NO customer name, NO markdown tables):\n\n"
    "**Bill #<id>**\n"
    "- <qty>x <item_name>\n"
    "- <qty>x <item_name>\n\n"
    "**Total:** ₹<total_amount> (CGST: ₹<cgst>, SGST: ₹<sgst>)\n"
    "**Payment Mode:** <mode>"
)

memory = MemorySaver()

agent_executor = create_react_agent(
    model=llm, 
    tools=toolkit, 
    prompt=system_prompt,
    checkpointer=memory
)

def run_agent(user_message, user_id="default_user"):
    try:
        config = {"configurable": {"thread_id": str(user_id)}}
        prompt = user_message[-1].get("content", "") if isinstance(user_message, list) else str(user_message)
        
        # Split compound messages by '·' to ensure strict sequential execution
        sub_prompts = [p.strip() for p in prompt.split("·") if p.strip()]
        
        final_reply = ""
        file_path = None
        
        for sub_prompt in sub_prompts:
            result = agent_executor.invoke(
                {"messages": [("user", sub_prompt)]}, 
                config=config
            )
            
            # Concatenate replies so the user sees the outcome of every chained command
            current_reply = result["messages"][-1].content
            if final_reply:
                final_reply += "\n\n" + current_reply
            else:
                final_reply = current_reply
            
            recent_messages = result["messages"][-4:]
            for msg in recent_messages:
                if hasattr(msg, "type") and msg.type == "tool" and isinstance(msg.content, str):
                    if (".pdf" in msg.content or ".pptx" in msg.content) and os.path.exists(msg.content.strip()):
                        file_path = msg.content.strip()
                        break
                        
        return final_reply, file_path
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return f"System Error: {str(e)[:200]}", None
"""
Main Entry Point & User Interface

Provides CLI interface for interacting with the AI agent.
"""


import time




# ═══════════════════════════════════════════════════════════════════════════════
# TYPING EFFECTS (UI UTILITIES)
# ═══════════════════════════════════════════════════════════════════════════════

def type_out(text: str, delay: float = 0.02):
    """
    Print text with typing effect.
    
    Args:
        text: Text to print
        delay: Delay between characters (seconds)
    """
    for char in text:
        print(char, end="", flush=True)
        time.sleep(delay)
    print()


def type_list(items: list, delay: float = 0.5):
    """
    Print list items with typing effect.
    
    Args:
        items: List of items to print
        delay: Delay between items (seconds)
    """
    for i, item in enumerate(items, start=1):
        print(f"  {i}. ", end="", flush=True)
        type_out(item, delay=0.02)
        if delay > 0:
            time.sleep(delay)



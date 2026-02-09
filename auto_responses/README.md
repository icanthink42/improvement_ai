# Auto Response System

This directory contains auto response handlers that are automatically called for every message the bot receives.

## How It Works

1. Every `.py` file in this directory (except `__init__.py`) is automatically loaded
2. Each file must have an `async def handle_message(ctx)` function
3. This function is called for every message with full context
4. Return `True` if your handler processed the message, `False` otherwise

## Context Object

The `ctx` parameter is an `AutoResponseContext` object with these attributes:

- `ctx.message` - The full Discord message object
- `ctx.bot` - The Discord bot instance
- `ctx.llm` - The Claude LLM instance (if configured)
- `ctx.author` - Message author (User object)
- `ctx.channel` - Channel where message was sent
- `ctx.content` - Message content string
- `ctx.guild` - Guild/Server object

## Creating a New Auto Response

Create a new file in this directory (e.g., `my_response.py`):

```python
"""
Description of what this auto response does
"""

async def handle_message(ctx):
    """
    Your handler logic here
    
    Args:
        ctx: AutoResponseContext object
        
    Returns:
        bool: True if handled, False otherwise
    """
    # Check if message matches your criteria
    if 'trigger_word' in ctx.content.lower():
        # Send a response
        await ctx.channel.send("Your response here!")
        return True
    
    return False
```

## Examples Included

- `example_hello.py` - Responds to greetings like "hello", "hi"
- `example_reactions.py` - Adds emoji reactions to messages with keywords
- `example_keyword_response.py` - Responds to "good bot" / "bad bot"
- `example_llm_trigger.py` - Triggers LLM without @mention for certain phrases

## Tips

- Use `return False` if your handler doesn't process the message
- Multiple handlers can process the same message
- Auto responses run BEFORE the @mention LLM handler
- Be careful with broad triggers to avoid spam
- Use `try/except` blocks for error handling
- You can access the LLM with `ctx.llm` for AI responses
- Check `if ctx.llm:` before using LLM features

## Disabling an Auto Response

Simply rename the file to not end with `.py` (e.g., `example_hello.py.disabled`)

## Reloading Handlers

Restart the bot to reload all handlers. Hot-reloading may be added in the future.

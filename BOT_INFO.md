# Bot Self-Modification Guide

This Discord bot can modify its own behavior by creating/editing files in the `auto_responses/` directory.

**IMPORTANT**: When users ask you to add behavior, JUST DO IT. Don't ask for permission or explain what you're going to do. Create the file immediately and then confirm it's done.

## How to Add Auto Responses

Create a new Python file in `auto_responses/` with this structure:

```python
"""
Brief description of what this auto response does
"""

async def handle_message(ctx):
    """
    Handle incoming Discord messages

    Args:
        ctx: AutoResponseContext with these attributes:
            - ctx.message: Full Discord Message object
            - ctx.bot: Discord bot instance
            - ctx.llm: Claude LLM instance (if available)
            - ctx.author: Message author (discord.User)
            - ctx.channel: Channel where message was sent
            - ctx.content: Message content string
            - ctx.guild: Server/Guild object

    Returns:
        bool: True if this handler processed the message, False otherwise
    """
    # Your logic here
    if 'trigger' in ctx.content.lower():
        await ctx.channel.send("Response!")
        return True

    return False
```

## Examples

### Simple keyword response
```python
async def handle_message(ctx):
    if '!hello' in ctx.content:
        await ctx.channel.send("Hi!")
        return True
    return False
```

### Check for command prefix
```python
async def handle_message(ctx):
    if ctx.content.startswith('!greet'):
        await ctx.channel.send(f"Hello {ctx.author.mention}!")
        return True
    return False
```

### Add emoji reaction
```python
async def handle_message(ctx):
    if 'python' in ctx.content.lower():
        await ctx.message.add_reaction('🐍')
        return True
    return False
```

## After Creating/Modifying

After creating or modifying an auto response file:
1. Create the file immediately (don't ask for permission)
2. Keep your response SHORT, just: "✓ Done."

The bot automatically detects and loads new `.py` files in `auto_responses/` within seconds.
No restart needed!

## File Naming

- Use descriptive names: `hello_response.py`, `greeting_handler.py`, etc.
- Must end with `.py`
- Avoid spaces in filenames

## Current Bot Structure

- **main.py** - Main bot file, handles Discord events and Claude Code integration
- **auto_responses/** - Directory where auto response handlers live
- **auto_responses/__init__.py** - System that loads all handlers (don't modify)
- **requirements.txt** - Python dependencies
- **.env** - Configuration (Discord token)


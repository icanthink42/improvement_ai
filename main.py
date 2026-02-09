import discord
from discord.ext import commands
import os
import sys
import json
from dotenv import load_dotenv
from auto_responses import load_all_handlers, get_handler
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, HookMatcher

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# Bot setup with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Project directory
project_dir = os.path.dirname(os.path.abspath(__file__))

# Auto-approve hook for all tool usage
async def auto_approve_hook(input_data, tool_use_id, context):
    """Automatically approve all tool usage without asking"""
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": "Auto-approved by bot"
        }
    }

# Claude Code client options
claude_options = ClaudeAgentOptions(
    # Allow all tools - Claude Code has filesystem, shell, browser, etc.
    allowed_tools="*",
    # Set working directory to project root
    cwd=project_dir,
    # Auto-approve all tool usage
    hooks={
        "PreToolUse": [
            HookMatcher(matcher="*", hooks=[auto_approve_hook])
        ]
    }
)

# Store active Claude sessions per channel
claude_sessions = {}

# Conversation history file
HISTORY_FILE = os.path.join(project_dir, '.conversation_history.json')
conversation_history = {}

# Load conversation history from disk
def load_conversation_history():
    global conversation_history
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                conversation_history = json.load(f)
            print(f"✓ Loaded conversation history for {len(conversation_history)} channels")
    except Exception as e:
        print(f"Warning: Could not load conversation history: {e}")
        conversation_history = {}

# Save conversation history to disk
def save_conversation_history():
    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(conversation_history, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save conversation history: {e}")

# Add message to history
def add_to_history(channel_id: str, role: str, content: str):
    if channel_id not in conversation_history:
        conversation_history[channel_id] = []
    conversation_history[channel_id].append({
        'role': role,
        'content': content
    })
    # Keep last 50 messages per channel
    if len(conversation_history[channel_id]) > 50:
        conversation_history[channel_id] = conversation_history[channel_id][-50:]
    save_conversation_history()

# Check for restart request
RESTART_FLAG = os.path.join(project_dir, '.restart_bot')

def check_restart_request():
    if os.path.exists(RESTART_FLAG):
        os.remove(RESTART_FLAG)
        return True
    return False

# Restart the bot
async def restart_bot():
    print("\n🔄 Bot restart requested...")
    # Cleanup sessions
    for session in claude_sessions.values():
        try:
            await session.__aexit__(None, None, None)
        except:
            pass
    # Restart using the same Python interpreter and script
    os.execv(sys.executable, [sys.executable] + sys.argv)

# Load history on startup
load_conversation_history()

# Load auto response handlers
print("\nLoading auto response handlers...")
load_all_handlers()
auto_response_handler = get_handler()

# Auto-reload check - track when handlers were last loaded
import time
last_reload_check = time.time()
RELOAD_CHECK_INTERVAL = 5  # seconds


@bot.event
async def on_ready():
    """Event handler for when the bot is ready"""
    print(f'\n{"="*50}')
    print(f'{bot.user} has connected to Discord!')
    print(f'{"="*50}')
    print(f'Guilds: {len(bot.guilds)}')
    print(f'Claude Code: ✓ Using Official SDK')
    print(f'Auto responses: {len(auto_response_handler.handlers)}')
    print(f'{"="*50}')
    print('Bot is ready to receive messages!\n')


async def get_claude_client(channel_id: str) -> ClaudeSDKClient:
    """Get or create a Claude client for a channel"""
    if channel_id not in claude_sessions:
        client = ClaudeSDKClient(options=claude_options)
        await client.__aenter__()  # Initialize the session
        claude_sessions[channel_id] = client

        # Note: Claude Code maintains its own session context
        # We save history for reference but don't need to replay it
        if channel_id in conversation_history:
            print(f"📚 Channel has {len(conversation_history[channel_id])} saved messages")

    return claude_sessions[channel_id]


@bot.event
async def on_message(message):
    """Event handler for messages"""
    global last_reload_check

    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Check for restart request
    if check_restart_request():
        await restart_bot()
        return

    # Check if we should reload auto responses
    current_time = time.time()
    if current_time - last_reload_check > RELOAD_CHECK_INTERVAL:
        # Check if auto_responses directory has been modified
        auto_responses_dir = os.path.join(project_dir, 'auto_responses')
        try:
            # Get list of .py files
            py_files = [f for f in os.listdir(auto_responses_dir)
                       if f.endswith('.py') and f != '__init__.py']

            # Check if number of handlers matches number of files
            if len(py_files) != len(auto_response_handler.handlers):
                print(f"\n🔄 Detected changes in auto_responses/, reloading...")
                auto_response_handler.reload()
                print(f"✓ Reloaded! Active handlers: {len(auto_response_handler.handlers)}\n")
        except Exception as e:
            print(f"Error checking for auto response changes: {e}")

        last_reload_check = current_time

    # Process auto responses first - if handled, don't send to Claude
    handled = await auto_response_handler.process_message(message, bot, None)

    # If auto response handled it, we're done
    if handled:
        return

    # Process remaining messages with Claude Code
    content = message.content.strip()

    if not content:
        return

    channel_id = str(message.channel.id)

    # Prepend instructions for first message in channel (only if no history)
    is_first_message = channel_id not in claude_sessions and channel_id not in conversation_history
    if is_first_message:
        content = f"""You are a Discord bot. When users ask you to do something, DO IT IMMEDIATELY without asking for permission.

IMPORTANT CAPABILITIES:
- You can modify ANY file in this project, including main.py and your own code
- To restart the bot: create a file called .restart_bot in the project root
- Conversation history persists across restarts automatically
- For adding bot behaviors: Read BOT_INFO.md and create files in auto_responses/

User's message: {content}"""

    # Store user message in history
    add_to_history(channel_id, 'user', content)

    # Show typing indicator
    async with message.channel.typing():
        try:
            client = await get_claude_client(channel_id)

            # Send query to Claude Code (client already initialized, just use it)
            await client.query(content)

            # Collect response
            response_parts = []
            async for msg in client.receive_response():
                # Try different ways to extract text
                if hasattr(msg, 'content'):
                    if isinstance(msg.content, str):
                        response_parts.append(msg.content)
                    elif isinstance(msg.content, list):
                        for block in msg.content:
                            if isinstance(block, str):
                                response_parts.append(block)
                            elif hasattr(block, 'text'):
                                response_parts.append(block.text)
                            elif hasattr(block, 'type') and block.type == 'text':
                                response_parts.append(block.text)
                elif hasattr(msg, 'text'):
                    response_parts.append(msg.text)

            response = '\n'.join(response_parts).strip()

            if not response:
                response = "I processed your request but didn't generate a text response."

            # Store assistant response in history
            add_to_history(channel_id, 'assistant', response)

            # Discord has a 2000 character limit
            if len(response) > 2000:
                # Split into chunks
                chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
                for chunk in chunks:
                    await message.channel.send(chunk)
            else:
                await message.channel.send(response)

        except Exception as e:
            print(f"Error processing message: {e}")
            import traceback
            traceback.print_exc()
            await message.channel.send(f"Sorry, I encountered an error: {str(e)}")

    # Process commands (if any are added in the future)
    await bot.process_commands(message)


async def cleanup():
    """Cleanup Claude sessions on shutdown"""
    print("Cleaning up Claude Code sessions...")
    for session in claude_sessions.values():
        try:
            await session.__aexit__(None, None, None)
        except:
            pass
    print("Done!")


if __name__ == '__main__':
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not found in .env file")
        print("Please create a .env file with your Discord bot token")
    else:
        try:
            bot.run(DISCORD_TOKEN)
        except KeyboardInterrupt:
            print("\n\nShutting down bot...")
            import asyncio
            asyncio.run(cleanup())

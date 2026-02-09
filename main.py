import discord
from discord.ext import commands
import os
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
    return claude_sessions[channel_id]


@bot.event
async def on_message(message):
    """Event handler for messages"""
    global last_reload_check

    # Ignore messages from the bot itself
    if message.author == bot.user:
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

    # Prepend instructions for first message in channel
    is_first_message = channel_id not in claude_sessions
    if is_first_message:
        content = f"""You are a Discord bot. When users ask you to do something, DO IT IMMEDIATELY without asking for permission.

For adding bot behaviors: Read BOT_INFO.md and create files in auto_responses/ directory. Don't explain, just do it and confirm briefly.

User's message: {content}"""

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

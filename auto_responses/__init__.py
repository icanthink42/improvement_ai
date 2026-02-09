"""
Auto Response System

Each file in this directory should define an async function called 'handle_message'
that takes a message context and returns a boolean indicating if it handled the message.

Example structure for an auto response file:

async def handle_message(ctx):
    '''
    ctx contains:
        - message: discord.Message object
        - bot: discord.Bot object
        - llm: ClaudeLLM instance (if available)
    '''
    if some_condition:
        await ctx['message'].channel.send("Response")
        return True  # Message was handled
    return False  # Message was not handled
"""

import os
import importlib.util
from typing import List, Callable, Dict
import discord


class AutoResponseContext:
    """Context object passed to auto response handlers"""

    def __init__(self, message: discord.Message, bot, llm=None):
        self.message = message
        self.bot = bot
        self.llm = llm
        self.author = message.author
        self.channel = message.channel
        self.content = message.content
        self.guild = message.guild

    def to_dict(self) -> Dict:
        """Convert context to dictionary for backwards compatibility"""
        return {
            'message': self.message,
            'bot': self.bot,
            'llm': self.llm,
            'author': self.author,
            'channel': self.channel,
            'content': self.content,
            'guild': self.guild
        }


class AutoResponseHandler:
    """Manages auto response modules"""

    def __init__(self):
        self.handlers: List[Callable] = []
        self.handler_names: List[str] = []

    def load_handlers(self, directory: str = None):
        """Load all auto response handlers from the directory"""
        if directory is None:
            directory = os.path.dirname(__file__)

        self.handlers = []
        self.handler_names = []

        # Get all Python files in the directory except __init__.py
        files = [f for f in os.listdir(directory)
                if f.endswith('.py') and f != '__init__.py']

        for filename in sorted(files):
            filepath = os.path.join(directory, filename)
            module_name = filename[:-3]  # Remove .py extension

            try:
                # Load the module
                spec = importlib.util.spec_from_file_location(module_name, filepath)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Check if module has handle_message function
                    if hasattr(module, 'handle_message'):
                        self.handlers.append(module.handle_message)
                        self.handler_names.append(module_name)
                        print(f"✓ Loaded auto response: {module_name}")
                    else:
                        print(f"⚠ Skipped {module_name}: no handle_message function")

            except Exception as e:
                print(f"✗ Error loading {module_name}: {e}")

        print(f"Loaded {len(self.handlers)} auto response handler(s)")

    async def process_message(self, message: discord.Message, bot, llm=None) -> bool:
        """
        Process a message through all handlers

        Returns:
            True if any handler processed the message, False otherwise
        """
        ctx = AutoResponseContext(message, bot, llm)

        handled = False
        for handler, name in zip(self.handlers, self.handler_names):
            try:
                result = await handler(ctx)
                if result:
                    handled = True
                    # Note: we continue processing even if handled,
                    # so multiple handlers can respond to the same message
                    # Change this behavior if you want to stop after first handler
            except Exception as e:
                print(f"Error in auto response handler '{name}': {e}")

        return handled

    def reload(self):
        """Reload all handlers"""
        self.load_handlers()


# Global handler instance
_handler = AutoResponseHandler()


def get_handler() -> AutoResponseHandler:
    """Get the global auto response handler"""
    return _handler


def load_all_handlers():
    """Load all auto response handlers"""
    _handler.load_handlers()


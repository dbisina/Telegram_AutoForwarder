import asyncio
from telethon import TelegramClient, events, Button
from telethon.tl.custom import Message
import json
import logging
import socket

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BotUI:
    def __init__(self, api_id: str, api_hash: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.bot = TelegramClient('bot_ui', api_id, api_hash)
        self.user_states = {}  # Track user interaction states
        self.config = self.load_config()

    def load_config(self) -> dict:
        try:
            with open('config.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                'forwarding_rules': {},
                'word_replacements': {},
                'blacklist_words': [],
                'approved_words': [],
                'admins': ["1493595978"]  # List of admin user IDs
            }

    def save_config(self):
        with open('config.json', 'w') as f:
            json.dump(self.config, f, indent=4)

    async def start(self, bot_token: str):
        await self.bot.start(bot_token=bot_token)
        
        # Register command handlers
        self.bot.add_event_handler(self.handle_start, events.NewMessage(pattern='/start'))
        self.bot.add_event_handler(self.handle_callback, events.CallbackQuery())
        self.bot.add_event_handler(self.handle_message, events.NewMessage())
        
        logger.info("Bot started!")
        await self.bot.run_until_disconnected()

    async def handle_start(self, event: Message):
        if not await self.is_admin(event.sender_id):
            await event.respond("Sorry, this bot is only for administrators.")
            return

        buttons = [
            [Button.inline("➕ Add Forwarding Rule", b"add_rule")],
            [Button.inline("📋 List Active Rules", b"list_rules")],
            [Button.inline("🔄 Word Replacements", b"word_replace")],
            [Button.inline("⛔ Blacklist Words", b"blacklist")],
            [Button.inline("✅ Approved Words", b"approved")],
            [Button.inline("❌ Stop All Forwards", b"stop_all")]
        ]
        
        await event.respond(
            "🤖 **Welcome to the Message Forwarder Bot!**\n\n"
            "Choose an option from the menu below:",
            buttons=buttons
        )

    async def handle_callback(self, event):
        if not await self.is_admin(event.sender_id):
            await event.answer("Unauthorized access!")
            return

        data = event.data.decode()
        
        if data == "add_rule":
            self.user_states[event.sender_id] = {"state": "awaiting_source"}
            await event.respond(
                "Please forward a message from the source channel/group, or send its ID."
            )
            
        elif data == "list_rules":
            rules = self.config['forwarding_rules']
            if not rules:
                await event.respond("No active forwarding rules.")
                return
                
            text = "**Active Forwarding Rules:**\n\n"
            for source, destinations in rules.items():
                text += f"From: {source}\nTo: {', '.join(destinations)}\n\n"
            
            await event.respond(text, buttons=[
                [Button.inline("🗑️ Delete Rule", b"delete_rule")],
                [Button.inline("◀️ Back to Menu", b"main_menu")]
            ])

        elif data == "word_replace":
            self.user_states[event.sender_id] = {"state": "awaiting_word"}
            await event.respond(
                "Current replacements:\n" +
                "\n".join([f"`{old}` → `{new}`" for old, new in self.config['word_replacements'].items()]) +
                "\n\nEnter a word to replace (or /cancel to go back):"
            )

        elif data == "blacklist":
            words = self.config['blacklist_words']
            await event.respond(
                "**Blacklisted Words:**\n" +
                "\n".join([f"• `{word}`" for word in words]) +
                "\n\nSend words to add to blacklist (comma-separated) or /cancel to go back."
            )

        elif data == "main_menu":
            await self.handle_start(event)

    async def handle_message(self, event: Message):
        if not await self.is_admin(event.sender_id):
            return

        user_id = event.sender_id
        if user_id not in self.user_states:
            return

        state = self.user_states[user_id]["state"]

        if event.message.text == "/cancel":
            del self.user_states[user_id]
            await self.handle_start(event)
            return

        if state == "awaiting_source":
            if event.message.forward:
                source_id = str(event.message.forward.chat_id)
            else:
                source_id = event.message.text

            self.user_states[user_id].update({
                "state": "awaiting_dest",
                "source": source_id
            })
            await event.respond("Now forward a message from the destination channel/group, or send its ID.")

        elif state == "awaiting_dest":
            if event.message.forward:
                dest_id = str(event.message.forward.chat_id)
            else:
                dest_id = event.message.text

            source = self.user_states[user_id]["source"]
            
            # Add the forwarding rule
            if source not in self.config['forwarding_rules']:
                self.config['forwarding_rules'][source] = []
            self.config['forwarding_rules'][source].append(dest_id)
            self.save_config()

            # Communicate with the secondary script to start forwarding
            await self.start_forwarding(source, dest_id)

            del self.user_states[user_id]
            await event.respond(
                "✅ Forwarding rule added successfully!\n\n"
                f"Messages from {source} will be forwarded to {dest_id}",
                buttons=[[Button.inline("◀️ Back to Menu", b"main_menu")]]
            )

    async def start_forwarding(self, source_id: str, dest_id: str):
        # Send a command to the secondary script to start forwarding
        command = f"start_forward:{source_id}:{dest_id}"
        await self.send_command_to_forwarder(command)

    async def stop_forwarding(self, source_id: str, dest_id: str):
        # Send a command to the secondary script to stop forwarding
        command = f"stop_forward:{source_id}:{dest_id}"
        await self.send_command_to_forwarder(command)

    async def send_command_to_forwarder(self, command: str):
        # Connect to the secondary script via TCP socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(('localhost', 65432))  # Connect to the secondary script
                s.sendall(command.encode('utf-8'))  # Send the command
                response = s.recv(1024).decode('utf-8')  # Wait for a response
                logger.info(f"Response from forwarder: {response}")
        except Exception as e:
            logger.error(f"Failed to communicate with forwarder: {e}")

    async def is_admin(self, user_id: int) -> bool:
        return str(user_id) in self.config['admins']

if __name__ == "__main__":
    # Load credentials from config
    with open("credentials.txt") as f:
        api_id = f.readline().strip()
        api_hash = f.readline().strip()
        bot_token = f.readline().strip()

    bot = BotUI(api_id, api_hash)
    asyncio.run(bot.start(bot_token))
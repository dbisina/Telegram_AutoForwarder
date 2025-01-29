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
                await event.respond(
                    "No active forwarding rules.",
                    buttons=[[Button.inline("◀️ Back to Menu", b"main_menu")]]
                )
                return
                
            text = "**Active Forwarding Rules:**\n\n"
            for source, destinations in rules.items():
                text += f"From: {source}\nTo: {', '.join(destinations)}\n\n"
            
            await event.respond(text, buttons=[
                [Button.inline("🗑️ Delete Rule", b"delete_rule")],
                [Button.inline("◀️ Back to Menu", b"main_menu")]
            ])

        elif data == "word_replace":
            replacements = self.config['word_replacements']
            text = "**Current Word Replacements:**\n\n"
            if replacements:
                for old, new in replacements.items():
                    text += f"`{old}` → `{new}`\n"
            else:
                text += "No word replacements configured.\n"
            
            await event.respond(text, buttons=[
                [Button.inline("➕ Add Replacement", b"add_replacement")],
                [Button.inline("🗑️ Delete Replacement", b"delete_replacement")],
                [Button.inline("◀️ Back to Menu", b"main_menu")]
            ])

        elif data == "add_replacement":
            self.user_states[event.sender_id] = {"state": "awaiting_old_word"}
            await event.respond("Enter the word to be replaced:")

        elif data == "delete_replacement":
            replacements = self.config['word_replacements']
            if not replacements:
                await event.respond(
                    "No word replacements to delete.",
                    buttons=[[Button.inline("◀️ Back", b"word_replace")]]
                )
                return

            buttons = [
                [Button.inline(f"❌ {old} → {new}", f"del_replace_{old}")]
                for old, new in replacements.items()
            ]
            buttons.append([Button.inline("◀️ Back", b"word_replace")])
            await event.respond("Select a replacement to delete:", buttons=buttons)

        elif data.startswith("del_replace_"):
            word = data.replace("del_replace_", "")
            if word in self.config['word_replacements']:
                del self.config['word_replacements'][word]
                self.save_config()
                await event.respond(
                    f"Deleted replacement for '{word}'",
                    buttons=[[Button.inline("◀️ Back", b"word_replace")]]
                )

        elif data == "blacklist":
            words = self.config['blacklist_words']
            text = "**Current Blacklisted Words:**\n\n"
            if words:
                for word in words:
                    text += f"• `{word}`\n"
            else:
                text += "No blacklisted words.\n"
            
            await event.respond(text, buttons=[
                [Button.inline("➕ Add Words", b"add_blacklist")],
                [Button.inline("🗑️ Delete Words", b"delete_blacklist")],
                [Button.inline("◀️ Back to Menu", b"main_menu")]
            ])

        elif data == "add_blacklist":
            self.user_states[event.sender_id] = {"state": "awaiting_blacklist"}
            await event.respond("Enter words to blacklist (comma-separated):")

        elif data == "delete_blacklist":
            words = self.config['blacklist_words']
            if not words:
                await event.respond(
                    "No blacklisted words to delete.",
                    buttons=[[Button.inline("◀️ Back", b"blacklist")]]
                )
                return

            buttons = [
                [Button.inline(f"❌ {word}", f"del_blacklist_{word}")]
                for word in words
            ]
            buttons.append([Button.inline("◀️ Back", b"blacklist")])
            await event.respond("Select a word to remove from blacklist:", buttons=buttons)

        elif data.startswith("del_blacklist_"):
            word = data.replace("del_blacklist_", "")
            if word in self.config['blacklist_words']:
                self.config['blacklist_words'].remove(word)
                self.save_config()
                await event.respond(
                    f"Removed '{word}' from blacklist",
                    buttons=[[Button.inline("◀️ Back", b"blacklist")]]
                )

        elif data == "approved":
            words = self.config['approved_words']
            text = "**Current Approved Words:**\n\n"
            if words:
                for word in words:
                    text += f"• `{word}`\n"
            else:
                text += "No approved words.\n"
            
            await event.respond(text, buttons=[
                [Button.inline("➕ Add Words", b"add_approved")],
                [Button.inline("🗑️ Delete Words", b"delete_approved")],
                [Button.inline("◀️ Back to Menu", b"main_menu")]
            ])

        elif data == "add_approved":
            self.user_states[event.sender_id] = {"state": "awaiting_approved"}
            await event.respond("Enter words to approve (comma-separated):")

        elif data == "delete_approved":
            words = self.config['approved_words']
            if not words:
                await event.respond(
                    "No approved words to delete.",
                    buttons=[[Button.inline("◀️ Back", b"approved")]]
                )
                return

            buttons = [
                [Button.inline(f"❌ {word}", f"del_approved_{word}")]
                for word in words
            ]
            buttons.append([Button.inline("◀️ Back", b"approved")])
            await event.respond("Select a word to remove from approved list:", buttons=buttons)

        elif data.startswith("del_approved_"):
            word = data.replace("del_approved_", "")
            if word in self.config['approved_words']:
                self.config['approved_words'].remove(word)
                self.save_config()
                await event.respond(
                    f"Removed '{word}' from approved words",
                    buttons=[[Button.inline("◀️ Back", b"approved")]]
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

        elif state == "awaiting_old_word":
            old_word = event.message.text
            self.user_states[user_id].update({
                "state": "awaiting_new_word",
                "old_word": old_word
            })
            await event.respond(f"Enter the replacement for '{old_word}':")

        elif state == "awaiting_new_word":
            new_word = event.message.text
            old_word = self.user_states[user_id]["old_word"]
            self.config['word_replacements'][old_word] = new_word
            self.save_config()
            del self.user_states[user_id]
            await event.respond(
                f"✅ Added replacement: '{old_word}' → '{new_word}'",
                buttons=[[Button.inline("◀️ Back to Word Replacements", b"word_replace")]]
            )

        elif state == "awaiting_blacklist":
            words = [w.strip() for w in event.message.text.split(",")]
            self.config['blacklist_words'].extend(words)
            self.config['blacklist_words'] = list(set(self.config['blacklist_words']))  # Remove duplicates
            self.save_config()
            del self.user_states[user_id]
            await event.respond(
                f"✅ Added {len(words)} words to blacklist",
                buttons=[[Button.inline("◀️ Back to Blacklist", b"blacklist")]]
            )

        elif state == "awaiting_approved":
            words = [w.strip() for w in event.message.text.split(",")]
            self.config['approved_words'].extend(words)
            self.config['approved_words'] = list(set(self.config['approved_words']))  # Remove duplicates
            self.save_config()
            del self.user_states[user_id]
            await event.respond(
                f"✅ Added {len(words)} words to approved list",
                buttons=[[Button.inline("◀️ Back to Approved Words", b"approved")]]
            )

    async def start_forwarding(self, source_id: str, dest_id: str):
        try:
            # Send a command to the secondary script to start forwarding
            command = f"start_forward:{source_id}:{dest_id}"
            await self.send_command_to_forwarder(command)
        except Exception as e:
            logger.error(f"Failed to start forwarding: {e}")
            await self.bot.send_message(
                int(self.config['admins'][0]),
                f"⚠️ Error starting forwarding from {source_id} to {dest_id}: {str(e)}"
            )

    async def stop_forwarding(self, source_id: str, dest_id: str):
        try:
            # Send a command to the secondary script to stop forwarding
            command = f"stop_forward:{source_id}:{dest_id}"
            await self.send_command_to_forwarder(command)
        except Exception as e:
            logger.error(f"Failed to stop forwarding: {e}")
            await self.bot.send_message(
                int(self.config['admins'][0]),
                f"⚠️ Error stopping forwarding from {source_id} to {dest_id}: {str(e)}"
            )

    async def send_command_to_forwarder(self, command: str):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(('localhost', 65432))
                s.sendall(command.encode('utf-8'))
                response = s.recv(1024).decode('utf-8')
                logger.info(f"Response from forwarder: {response}")
                return response
        except Exception as e:
            logger.error(f"Failed to communicate with forwarder: {e}")
            raise

    async def is_admin(self, user_id: int) -> bool:
        return str(user_id) in self.config['admins']

    async def stop_all_forwards(self):
        """Stop all active forwarding rules"""
        rules = self.config['forwarding_rules'].copy()
        for source, destinations in rules.items():
            for dest in destinations:
                await self.stop_forwarding(source, dest)
        
        self.config['forwarding_rules'] = {}
        self.save_config()

if __name__ == "__main__":
    # Load credentials from config
    with open("credentials.txt") as f:
        api_id = f.readline().strip()
        api_hash = f.readline().strip()
        bot_token = f.readline().strip()

    bot = BotUI(api_id, api_hash)
    asyncio.run(bot.start(bot_token))
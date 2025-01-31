# bot_ui.py
import asyncio
from telethon import TelegramClient, events, Button
from telethon.tl.custom import Message
import json
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_ui.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BotUI:
    def __init__(self):
        self.bot = TelegramClient("bot_ui", API_ID, API_HASH)
        self.user_states = {}
        self.config = self.load_config()
        self.lock = asyncio.Lock()

    def load_config(self) -> dict:
        try:
            with open("config.json", "r", encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            default_config = {
                "forwarding_rules": {},
                "word_replacements": {},
                "blacklist_words": [],
                "approved_words": [],
                'admins': [os.getenv('ADMIN_ID', '')],
                "available_chats": {},
            }
            self.save_config(default_config)
            return default_config

    def save_config(self, config: Optional[dict] = None):
        if config is None:
            config = self.config
        try:
            with open("config.json", "w", encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            raise

    async def start(self):
        """Start the bot and set up event handlers"""
        try:
            await self.bot.start(bot_token=BOT_TOKEN)

            # Register event handlers
            self.bot.add_event_handler(self.handle_start, events.NewMessage(pattern="/start"))
            self.bot.add_event_handler(self.handle_callback, events.CallbackQuery())
            self.bot.add_event_handler(self.handle_message, events.NewMessage())

            logger.info("Bot started successfully!")

            # Run the bot
            await self.bot.run_until_disconnected()
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            raise

    async def handle_start(self, event: Message):
        """Handle /start command"""
        if not await self.is_admin(event.sender_id):
            await event.respond("🚫 Access Denied: This bot is for administrators only.")
            return

        buttons = [
            [
                Button.inline("➕ Add Rule", b"add_rule"),
                Button.inline("📋 List Rules", b"list_rules")
            ],
            [
                Button.inline("🔄 Word Replace", b"word_replace"),
                Button.inline("⛔ Blacklist", b"blacklist")
            ],
            [
                Button.inline("✅ Approved Words", b"approved"),
                Button.inline("❌ Stop All", b"stop_all")
            ],
            [
                Button.inline("🔍 Fetch Available Chats", b"fetch_chats")
            ]
        ]

        await event.respond(
            "🤖 **Message Forwarder Control Panel**\n\n"
            "📱 Select an option to manage your forwarding setup:",
            buttons=buttons
        )

    async def handle_callback(self, event):
        """Handle callback queries from inline buttons"""
        if not await self.is_admin(event.sender_id):
            await event.answer("Unauthorized access!", alert=True)
            return

        try:
            data = event.data.decode()

            if data.startswith("media_"):
                await self.handle_media_preference(event, data)
            elif data == "add_rule":
                await self.handle_add_rule(event)
            elif data == "list_rules":
                await self.handle_list_rules(event)
            elif data == "word_replace":
                await self.handle_word_replace(event)
            elif data == "blacklist":
                await self.handle_blacklist(event)
            elif data == "approved":
                await self.handle_approved_words(event)
            elif data == "stop_all":
                await self.handle_stop_all(event)
            elif data == "fetch_chats":
                await self.handle_fetch_chats(event)
            elif data == "main_menu":
                await self.handle_start(event)
            elif data.startswith("select_source_"):
                await self.handle_source_selection(event, data)
            elif data.startswith("select_dest_"):
                await self.handle_destination_selection(event, data)
            elif data.startswith("del_rule_"):
                await self.handle_rule_deletion(event, data)
            else:
                await event.answer("Unknown command", alert=True)

        except Exception as e:
            logger.error(f"Error in handle_callback: {e}")
            await event.edit(
                "An error occurred. Please try again.",
                buttons=[[Button.inline("◀️ Back to Menu", b"main_menu")]]
            )

    async def handle_add_rule(self, event):
        """Handle adding new forwarding rule"""
        chats = self.config.get('available_chats', {})
        if not chats:
            await event.edit(
                "Please fetch available chats first using the 'Fetch Available Chats' button.",
                buttons=[[Button.inline("◀️ Back to Menu", b"main_menu")]]
            )
            return

        buttons = []
        for chat_id, info in chats.items():
            buttons.append([Button.inline(
                f"📌 {info['title']} ({info['type']})",
                f"select_source_{chat_id}".encode()
            )])
        buttons.append([Button.inline("◀️ Back to Menu", b"main_menu")])

        await event.edit("Select source chat:", buttons=buttons)

    async def handle_source_selection(self, event, data):
        """Handle source chat selection"""
        source_id = data.replace("select_source_", "")
        self.user_states[event.sender_id] = {"state": "selecting_dest", "source": source_id}

        buttons = []
        for chat_id, info in self.config['available_chats'].items():
            if chat_id != source_id:
                buttons.append([Button.inline(
                    f"📌 {info['title']} ({info['type']})",
                    f"select_dest_{chat_id}".encode()
                )])
        buttons.append([Button.inline("◀️ Back", b"add_rule")])

        await event.edit("Select destination chat:", buttons=buttons)

    async def handle_destination_selection(self, event, data):
        """Handle destination chat selection"""
                dest_id = data.replace("select_dest_", "")
        source_id = self.user_states[event.sender_id]["source"]

        # Ask about media forwarding preference
        self.user_states[event.sender_id].update({
            "state": "selecting_media_pref",
            "source": source_id,
            "destination": dest_id
        })

        source_info = self.config['available_chats'][source_id]
        dest_info = self.config['available_chats'][dest_id]

        await event.edit(
            f"📱 **Forward Setup**\n\n"
            f"From: {source_info['title']} (ID: {source_id})\n"
            f"To: {dest_info['title']} (ID: {dest_id})\n\n"
            f"Would you like to forward media (images, videos, etc.) for this rule?",
            buttons=[
                [
                    Button.inline("✅ Yes", f"media_yes_{source_id}_{dest_id}"),
                    Button.inline("❌ No", f"media_no_{source_id}_{dest_id}")
                ],
                [Button.inline("◀️ Back", "add_rule")]
            ]
        )

    async def handle_media_preference(self, event, data):
        """Handle media forwarding preference selection"""
        try:
            _, choice, source_id, dest_id = data.split("_")
            forward_media = choice == "yes"

            async with self.lock:
                if source_id not in self.config['forwarding_rules']:
                    self.config['forwarding_rules'][source_id] = []
                if dest_id not in self.config['forwarding_rules'][source_id]:
                    self.config['forwarding_rules'][source_id].append(dest_id)
                    rule_key = f"{source_id}:{dest_id}"
                    self.config['forward_media_settings'][rule_key] = forward_media
                    self.save_config()

            source_info = self.config['available_chats'][source_id]
            dest_info = self.config['available_chats'][dest_id]

            del self.user_states[event.sender_id]
            await event.edit(
                f"✅ Forwarding rule added successfully!\n\n"
                f"From: {source_info['title']} (ID: {source_id})\n"
                f"To: {dest_info['title']} (ID: {dest_id})\n"
                f"Media Forwarding: {'Enabled' if forward_media else 'Disabled'}",
                buttons=[[Button.inline("◀️ Back to Menu", b"main_menu")]]
            )
        except Exception as e:
            logger.error(f"Error in handle_media_preference: {e}")
            await event.edit(
                "An error occurred. Please try again.",
                buttons=[[Button.inline("◀️ Back to Menu", b"main_menu")]]
            )

    async def handle_list_rules(self, event):
        """Handle listing forwarding rules with extended information"""
        rules = self.config['forwarding_rules']
        if not rules:
            await event.edit(
                "No active forwarding rules.",
                buttons=[[Button.inline("◀️ Back to Menu", b"main_menu")]]
            )
            return

        text = "**Active Forwarding Rules:**\n\n"
        for source, destinations in rules.items():
            source_info = self.config['available_chats'].get(source, {'title': 'Unknown', 'type': 'unknown'})
            for dest in destinations:
                dest_info = self.config['available_chats'].get(dest, {'title': 'Unknown', 'type': 'unknown'})
                rule_key = f"{source}:{dest}"
                forward_media = self.config.get('forward_media_settings', {}).get(rule_key, True)

                text += (
                    f"From: {source_info['title']}\n"
                    f"Source ID: {source}\n"
                    f"To: {dest_info['title']}\n"
                    f"Destination ID: {dest}\n"
                    f"Media Forwarding: {'Enabled' if forward_media else 'Disabled'}\n"
                    f"Type: {source_info['type']} ➡️ {dest_info['type']}\n\n"
                )

        # Handle long messages
        if len(text) > 4096:
            chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]
            for i, chunk in enumerate(chunks):
                if i == len(chunks) - 1:
                    await event.edit(chunk, buttons=[
                        [Button.inline("🗑️ Delete Rule", b"delete_rule")],
                        [Button.inline("◀️ Back to Menu", b"main_menu")]
                    ])
                else:
                    await event.respond(chunk)
        else:
            await event.edit(text, buttons=[
                [Button.inline("🗑️ Delete Rule", b"delete_rule")],
                [Button.inline("◀️ Back to Menu", b"main_menu")]
            ])

    async def handle_rule_deletion(self, event, data):
        """Handle deletion of forwarding rules"""
        try:
            _, source, dest = data.split("_")
            async with self.lock:
                if source in self.config['forwarding_rules']:
                    if dest in self.config['forwarding_rules'][source]:
                        await self.stop_forwarding(source, dest)
                        self.config['forwarding_rules'][source].remove(dest)
                        if not self.config['forwarding_rules'][source]:
                            del self.config['forwarding_rules'][source]
                        self.save_config()

            await event.edit(
                "✅ Rule deleted successfully!",
                buttons=[[Button.inline("◀️ Back to Rules", b"list_rules")]]
            )
        except Exception as e:
            logger.error(f"Error deleting rule: {e}")
            await event.edit(
                "Failed to delete rule. Please try again.",
                buttons=[[Button.inline("◀️ Back to Rules", b"list_rules")]]
            )

    async def handle_fetch_chats(self, event):
        """Handle fetching available chats"""
        await event.answer("🔄 Fetching available chats...")
        try:
            response = await self.send_command_to_forwarder("fetch_chats")
            if response.startswith("Success"):
                self.config = self.load_config()
                chats = self.config.get('available_chats', {})

                if not chats:
                    await event.edit(
                        "No chats found. Please check your permissions.",
                        buttons=[[Button.inline("◀️ Back to Menu", b"main_menu")]]
                    )
                    return

                text = "**📋 Available Chats:**\n\n"
                for chat_id, info in chats.items():
                    text += f"📌 **{info['title']}**\n"
                    text += f"🆔 `{chat_id}`\n"
                    text += f"📱 Type: {info['type'].title()}\n"
                    if info.get('members_count'):
                        text += f"👥 Members: {info['members_count']}\n"
                    if info.get('username'):
                        text += f"🔗 @{info['username']}\n"
                    text += "\n"

                # Handle long messages
                if len(text) > 4096:
                    chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]
                    for i, chunk in enumerate(chunks):
                        if i == len(chunks) - 1:
                            await event.edit(
                                chunk,
                                buttons=[[Button.inline("◀️ Back to Menu", b"main_menu")]]
                            )
                        else:
                            await event.respond(chunk)
                else:
                    await event.edit(
                        text,
                        buttons=[[Button.inline("◀️ Back to Menu", b"main_menu")]]
                    )
            else:
                await event.edit(
                    f"❌ Failed to fetch chats: {response}",
                    buttons=[[Button.inline("◀️ Back to Menu", b"main_menu")]]
                )
        except Exception as e:
            logger.error(f"Error in fetch_chats: {e}")
            await event.edit(
                f"❌ Error fetching chats: {str(e)}",
                buttons=[[Button.inline("◀️ Back to Menu", b"main_menu")]]
            )

    async def handle_word_replace(self, event):
        """Handle word replacement settings"""
        replacements = self.config['word_replacements']
        text = "**Current Word Replacements:**\n\n"
        if replacements:
            for old, new in replacements.items():
                text += f"`{old}` → `{new}`\n"
        else:
            text += "No word replacements configured.\n"

        await event.edit(text, buttons=[
            [Button.inline("➕ Add Replacement", b"add_replacement")],
            [Button.inline("🗑️ Delete Replacement", b"delete_replacement")],
            [Button.inline("◀️ Back to Menu", b"main_menu")]
        ])

    async def handle_message(self, event: Message):
        """Handle text messages for various states"""
        if not await self.is_admin(event.sender_id):
            return

        user_id = event.sender_id
        if user_id not in self.user_states:
            return

        if event.message.text == "/cancel":
            del self.user_states[user_id]
            await self.handle_start(event)
            return

        state = self.user_states[user_id]["state"]
        try:
            if state == "awaiting_old_word":
                await self.handle_old_word_input(event, user_id)
            elif state == "awaiting_new_word":
                await self.handle_new_word_input(event, user_id)
            elif state == "awaiting_blacklist":
                await self.handle_blacklist_input(event, user_id)
            elif state == "awaiting_approved":
                await self.handle_approved_input(event, user_id)
        except Exception as e:
            logger.error(f"Error handling message state {state}: {e}")
            await event.respond(
                "An error occurred. Please try again.",
                buttons=[[Button.inline("◀️ Back to Menu", b"main_menu")]]
            )

    async def send_command_to_forwarder(self, command: str) -> str:
        """Send command to forwarder service"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(('localhost', 65432))
                s.settimeout(10)  # 10 second timeout
                s.sendall(command.encode('utf-8'))
                response = s.recv(1024).decode('utf-8')
                logger.info(f"Response from forwarder: {response}")
                return response
        except socket.timeout:
            logger.error("Timeout while communicating with forwarder")
            raise RuntimeError("Forwarder communication timeout")
        except ConnectionRefusedError:
            logger.error("Forwarder service is not running")
            raise RuntimeError("Forwarder service is not running")
        except Exception as e:
            logger.error(f"Failed to communicate with forwarder: {e}")
            raise

    async def start_forwarding(self, source_id: str, dest_id: str, forward_media: bool):
        """Start forwarding messages between chats"""
        try:
            command = f"start_forward:{source_id}:{dest_id}:{forward_media}"
            response = await self.send_command_to_forwarder(command)
            if not response.startswith("Started"):
                raise RuntimeError(f"Failed to start forwarding: {response}")
            logger.info(f"Started forwarding from {source_id} to {dest_id}")
        except Exception as e:
            logger.error(f"Failed to start forwarding: {e}")
            raise

    async def stop_forwarding(self, source_id: str, dest_id: str):
        """Stop forwarding messages between chats"""
        try:
            command = f"stop_forward:{source_id}:{dest_id}"
            response = await self.send_command_to_forwarder(command)
            if not response.startswith("Stopped"):
                raise RuntimeError(f"Failed to stop forwarding: {response}")
            logger.info(f"Stopped forwarding from {source_id} to {dest_id}")
        except Exception as e:
            logger.error(f"Failed to stop forwarding: {e}")
            raise

    async def handle_stop_all(self, event):
        """Handle stopping all forwarding rules"""
        try:
            async with self.lock:
                response = await self.send_command_to_forwarder("stop_all")
                if response.startswith("Success"):
                    self.config['forwarding_rules'] = {}
                    self.save_config()
                    await event.edit(
                        "✅ All forwarding rules have been stopped.",
                        buttons=[[Button.inline("◀️ Back to Menu", b"main_menu")]]
                    )
                else:
                    raise RuntimeError(f"Failed to stop all forwards: {response}")
        except Exception as e:
            logger.error(f"Error stopping all forwards: {e}")
            await event.edit(
                "❌ Failed to stop all forwards. Please try again.",
                buttons=[[Button.inline("◀️ Back to Menu", b"main_menu")]]
            )

    async def handle_old_word_input(self, event, user_id):
        """Handle input for word to be replaced"""
        old_word = event.message.text.strip()
        if not old_word:
            await event.respond("Please enter a valid word.")
            return

        self.user_states[user_id].update({
            "state": "awaiting_new_word",
            "old_word": old_word
        })
        await event.respond(f"Enter the replacement for '{old_word}':")

    async def handle_new_word_input(self, event, user_id):
        """Handle input for replacement word"""
        try:
            new_word = event.message.text.strip()
            if not new_word:
                await event.respond("Please enter a valid replacement word.")
                return

            old_word = self.user_states[user_id]["old_word"]
            async with self.lock:
                self.config['word_replacements'][old_word] = new_word
                self.save_config()
            del self.user_states[user_id]
            await event.respond(
                f"✅ Added replacement: '{old_word}' → '{new_word}'",
                buttons=[[Button.inline("◀️ Back to Word Replacements", b"word_replace")]]
            )
        except Exception as e:
            logger.error(f"Error adding word replacement: {e}")
            await event.respond(
                "Failed to add word replacement. Please try again.",
                buttons=[[Button.inline("◀️ Back to Menu", b"main_menu")]]
            )

    async def handle_blacklist_input(self, event, user_id):
        """Handle input for blacklisted words"""
        try:
            words = [w.strip() for w in event.message.text.split(",") if w.strip()]
            if not words:
                await event.respond("No valid words provided. Please try again.")
                return

            async with self.lock:
                self.config['blacklist_words'].extend(words)
                self.config['blacklist_words'] = list(set(self.config['blacklist_words']))
                self.save_config()

            del self.user_states[user_id]
            await event.respond(
                f"✅ Added {len(words)} words to blacklist",
                buttons=[[Button.inline("◀️ Back to Blacklist", b"blacklist")]]
            )
        except Exception as e:
            logger.error(f"Error adding to blacklist: {e}")
            await event.respond(
                "Failed to add words to blacklist. Please try again.",
                buttons=[[Button.inline("◀️ Back to Menu", b"main_menu")]]
            )

    async def handle_approved_input(self, event, user_id):
        """Handle input for approved words"""
        try:
            words = [w.strip() for w in event.message.text.split(",") if w.strip()]
            if not words:
                await event.respond("No valid words provided. Please try again.")
                return

            async with self.lock:
                self.config['approved_words'].extend(words)
                self.config['approved_words'] = list(set(self.config['approved_words']))
                self.save_config()

            del self.user_states[user_id]
            await event.respond(
                f"✅ Added {len(words)} words to approved list",
                buttons=[[Button.inline("◀️ Back to Approved Words", b"approved")]]
            )
        except Exception as e:
            logger.error(f"Error adding approved words: {e}")
            await event.respond(
                "Failed to add words to approved list. Please try again.",
                buttons=[[Button.inline("◀️ Back to Menu", b"main_menu")]]
            )

    async def is_admin(self, user_id: int) -> bool:
        """Check if user is an admin"""
        return str(user_id) in self.config['admins']

if __name__ == "__main__":
    bot = BotUI()
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
# forwarder.py
import asyncio
from telethon import TelegramClient, events
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty, Channel, Chat, User
from typing import Dict, Tuple, List
import json
import logging
import socket
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Forwarder:
    def __init__(self):
        self.api_id = os.getenv('API_ID')
        self.api_hash = os.getenv('API_HASH')
        self.client = TelegramClient('forwarder_user', self.api_id, self.api_hash)
        self.config = self.load_config()
        self.socket_server = None
        self.lock = asyncio.Lock()
        self.message_map: Dict[int, Dict[int, List[Tuple[int, int]]]] = {}

    def load_config(self) -> dict:
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                config.setdefault('forward_media_settings', {})
                return config
        except FileNotFoundError:
            return {
                'forwarding_rules': {},
                'word_replacements': {},
                'blacklist_words': [],
                'approved_words': [],
                'admins': [os.getenv('ADMIN_ID', '')],
                'forward_media_settings': {}
            }

    def save_config(self):
        try:
            with open('config.json', 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    async def fetch_available_chats(self):
        """Fetch all available chats with detailed information"""
        try:
            result = await self.client(GetDialogsRequest(
                offset_date=None,
                offset_id=0,
                offset_peer=InputPeerEmpty(),
                limit=200,
                hash=0
            ))

            chats = {}
            for dialog in result.dialog:
                try:
                    # Get the peer from dialog
                    peer = dialog.peer
                    entity = await self.client.get_dialogs(peer)
                    
                    # Handle different entity types
                    if isinstance(entity, Channel):
                        if entity.broadcast:
                            chat_type = 'channel'
                            chat_id = str(entity.id)
                            
                        else:
                            chat_type = 'supergroup'
                            chat_id = f"-100{entity.id}"  # Proper supergroup ID format
                        username = entity.username if hasattr(entity, 'username') else None
                        members_count = entity.participants_count if hasattr(entity, 'participants_count') else None
                    elif isinstance(entity, Chat):
                        chat_type = 'group'
                        chat_id = str(entity.id)
                        username = None
                        members_count = entity.participants_count
                    elif isinstance(entity, User):
                        chat_type = 'user'
                        chat_id = str(entity.id)
                        username = entity.username
                        members_count = 1
                    else:
                        continue

                    chat_id = str(entity.id)
                    title = getattr(entity, 'title', 
                                getattr(entity, 'first_name', '') + ' ' + 
                                getattr(entity, 'last_name', '')).strip()

                    chats[chat_id] = {
                        'id': chat_id,
                        'title': title,
                        'type': chat_type,
                        'username': username,
                        'members_count': members_count
                    }

                except Exception as e:
                    logger.error(f"Error processing dialog: {e}")
                    continue

            self.config['available_chats'] = chats
            self.save_config()
            return "Success: Chats fetched and saved"

        except Exception as e:
            logger.error(f"Error fetching chats: {e}")
            return f"Error: {str(e)}"

    async def process_command(self, command: str) -> str:
        try:
            parts = command.split(':')
            if len(parts) < 1:
                return "Invalid command format"

            cmd_type = parts[0]

            if cmd_type == "fetch_chats":
                return await self.fetch_available_chats()

            elif cmd_type == "start_forward":
                source_id, dest_id, forward_media = parts[1], parts[2], parts[3].lower() == 'true'
                async with self.lock:
                    self.config.setdefault('forward_media_settings', {})
                    if source_id not in self.config['forwarding_rules']:
                        self.config['forwarding_rules'][source_id] = []
                    if dest_id not in self.config['forwarding_rules'][source_id]:
                        self.config['forwarding_rules'][source_id].append(dest_id)
                    rule_key = f"{source_id}:{dest_id}"
                    self.config['forward_media_settings'][rule_key] = forward_media
                    self.save_config()
                return f"Started forwarding from {source_id} to {dest_id}"

            elif cmd_type == "stop_forward":
                source_id, dest_id = parts[1], parts[2]
                return await self.stop_forwarding(source_id, dest_id)

            elif cmd_type == "stop_all":
                self.config['forwarding_rules'] = {}
                self.config['forward_media_settings'] = {}
                self.save_config()
                return "Success: All forwarding rules stopped"

            else:
                return "Unknown command"

        except Exception as e:
            logger.error(f"Error processing command: {e}")
            return f"Error: {str(e)}"

    async def handle_message(self, event):
        try:
            logger.info(f"Received message in chat {event.chat_id}")
            self.config = self.load_config()

            source_id = str(event.chat_id)
            if source_id not in self.config['forwarding_rules']:
                logger.info(f"No forwarding rules found for chat {source_id}")
                return

            destinations = self.config['forwarding_rules'][source_id]
            logger.info(f"Found forwarding rules to destinations: {destinations}")

            has_media = bool(event.message.media)
            has_text = bool(event.message.text)
            logger.info(f"Message has media: {has_media}, has text: {has_text}")

            if not has_text and not has_media:
                logger.info("Message has no content to forward")
                return

            if has_text:
                logger.info(f"Message text: {event.message.text[:50]}...")
                if not self.should_forward_message(event.message.text):
                    logger.info("Message filtered by should_forward_message")
                    return

            src_chat_id = event.chat_id
            src_msg_id = event.message.id

            if src_chat_id not in self.message_map:
                self.message_map[src_chat_id] = {}

            self.message_map[src_chat_id][src_msg_id] = []

            for dest_id in destinations:
                try:
                    rule_key = f"{source_id}:{dest_id}"
                    forward_media = self.config['forward_media_settings'].get(rule_key, True)

                    if has_media and not forward_media:
                        continue

                    dest_msg = await self.client.forward_messages(
                        int(dest_id),
                        messages=event.message,
                        drop_author=True
                    )

                    if has_text:
                        processed_text = self.process_message_text(event.message.text)
                        if processed_text != event.message.text:
                            await self.client.edit_message(
                                int(dest_id),
                                dest_msg.id,
                                processed_text
                            )

                    self.message_map[src_chat_id][src_msg_id].append((int(dest_id), dest_msg.id))
                    logger.info(f"Forwarded message from {source_id} to {dest_id}")
                except Exception as e:
                    logger.error(f"Error forwarding to {dest_id}: {e}")

            self.save_message_map()

        except Exception as e:
            logger.error(f"Error in handle_message: {e}")

    async def stop_forwarding(self, source_id: str, dest_id: str):
        """Enhanced stop forwarding with cleanup"""
        try:
            if source_id in self.config['forwarding_rules']:
                if dest_id in self.config['forwarding_rules'][source_id]:
                    self.config['forwarding_rules'][source_id].remove(dest_id)
                    if not self.config['forwarding_rules'][source_id]:
                        del self.config['forwarding_rules'][source_id]
                    rule_key = f"{source_id}:{dest_id}"
                    if rule_key in self.config['forward_media_settings']:
                        del self.config['forward_media_settings'][rule_key]
                    self.save_config()
                    return f"Stopped forwarding from {source_id} to {dest_id}"
            return f"No forwarding rule found from {source_id} to {dest_id}"
        except Exception as e:
            logger.error(f"Error in stop_forwarding: {e}")
            return f"Error: {str(e)}"

    async def handle_edit(self, event):
        try:
            source_id = str(event.chat_id)
            if source_id not in self.config['forwarding_rules']:
                return

            if not event.message.text:
                return

            if not self.should_forward_message(event.message.text):
                return

            processed_text = self.process_message_text(event.message.text)

            src_chat_id = event.chat_id
            src_msg_id = event.message.id

            if (src_chat_id in self.message_map and
                src_msg_id in self.message_map[src_chat_id]):

                for dest_chat_id, dest_msg_id in self.message_map[src_chat_id][src_msg_id]:
                    try:
                        await self.client.edit_message(dest_chat_id, dest_msg_id, processed_text)
                        logger.info(f"Updated forwarded message in {dest_chat_id}")
                    except Exception as e:
                        logger.error(f"Error updating message in {dest_chat_id}: {e}")

        except Exception as e:
            logger.error(f"Error in handle_edit: {e}")

    def process_message_text(self, text: str) -> str:
        if not text:
            return text

        processed_text = text
        for old_word, new_word in self.config['word_replacements'].items():
            processed_text = processed_text.replace(old_word, new_word)

        return processed_text

    def should_forward_message(self, text: str) -> bool:
        if not text:
            return False

        text_lower = text.lower()

        if any(word.lower() in text_lower for word in self.config['blacklist_words']):
            logger.info(f"Message blocked by blacklist: {text[:50]}...")
            return False

        if self.config['approved_words']:
            should_forward = any(word.lower() in text_lower for word in self.config['approved_words'])
            if not should_forward:
                logger.info(f"Message doesn't contain any approved words: {text[:50]}...")
            return should_forward

        return True

    async def start_socket_server(self):
        server = await asyncio.start_server(
            self.handle_socket_client,
            'localhost',
            65432
        )
        self.socket_server = server
        async with server:
            await server.serve_forever()

    async def handle_socket_client(self, reader, writer):
        try:
            data = await reader.read(1024)
            command = data.decode('utf-8')
            response = await self.process_command(command)
            writer.write(response.encode('utf-8'))
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    def save_message_map(self):
        with open('message_map.json', 'w') as f:
            serializable_map = {
                str(k): {str(k2): v for k2, v in v.items()}
                for k, v in self.message_map.items()
            }
            json.dump(serializable_map, f)

    def load_message_map(self):
        try:
            with open('message_map.json', 'r') as f:
                content = f.read().strip()
                if content:  # Check if file has content
                    data = json.loads(content)
                    self.message_map = {
                        int(k): {int(k2): v for k2, v in v.items()}
                        for k, v in data.items()
                    }
                else:
                    self.message_map = {}
        except FileNotFoundError:
            self.message_map = {}
            # Create the file if it doesn't exist
            with open('message_map.json', 'w') as f:
                json.dump({}, f)
        except json.JSONDecodeError:
            logger.warning("Invalid message_map.json found, creating new one")
            self.message_map = {}
            with open('message_map.json', 'w') as f:
                json.dump({}, f)

    async def start(self):
        await self.client.start()
        self.load_message_map()
        asyncio.create_task(self.start_socket_server())
        self.client.add_event_handler(self.handle_message, events.NewMessage())
        self.client.add_event_handler(self.handle_edit, events.MessageEdited())
        logger.info("Forwarder started successfully!")
        try:
            await self.client.run_until_disconnected()
        finally:
            if self.socket_server:
                self.socket_server.close()

if __name__ == "__main__":
    forwarder = Forwarder()
    asyncio.run(forwarder.start())

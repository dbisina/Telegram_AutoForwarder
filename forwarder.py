import asyncio
from telethon import TelegramClient, events
import json
import logging
import socket
from typing import Dict, List, Tuple

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Forwarder:
    def __init__(self, api_id: str, api_hash: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.client = TelegramClient('forwarder_user', api_id, api_hash)
        self.config = self.load_config()
        self.socket_server = None
        # Store message mappings: {source_chat_id: {source_msg_id: [(dest_chat_id, dest_msg_id)]}}
        self.message_map: Dict[int, Dict[int, List[Tuple[int, int]]]] = {}

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
                'admins': ["1493595978"]
            }

    def save_config(self):
        with open('config.json', 'w') as f:
            json.dump(self.config, f, indent=4)

    def save_message_map(self):
        """Save message mapping to file"""
        try:
            # Convert int keys to strings for JSON serialization
            serializable_map = {
                str(src_chat): {
                    str(src_msg): [(str(dst_chat), dst_msg) for dst_chat, dst_msg in dests]
                    for src_msg, dests in msgs.items()
                }
                for src_chat, msgs in self.message_map.items()
            }
            with open('message_map.json', 'w') as f:
                json.dump(serializable_map, f)
        except Exception as e:
            logger.error(f"Failed to save message map: {e}")

    def load_message_map(self):
        """Load message mapping from file"""
        try:
            with open('message_map.json', 'r') as f:
                data = json.load(f)
                # Convert string keys back to integers
                self.message_map = {
                    int(src_chat): {
                        int(src_msg): [(int(dst_chat), dst_msg) for dst_chat, dst_msg in dests]
                        for src_msg, dests in msgs.items()
                    }
                    for src_chat, msgs in data.items()
                }
        except FileNotFoundError:
            self.message_map = {}
        except Exception as e:
            logger.error(f"Failed to load message map: {e}")
            self.message_map = {}

    async def start_socket_server(self):
        self.socket_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket_server.bind(('localhost', 65432))
        self.socket_server.listen()
        self.socket_server.setblocking(False)
        
        logger.info("Socket server started, waiting for commands...")
        
        while True:
            try:
                conn, addr = await asyncio.get_event_loop().sock_accept(self.socket_server)
                asyncio.create_task(self.handle_connection(conn, addr))
            except Exception as e:
                logger.error(f"Socket error: {e}")
                await asyncio.sleep(1)

    async def handle_connection(self, conn, addr):
        try:
            conn.setblocking(False)
            data = await asyncio.get_event_loop().sock_recv(conn, 1024)
            if data:
                response = await self.process_command(data.decode('utf-8'))
                await asyncio.get_event_loop().sock_sendall(conn, response.encode('utf-8'))
        except Exception as e:
            logger.error(f"Error handling connection: {e}")
        finally:
            conn.close()

    async def process_command(self, command: str) -> str:
        try:
            parts = command.split(':')
            if len(parts) < 2:
                return "Invalid command format"

            cmd_type = parts[0]
            
            if cmd_type == "start_forward":
                source_id, dest_id = parts[1], parts[2]
                self.config['forwarding_rules'].setdefault(source_id, []).append(dest_id)
                self.save_config()
                logger.info(f"Started forwarding: {source_id} -> {dest_id}")
                return f"Started forwarding from {source_id} to {dest_id}"

            elif cmd_type == "stop_forward":
                source_id, dest_id = parts[1], parts[2]
                if source_id in self.config['forwarding_rules']:
                    if dest_id in self.config['forwarding_rules'][source_id]:
                        self.config['forwarding_rules'][source_id].remove(dest_id)
                        if not self.config['forwarding_rules'][source_id]:
                            del self.config['forwarding_rules'][source_id]
                        self.save_config()
                        return f"Stopped forwarding from {source_id} to {dest_id}"
                return f"No forwarding rule found from {source_id} to {dest_id}"

            else:
                return "Unknown command"

        except Exception as e:
            logger.error(f"Error processing command: {e}")
            return f"Error: {str(e)}"

    async def handle_message(self, event):
        try:
            # Reload config for each message to get latest rules and settings
            self.config = self.load_config()
            
            source_id = str(event.chat_id)
            if source_id not in self.config['forwarding_rules']:
                return

            destinations = self.config['forwarding_rules'][source_id]
            if not event.message.text:
                return

            if not self.should_forward_message(event.message.text):
                return

            processed_text = self.process_message_text(event.message.text)
            
            # Store forwarded message IDs
            src_chat_id = event.chat_id
            src_msg_id = event.message.id
            
            if src_chat_id not in self.message_map:
                self.message_map[src_chat_id] = {}
            
            self.message_map[src_chat_id][src_msg_id] = []
            
            for dest_id in destinations:
                try:
                    dest_msg = await self.client.send_message(int(dest_id), processed_text)
                    self.message_map[src_chat_id][src_msg_id].append((int(dest_id), dest_msg.id))
                    logger.info(f"Forwarded message from {source_id} to {dest_id}")
                except Exception as e:
                    logger.error(f"Error forwarding to {dest_id}: {e}")
            
            self.save_message_map()

        except Exception as e:
            logger.error(f"Error in handle_message: {e}")

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
            
            # Check if we have this message mapped
            if (src_chat_id in self.message_map and 
                src_msg_id in self.message_map[src_chat_id]):
                
                # Update all forwarded copies
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

        # Check blacklist
        if any(word.lower() in text_lower for word in self.config['blacklist_words']):
            logger.info(f"Message blocked by blacklist: {text[:50]}...")
            return False

        # Check approved words
        if self.config['approved_words']:
            should_forward = any(word.lower() in text_lower for word in self.config['approved_words'])
            if not should_forward:
                logger.info(f"Message doesn't contain any approved words: {text[:50]}...")
            return should_forward

        return True

    async def start(self):
        await self.client.start()
        
        # Load existing message mappings
        self.load_message_map()
        
        # Start the socket server
        asyncio.create_task(self.start_socket_server())
        
        # Register message handlers
        self.client.add_event_handler(self.handle_message, events.NewMessage())
        self.client.add_event_handler(self.handle_edit, events.MessageEdited())
        
        logger.info("Forwarder started successfully!")
        
        try:
            await self.client.run_until_disconnected()
        finally:
            if self.socket_server:
                self.socket_server.close()

if __name__ == "__main__":
    # Load credentials from config
    with open("credentials.txt") as f:
        api_id = f.readline().strip()
        api_hash = f.readline().strip()

    forwarder = Forwarder(api_id, api_hash)
    asyncio.run(forwarder.start())
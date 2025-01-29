import asyncio
from telethon import TelegramClient, events
import json
import logging
import socket

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

    async def start_socket_server(self):
        # Start a TCP socket server to listen for commands
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', 65432))  # Bind to localhost on port 65432
            s.listen()
            logger.info("Socket server started, waiting for commands...")

            while True:
                conn, addr = s.accept()
                with conn:
                    logger.info(f"Connected by {addr}")
                    data = conn.recv(1024).decode('utf-8')  # Receive the command
                    if not data:
                        continue

                    # Process the command
                    response = await self.process_command(data)
                    conn.sendall(response.encode('utf-8'))  # Send a response back

    async def process_command(self, command: str) -> str:
        # Parse and execute the command
        parts = command.split(':')
        if parts[0] == "start_forward":
            source_id, dest_id = parts[1], parts[2]
            self.config['forwarding_rules'].setdefault(source_id, []).append(dest_id)
            self.save_config()
            return f"Started forwarding from {source_id} to {dest_id}"

        elif parts[0] == "stop_forward":
            source_id, dest_id = parts[1], parts[2]
            if source_id in self.config['forwarding_rules']:
                if dest_id in self.config['forwarding_rules'][source_id]:
                    self.config['forwarding_rules'][source_id].remove(dest_id)
                    if not self.config['forwarding_rules'][source_id]:
                        del self.config['forwarding_rules'][source_id]
                    self.save_config()
                    return f"Stopped forwarding from {source_id} to {dest_id}"
                else:
                    return f"No forwarding rule found from {source_id} to {dest_id}"
            else:
                return f"No forwarding rules found for {source_id}"

        else:
            return "Invalid command"

    async def handle_message(self, event):
        source_id = str(event.chat_id)
        if source_id not in self.config['forwarding_rules']:
            return

        destinations = self.config['forwarding_rules'][source_id]
        text = event.message.text
        if not self.should_forward_message(text):
            return

        processed_text = self.process_message_text(text)
        for dest_id in destinations:
            try:
                await self.client.send_message(int(dest_id), processed_text)
            except Exception as e:
                logger.error(f"Error forwarding message: {str(e)}")

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
            return False

        # Check approved words
        if self.config['approved_words']:
            return any(word.lower() in text_lower for word in self.config['approved_words'])

        return True

    async def start(self):
        await self.client.start()
        
        # Start the socket server in the background
        asyncio.create_task(self.start_socket_server())
        
        # Register event handlers
        self.client.add_event_handler(self.handle_message, events.NewMessage())
        
        logger.info("Forwarder started!")
        await self.client.run_until_disconnected()

if __name__ == "__main__":
    # Load credentials from config
    with open("credentials.txt") as f:
        api_id = f.readline().strip()
        api_hash = f.readline().strip()

    forwarder = Forwarder(api_id, api_hash)
    asyncio.run(forwarder.start())
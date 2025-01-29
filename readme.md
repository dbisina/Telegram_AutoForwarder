# 📨 Telegram Message Forwarder Bot

A powerful and flexible Telegram bot that forwards messages between channels/groups with advanced filtering, word replacement, and message synchronization capabilities.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.7+-blue.svg)
![Telethon](https://img.shields.io/badge/telethon-latest-green.svg)

## ✨ Features

### Core Functionality
- 🔄 Forward messages between multiple channels/groups
- ✏️ Synchronize message edits between source and destination
- 🎯 Smart message filtering system
- 🔄 Word replacement capabilities
- 🎮 User-friendly bot interface for management

### Advanced Features
- ⚡ Real-time message processing
- 🔍 Customizable word filters
- 🚫 Blacklist system for blocked words
- ✅ Whitelist system for approved words
- 🔐 Admin-only access control
- 📝 Message edit synchronization
- 💾 Persistent configuration storage

## 🛠️ Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/telegram-forwarder.git
cd telegram-forwarder
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `credentials.txt` file with your Telegram API credentials:
```
your_api_id
your_api_hash
your_bot_token
```

4. Set up your bot configuration in `config.json` (created automatically on first run):
```json
{
    "forwarding_rules": {},
    "word_replacements": {},
    "blacklist_words": [],
    "approved_words": [],
    "admins": ["YOUR_TELEGRAM_ID"]
}
```

## 🚀 Usage

1. Start the forwarder service:
```bash
python forwarder.py
```

2. Start the bot interface:
```bash
python bot_ui.py
```

3. Interact with the bot on Telegram:
   - Start the bot with `/start`
   - Use the menu buttons to manage forwarding rules
   - Configure word replacements and filters
   - Monitor forwarding status

## 🎮 Bot Commands

### Basic Commands
- `/start` - Initialize the bot and show main menu
- `/help` - Show help information

### Menu Options
- **➕ Add Forwarding Rule** - Set up new message forwarding
- **📋 List Active Rules** - View current forwarding configuration
- **🔄 Word Replacements** - Manage word replacement rules
- **⛔ Blacklist Words** - Manage blocked words
- **✅ Approved Words** - Manage approved words
- **❌ Stop All Forwards** - Disable all forwarding rules

## ⚙️ Configuration

### Forwarding Rules
Configure message forwarding between channels:
```json
{
    "forwarding_rules": {
        "source_channel_id": ["destination_channel_id1", "destination_channel_id2"]
    }
}
```

### Word Replacements
Set up automatic word replacements:
```json
{
    "word_replacements": {
        "original_word": "replacement_word",
        "another_word": "new_word"
    }
}
```

### Filter Lists
Configure word filtering:
```json
{
    "blacklist_words": ["blocked_word1", "blocked_word2"],
    "approved_words": ["allowed_word1", "allowed_word2"]
}
```

## 🔒 Security Features

- Admin-only access control
- Secure message processing
- Configuration file validation
- Error logging and monitoring
- Safe credential handling

## 📝 Logging

The bot maintains detailed logs of:
- Message forwarding status
- Edit synchronization
- Error messages
- Configuration changes
- Administrative actions

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔧 Troubleshooting

### Common Issues

1. **Connection Errors**
   - Verify your internet connection
   - Check API credentials
   - Ensure bot token is valid

2. **Forwarding Issues**
   - Verify channel permissions
   - Check bot admin status
   - Validate channel IDs

3. **Configuration Problems**
   - Check config.json format
   - Verify file permissions
   - Ensure valid JSON syntax

## 📞 Support

For support, please:
1. Check the documentation
2. Look through existing issues
3. Create a new issue with detailed information

## ⚠️ Requirements

- Python 3.7+
- Telethon library
- Active internet connection
- Telegram API credentials
- Bot token from @BotFather

---

Made with ❤️ for the Telegram community
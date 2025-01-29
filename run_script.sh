#!/bin/bash

# Install required libraries
pip install telethon

# Start the secondary script (Forwarder) in the background
python3 forwarder.py &

# Start the bot script (BotUI)
python3 bot_ui.py

# Wait for both scripts to finish
wait
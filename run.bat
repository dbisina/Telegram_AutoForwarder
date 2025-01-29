@echo off

:: Install required libraries
pip install telethon

:: Start the secondary script (Forwarder) in the background
start python forwarder.py

:: Start the bot script (BotUI)
python bot_ui.py

:: Wait for user input before closing
pause
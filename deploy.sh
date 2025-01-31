#!/bin/bash

# Server setup commands
sudo apt-get update -y
sudo apt-get install -y python3-pip python3-venv git

# Clone or update repository
if [ -d "telegram-forwarder" ]; then
  cd telegram-forwarder
  git pull
else
  git clone https://github.com/dbisina/telegram-forwarder.git
  cd telegram-forwarder
fi

# Python environment setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env file if missing
if [ ! -f ".env" ]; then
  echo "Creating .env file..."
  touch .env
  echo "API_ID=your_api_id" >> .env
  echo "API_HASH=your_api_hash" >> .env
  echo "BOT_TOKEN=your_bot_token" >> .env
  echo "ADMIN_ID=your_admin_id" >> .env
  echo "Please edit the .env file with actual values!"
fi

# Create systemd services
sudo tee /etc/systemd/system/forwarder.service > /dev/null << EOL
[Unit]
Description=Telegram Forwarder Service
After=network.target

[Service]
User=$USER
WorkingDirectory=/home/$USER/telegram-forwarder
ExecStart=/home/$USER/telegram-forwarder/venv/bin/python3 forwarder.py
Restart=always

[Install]
WantedBy=multi-user.target
EOL

sudo tee /etc/systemd/system/bot_ui.service > /dev/null << EOL
[Unit]
Description=Telegram Bot UI Service
After=network.target

[Service]
User=$USER
WorkingDirectory=/home/$USER/telegram-forwarder
ExecStart=/home/$USER/telegram-forwarder/venv/bin/python3 bot_ui.py
Restart=always

[Install]
WantedBy=multi-user.target
EOL

# Reload and enable services
sudo systemctl daemon-reload
sudo systemctl enable forwarder.service bot_ui.service
sudo systemctl restart forwarder.service bot_ui.service
ENDSSH

echo "Deployment complete! Services are now running."
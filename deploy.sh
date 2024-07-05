#!/bin/bash

# Install Python dependencies
pip install -r requirements.txt

# Update package list
sudo apt-get update

# Install wget
sudo apt-get install -y wget

# Download Chrome installer
sudo wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

# Install Chrome
sudo apt install -y ./google-chrome-stable_current_amd64.deb

# Install Chromium browser (optional, if needed)
sudo apt-get install -y chromium-browser

# Start your application
python main.py

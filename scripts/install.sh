#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Dependency Check ---
echo "Checking for dependencies..."
if ! command -v stow &> /dev/null; then
    echo "Error: 'stow' is not installed. Please install it first (e.g., 'sudo apt-get install stow')."
    exit 1
fi
echo "All dependencies are satisfied."

# --- Systemd Service Installation ---
echo "Installing raspiLogger.service..."
SERVICE_FILE="etc/systemd/system/raspiLogger.service"
DEST_SERVICE_PATH="/etc/systemd/system/raspiLogger.service"

if [ ! -f "$SERVICE_FILE" ]; then
    echo "Error: Service file '$SERVICE_FILE' not found. Please ensure you are running this script from the project root."
    exit 1
fi

# Stop and disable existing service if it's active
if sudo systemctl is-active --quiet raspiLogger.service; then
    echo "Stopping existing raspiLogger.service..."
    sudo systemctl stop raspiLogger.service
fi
if sudo systemctl is-enabled --quiet raspiLogger.service; then
    echo "Disabling existing raspiLogger.service..."
    sudo systemctl disable raspiLogger.service
fi

# Remove existing service file or symlink if it exists
if [ -f "$DEST_SERVICE_PATH" ] || [ -L "$DEST_SERVICE_PATH" ]; then
    echo "Existing service file or symlink found at $DEST_SERVICE_PATH. Removing..."
    sudo rm "$DEST_SERVICE_PATH"
fi

# Create a symbolic link (stow)
sudo ln -s "$(pwd)/$SERVICE_FILE" "$DEST_SERVICE_PATH" # Use absolute path for source
echo "Symbolic link created for raspiLogger.service at $DEST_SERVICE_PATH"

sudo systemctl daemon-reload
sudo systemctl enable raspiLogger.service
sudo systemctl start raspiLogger.service
echo "raspiLogger.service installed and started."

# --- Nginx Configuration Installation (using stow) ---
echo "Installing Nginx configuration using stow..."
NGINX_STOW_DIR="scripts/nginx"
NGINX_CONF_NAME="raspiLogger.nginx.conf"
NGINX_SITES_AVAILABLE="/etc/nginx/sites-available/$NGINX_CONF_NAME"
NGINX_SITES_ENABLED="/etc/nginx/sites-enabled/$NGINX_CONF_NAME"

if [ ! -d "$NGINX_STOW_DIR" ]; then
    echo "Error: Nginx stow directory '$NGINX_STOW_DIR' not found."
    echo "Please create the directory structure 'scripts/nginx/etc/nginx/sites-available' and move '$NGINX_CONF_NAME' into it."
    exit 1
fi

# Remove existing config file if it is not a symlink
if [ -f "$NGINX_SITES_AVAILABLE" ] && [ ! -L "$NGINX_SITES_AVAILABLE" ]; then
    echo "Existing configuration file found at $NGINX_SITES_AVAILABLE. Removing..."
    sudo rm "$NGINX_SITES_AVAILABLE"
fi

# Unstow first to remove old symlinks if they exist
echo "Unstowing existing nginx configuration if present..."
sudo stow -D -d "$NGINX_STOW_DIR" -t / nginx

# Stow the new configuration
echo "Stowing new nginx configuration..."
sudo stow -d "$NGINX_STOW_DIR" -t / nginx
echo "Nginx configuration stowed."

# Enable the Nginx site (stow should handle this, but we'll ensure the symlink exists)
if [ ! -L "$NGINX_SITES_ENABLED" ]; then
    echo "Enabling Nginx site..."
    sudo ln -s "$NGINX_SITES_AVAILABLE" "$NGINX_SITES_ENABLED"
fi

# Test Nginx configuration and reload
echo "Testing Nginx configuration..."
sudo nginx -t
echo "Reloading Nginx..."
sudo systemctl reload nginx
echo "Nginx configuration installed and reloaded."

echo "Installation complete."

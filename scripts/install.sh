#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Systemd Service Installation ---
echo "Installing raspiLogger.service..."
SERVICE_FILE="etc/systemd/system/raspiLogger.service"
DEST_SERVICE_PATH="/etc/systemd/system/raspiLogger.service"

if [ ! -f "$SERVICE_FILE" ]; then
    echo "Error: Service file '$SERVICE_FILE' not found. Please ensure you are running this script from the project root."
    exit 1
fi

sudo cp "$SERVICE_FILE" "$DEST_SERVICE_PATH"
sudo systemctl daemon-reload
sudo systemctl enable raspiLogger.service
sudo systemctl start raspiLogger.service
echo "raspiLogger.service installed and started."

# --- Nginx Configuration Installation ---
echo "Installing Nginx configuration..."
NGINX_CONF_SOURCE="scripts/raspiLogger.nginx.conf" # New: Source file for Nginx config
NGINX_CONF_NAME="raspiLogger.nginx.conf"
NGINX_SITES_AVAILABLE="/etc/nginx/sites-available/$NGINX_CONF_NAME"
NGINX_SITES_ENABLED="/etc/nginx/sites-enabled/$NGINX_CONF_NAME"

if [ ! -f "$NGINX_CONF_SOURCE" ]; then
    echo "Error: Nginx configuration source file '$NGINX_CONF_SOURCE' not found."
    exit 1
fi

# Copy the Nginx configuration file
sudo cp "$NGINX_CONF_SOURCE" "$NGINX_SITES_AVAILABLE"
echo "Nginx configuration copied to $NGINX_SITES_AVAILABLE"

# Enable the Nginx site
if [ -L "$NGINX_SITES_ENABLED" ]; then
    echo "Nginx site already enabled. Removing old symlink..."
    sudo rm "$NGINX_SITES_ENABLED"
fi
sudo ln -s "$NGINX_SITES_AVAILABLE" "$NGINX_SITES_ENABLED"
echo "Nginx site enabled."

# Test Nginx configuration and reload
echo "Testing Nginx configuration..."
sudo nginx -t
echo "Reloading Nginx..."
sudo systemctl reload nginx
echo "Nginx configuration installed and reloaded."

echo "Installation complete."
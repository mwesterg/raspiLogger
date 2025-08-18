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

# --- Nginx Configuration Update (using stow) ---
echo "Updating Nginx configuration using stow..."
NGINX_STOW_DIR="$(dirname "$0")"/nginx # Relative to the script's location
NGINX_CONF_NAME="raspiLogger.nginx.conf"
NGINX_SITES_AVAILABLE="/etc/nginx/sites-available/$NGINX_CONF_NAME"
NGINX_SITES_ENABLED="/etc/nginx/sites-enabled/$NGINX_CONF_NAME"

if [ ! -d "$NGINX_STOW_DIR" ]; then
    echo "Error: Nginx stow directory '$NGINX_STOW_DIR' not found."
    echo "Please ensure the directory structure 'scripts/nginx/etc/nginx/sites-available' and '$NGINX_CONF_NAME' are correctly set up."
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
echo "Nginx configuration updated and reloaded."

echo "Nginx configuration update complete."

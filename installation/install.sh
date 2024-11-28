#!/bin/bash

# Define variables
MAIN_DIR=$(dirname "$(dirname "$(readlink -f "$0")")")
INSTALL_DIR="/opt/esteban"
SERVICE_FILE="/etc/systemd/system/esteban.service"
LOCAL_SERVICE_FILE="$MAIN_DIR/installation/esteban.service"

# Print an informative message
echo "Installing Esteban..."

# Check if running as root
if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root. Please use 'sudo ./install.sh'."
  exit 1
fi

# Create the installation directory
echo "Creating installation directory at $INSTALL_DIR..."
if [[ -d $INSTALL_DIR ]]; then
  echo "Directory $INSTALL_DIR already exists. Overwriting..."
  rm -rf "$INSTALL_DIR"
fi
mkdir -p "$INSTALL_DIR"

# Copy the main folder to the installation directory
echo "Copying files to $INSTALL_DIR..."
cp -r "$MAIN_DIR"/* "$INSTALL_DIR"

# Copy the service file to /etc/systemd/system
echo "Installing systemd service..."
if [[ -f $LOCAL_SERVICE_FILE ]]; then
  cp "$LOCAL_SERVICE_FILE" "$SERVICE_FILE"
else
  echo "Error: $LOCAL_SERVICE_FILE not found!"
  exit 1
fi

# Set correct permissions
echo "Setting permissions for $INSTALL_DIR and $SERVICE_FILE..."
chown -R root:root "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR"
chmod 644 "$SERVICE_FILE"

# Reload systemd to recognize the new service
echo "Reloading systemd..."
systemctl daemon-reload

# Enable and start the service
echo "Enabling and starting esteban.service..."
systemctl enable esteban.service
systemctl start esteban.service

# Check the status of the service
echo "Checking the status of esteban.service..."
systemctl status esteban.service --no-pager

echo "Installation complete!"

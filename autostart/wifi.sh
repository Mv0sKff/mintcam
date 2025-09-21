#!/bin/bash

CONFIG_FILE="config.yml"

wifi=$(grep "^wifi:" "$CONFIG_FILE" | awk '{print $2}')
ssid=$(grep "^wifi_ssid:" "$CONFIG_FILE" | sed 's/wifi_ssid:[ ]*//; s/"//g')
password=$(grep "^wifi_password:" "$CONFIG_FILE" | sed 's/wifi_password:[ ]*//; s/"//g')

# debug
echo "wifi=$wifi"
echo "ssid=$ssid"
echo "password=$password"

if [ "$wifi" = "true" ]; then
    echo "Starting Wi-Fi hotspot..."
    sudo nmcli device wifi hotspot ssid "$ssid" password "$password"
else
    echo "Wi-Fi disabled in config."
fi

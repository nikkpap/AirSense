#!/bin/bash
# AirSense — Raspberry Pi installer (kept for old instructions): runs the common installer.
# Recommended:  wget -qO get.sh https://raw.githubusercontent.com/nikkpap/AirSense/main/get.sh && sudo bash get.sh
exec sudo bash "$(cd "$(dirname "$0")" && pwd)/airsense-setup.sh" "$@"

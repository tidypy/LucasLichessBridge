# LucasLichessBridge
A python Bridge to utilize Lucas Chess GUI instead of Lichess Browser GUI

# Lucas Lichess Bridge Description 2

A UCI-compliant bridge that allows Lucas Chess to play against Lichess bots.

## Overview

This project creates a "fake" UCI engine that:
- Presents itself to Lucas Chess as a normal UCI engine
- Relays moves to/from Lichess bots via the Lichess API
- Allows you to use Lucas Chess GUI to play against online bots


┌─────────────┐ ┌──────────────┐ ┌─────────────┐
│ Lucas Chess │ ◄─UCI─► │ Bridge │ ◄─API─► │ Lichess Bot │
│ (GUI) │ │ (Python) │ │ (LichessOnline-Bot)│
└─────────────┘ └──────────────┘ └─────────────┘


## Dependency Requirements

- Python 3.x
- `berserk` - Lichess API client
- `chess` - Python chess library
- Lichess API token with scopes: `challenge:read`, `challenge:write`, `board:play`

## Installation LINUX (Arch/CachyOS)

***Due to PEP 668, Arch-based distros require a virtual environment:  INSTALLATION THROUGH A PACKAGE MANAGER or REPOSITORY WILL NOT WORK***

# Open terminal; go to the location/folder you saved LichessBridge 
bash
cd /path/where-you-put/LucasLichessBridge

# Create a virtual environment
python -m venv my-venv  
Note: creates the Virtual Environment, it is now called, my-venv

# Activate the VE (bash/zsh)  ...Most Linux Distros
source my-venv/bin/activate

# Activate the VE if utilizing (Fish Shell), Arch/CachyOS Specific
source my-venv/bin/activate.fish  
Note: "CachyOS uses Fish Shell, the syntax is different" so I put this line in here for ARCH users. This step is not necessary if you are using (Bash/zsh).

# Install dependencies
pip install berserk chess

# Deactivate after you are done using the VE
deactivate   
Note: "later in time you can deactivate the virtual environment"

# LICHESS Token Creation Instructions
1. GO TO YOUR LICHESS PROFILE:  https://lichess.org/
2. CLICK ON "Preferences" ,  CLICK ON "API Access Tokens"
3. Click The Blue and White PLUS ICON (upper right corner), to create an API. Name your API in the "token description box".
4. Check all boxes to give permission that you wish your token to have.   Click Create. 
5. Copy/SAVE the token Immediately, it will disappear, it cannot be found or recovered later.

### Usage and Standalone Test

1. Open terminal; 
2. Change directory into the location/folder you saved LichessBridge 
3. Confirm you have your virtual environment in this folder and all dependencies are installed, then type:

bash
./run_bridge.sh
-- Then type:
# uci
# isready
# quit

LucasBridge should instantly output:
id name Lichess Bridge v3.1

### Open Lucas Chess and Create a new UCI engine







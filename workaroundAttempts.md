### Lucas Lichess BridgeUsage and Standalone Test

1. open terminal; go to the location/folder you saved LichessBridge 
bash
./run_bridge.sh
-- Then type:
# uci
# isready
# quit

#   For Issues With Lucas Chess
See TROUBLESHOOTING.md for Lucas Chess integration issues.

##  Configuration of Lucas Chess Bridge
# UCI Options (set in Lucas Chess engine parameters):

Option	Type	Default	Description
LichessToken	string		Your Lichess API token
Opponent	string	maia1	Bot username to challenge
PlayAs	combo	random	white / black / random
Variant	combo	standard	Chess variant
TimeMode	combo	realtime	realtime / correspondence / unlimited
Minutes	spin	5	Minutes per side
Increment	spin	3	Increment in seconds
Rated	check	false	Casual or rated game

Getting a Lichess Token
Go to https://lichess.org/account/oauth/token  --> your profile --> preferences --> Api Access Tokens --> 
Create token - The minimum required are scopes:
✅ challenge:read
✅ challenge:write
✅ board:play
Copy token! you will NOT be able to recover it later!

## For Known Lucas Chess Issues
See Lucas Chess GitHub Issues



## Troubleshooting Lucas Chess Integration

## Environment: Arch Linux / CachyOS

- Shell: Fish
- Python: /usr/bin/python (3.x)
- Lucas Chess: [version]

## Issue: Lucas Chess Hangs When Adding Engine

### Symptoms
- Lucas Chess freezes when adding the bridge as UCI engine
- No timeout, just infinite hang
- Must force-close Lucas

### Verified Working
- Bridge runs correctly standalone
- UCI handshake completes instantly
- Token authentication works
- All UCI commands function properly

### Test Results

For fish bash shell:
# Response is instant
set output (echo "uci" | ./run_bridge.sh 2>/dev/null | head -1)
echo $output

# Output: id name Lichess Bridge v3.1
Workarounds Attempted

#	Workaround	Result
1	Bash wrapper script (run_bridge.sh)	❌ Lucas hangs
2	Direct Python with venv shebang	❌ Not tested yet
3	PYTHONUNBUFFERED=1	❌ No effect
4	python -u flag	❌ No effect
5	flush=True on all prints	✅ Works standalone, Lucas still hangs
6	Waiting 3+ minutes	❌ Never completes

#   Wrapper Script Used
bash
#!/bin/bash
export PYTHONUNBUFFERED=1
exec /path/to/venv/bin/python -u /path/to/UCIbridgeForLucas.py
Next Steps to Try
Point Lucas to Python binary directly with arguments
Create launcher script with venv Python in shebang
Check Lucas Chess engine timeout settings
Test with different Lucas Chess version
Try alternative GUI (CuteChess, Arena)


##  Related Issues
Lucas Chess GitHub: [link to issue you create]

## GitHub Issue Template for Lucas Chess

## Bug: Engine detection hangs with Python UCI script

### Environment
- **OS**: Arch Linux / CachyOS
- **Lucas Chess Version**: [check Help → About]
- **Python**: 3.x

### Description
Lucas Chess hangs indefinitely when attempting to add a Python-based UCI engine. The engine responds correctly to UCI protocol when tested standalone.

### Steps to Reproduce
1. Create a Python UCI engine script
2. Tools → Engines → External Engines → New
3. Browse to the script/wrapper
4. Lucas hangs - never detects the engine

### Expected Behavior
Engine should be detected within a few seconds

### Actual Behavior
Infinite hang, must force-close Lucas

### Evidence Engine Works Correctly

# Standalone test shows instant response:
$ echo "uci" | ./run_bridge.sh | head -1
id name Lichess Bridge v3.1

test1

Full UCI handshake works:
$ ./run_bridge.sh
uci
id name Lichess Bridge v3.1
id author Human-Bot Bridge
option name ...
uciok
isready
readyok
quit

test2

### Workarounds Attempted
- [x] Bash wrapper script
- [x] PYTHONUNBUFFERED=1
- [x] python -u flag
- [x] flush=True on all print statements
- [x] Waited 3+ minutes

### Additional Context
- Most Other compiled UCI engines (e.g., Stockfish) work fine
- Issue appears specific to Python/scripted engines, and UCI engines with custom or partial parameters.
- Same script works with other GUIs (if tested)

### Possible Causes
- Engine startup timeout too short
- Wrapper script handling
- stdout/stderr handling differences
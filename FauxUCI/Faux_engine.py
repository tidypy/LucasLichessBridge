#!/usr/bin/python -u
"""
Minimal UCI Engine - Test if Lucas Chess can detect it.
No imports. No dependencies. Just UCI protocol.
"""
import sys

# --- Simple Logging ---
# No extra imports. Log file appears in the directory where the script is run from.
LOG_FILE = "faux_engine_log.txt"

def log(message):
    """Appends a message to the log file."""
    try:
        # Using 'a' for append mode. open() is a built-in, no import needed.
        with open(LOG_FILE, "a") as f:
            f.write(message + "\n")
    except:
        # If logging fails, we don't want to crash the engine.
        pass

def send(message):
    """Sends a message to the GUI, logs it, and flushes stdout."""
    log(f">>> {message}")
    print(message, flush=True)

def main():
    log("\n--- Engine Started ---")
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                log("EOF from stdin. Shutting down.")
                break

            line = line.strip()
            if not line:
                continue

            log(f"<<< {line}")
            cmd = line.split()[0].lower()

            if cmd == "uci":
                send("id name Faux UCI Engine")
                send("id author tidypy")
                send("option name TestOption type string default hello")
                send("option name TestSpin type spin default 5 min 1 max 100")
                send("option name TestCheck type check default false")
                send("option name TestCombo type combo default one var one var two var three")
                send("uciok")
            elif cmd == "isready":
                send("readyok")
            elif cmd == "go":
                send("bestmove e2e4")
            elif cmd == "quit":
                log("Quit command received. Exiting.")
                break
        except Exception as e:
            log(f"ERROR in main loop: {e}")
            break
    log("--- Engine Stopped ---\n")

if __name__ == "__main__":
    main()
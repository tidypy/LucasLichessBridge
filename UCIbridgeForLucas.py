import sys
import os
import threading
import time
from datetime import datetime
from queue import Queue, Empty

# --- LOGGING ---
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uci_bridge_log.txt")
log_lock = threading.Lock()

def log(message: str):
    """Appends a timestamped message to the log file in a thread-safe way."""
    try:
        with log_lock:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                f.write(f"[{timestamp}] {message}\n")
    except Exception:
        # Don't crash the engine if logging fails
        pass

# --- GLOBAL QUEUES ---
COMMAND_QUEUE = Queue()
RESPONSE_QUEUE = Queue()

# --- UCI THREAD (MAIN THREAD) ---
def uci_thread_main():
    """Handles all communication with the GUI via stdin/stdout."""
    log("--- UCI Thread Started ---")

    try:
        sys.stdout.reconfigure(line_buffering=True, encoding='utf-8')
        sys.stdin.reconfigure(encoding='utf-8')
        log("Reconfigured stdout/stdin for UTF-8 and line buffering.")
    except Exception as e:
        log(f"Could not reconfigure stdio: {e}. Using default buffering.")

    # Initial UCI handshake
    print("id name Lucas Lichess Bridge by tidypy", flush=True)
    log(">>> id name Lucas Lichess Bridge by tidypy")
    print("id author tidypy", flush=True)
    log(">>> id author tidypy")
    print("uciok", flush=True)
    log(">>> uciok")

    while True:
        try:
            # Send any responses from the worker thread to the GUI
            try:
                while True:
                    message = RESPONSE_QUEUE.get_nowait()
                    log(f">>> {message}")
                    print(message, flush=True)
            except Empty:
                pass  # This is the normal case when the queue is empty

            # Read command from GUI (this is a blocking call)
            line = sys.stdin.readline()
            if not line:
                log("EOF on stdin, signaling quit.")
                COMMAND_QUEUE.put("quit")
                break

            line = line.strip()
            if not line:
                continue

            log(f"<<< {line}")

            # Handle commands
            if line == "isready":
                log(">>> readyok")
                print("readyok", flush=True)
            elif line == "quit":
                log("Quit command received in UCI loop. Signaling worker.")
                COMMAND_QUEUE.put("quit")
                break
            else:
                # Offload all other commands to the worker thread
                COMMAND_QUEUE.put(line)

        except (EOFError, KeyboardInterrupt):
            log("EOF or KeyboardInterrupt in UCI loop, signaling quit.")
            COMMAND_QUEUE.put("quit")
            break
        except Exception as e:
            log(f"ERROR in UCI loop: {e}")
            COMMAND_QUEUE.put("quit")
            break

    log("--- UCI Thread Finished ---")

# --- WORKER THREAD ---
def worker_thread_main():
    """Processes complex commands and handles blocking I/O."""
    log("--- Worker Thread Started ---")
    RESPONSE_QUEUE.put("info string Worker thread started. Ready for commands.")

    while True:
        try:
            # Block until a command is available
            command = COMMAND_QUEUE.get()
            log(f"WORKER: Received command: '{command}'")

            if command == "quit":
                log("WORKER: Quit command received. Exiting.")
                break

            if command.startswith("go"):
                RESPONSE_QUEUE.put("info string WORKER: Received 'go'. Simulating 2-second blocking task...")
                time.sleep(2)
                RESPONSE_QUEUE.put("info string WORKER: Task complete. Sending result.")
                RESPONSE_QUEUE.put("bestmove a1a2")
            elif command.startswith("uci"):
                # This is handled by the main thread, but we log it if it gets here
                log("WORKER: Ignoring 'uci' command.")
            else:
                RESPONSE_QUEUE.put(f"info string WORKER: Unhandled command: {command}")

        except Exception as e:
            log(f"WORKER: ERROR in worker loop: {e}")
            RESPONSE_QUEUE.put(f"info string WORKER: ERROR: {e}")

    log("--- Worker Thread Finished ---")

if __name__ == "__main__":
    # Clear log file for a clean session
    try:
        with open(LOG_FILE, "w") as f:
            f.write("")
    except Exception as e:
        sys.stderr.write(f"Could not clear log file: {e}\n")

    log("--- Engine Starting ---")

    worker = threading.Thread(target=worker_thread_main, daemon=True)
    worker.start()
    log("Worker thread created and started.")

    # Run the UCI loop in the main thread
    uci_thread_main()

    # Wait for the worker thread to finish cleanly
    log("UCI loop finished. Waiting for worker thread to join.")
    worker.join(timeout=2)
    log("Worker thread joined. Exiting.")

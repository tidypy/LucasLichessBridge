import sys
import threading
from queue import Queue

# --- GLOBAL COMMUNICATION QUEUES ---
# Input commands from Lucas Chess (UCI Thread -> Worker Thread)
COMMAND_QUEUE = Queue()
# Output messages from Lichess (Worker Thread -> UCI Thread)
RESPONSE_QUEUE = Queue()

def main_uci_loop():
    """
    Handles all communication with the Lucas Chess GUI via STDIN/STDOUT.
    MUST be non-blocking except for sys.stdin.readline().
    """
    # Force unbuffered I/O immediately upon execution
    try:
        sys.stdout.reconfigure(line_buffering=True, encoding='utf-8')
        sys.stdin.reconfigure(encoding='utf-8')
    except Exception:
        # Fallback for systems where reconfigure isn't available
        pass

    # 1. Mandatory UCI Handshake (Must be fast!)
    print("id name Lucas Lichess Bridge by tidypy", flush=True)
    print("id author tidypy", flush=True)
    # Define Options here later (e.g., LichessToken, ChallengeType)
    print("uciok", flush=True)
    
    # 2. Main loop: Read commands from GUI and put them on the queue
    while True:
        try:
            # Check for a response from the worker thread (e.g., a move)
            while not RESPONSE_QUEUE.empty():
                message = RESPONSE_QUEUE.get_nowait()
                print(message, flush=True)

            # Read a line from the GUI (stdin). This will block.
            line = sys.stdin.readline().strip()

            if not line:
                # EOF or process terminated
                break

            # Process essential UCI commands directly for instant feedback
            if line == "isready":
                print("readyok", flush=True)
            
            elif line == "quit":
                break
            
            # Put any complex commands onto the queue for the worker thread
            else:
                COMMAND_QUEUE.put(line)

        except EOFError:
            break
        except Exception as e:
            # Log any serious error to stderr (visible in console without -u)
            sys.stderr.write(f"info string ERROR in UCI loop: {e}\n")
            sys.stderr.flush()
            break

def worker_thread_main():
    """
    The Worker Thread. It processes complex commands (like 'go') 
    and handles all blocking I/O (Lichess API calls).
    """
    RESPONSE_QUEUE.put("info string Worker thread started. Ready for commands.")
    
    while True:
        # Check for commands from the UCI thread
        if not COMMAND_QUEUE.empty():
            command = COMMAND_QUEUE.get_nowait()
            
            if command == "quit":
                break
            
            # --- STAGE 2: PROCESS 'GO' COMMANDS HERE ---
            if command.startswith("go"):
                RESPONSE_QUEUE.put("info string Received 'go'. Worker is simulating work...")
                # Simulate the blocking Lichess API call with a short delay
                # import time; time.sleep(1) 
                
                # Report a dummy move (to keep the GUI happy)
                RESPONSE_QUEUE.put("bestmove a1a2") # This is replaced later
            
            # --- STAGE 3: HANDLE OTHER COMMANDS ---
            else:
                RESPONSE_QUEUE.put(f"info string Unhandled command: {command}")

        # Sleep briefly to avoid consuming 100% CPU when queues are empty
        # Real code will block on Lichess API/Queue, so a sleep isn't strictly necessary.
        # import time; time.sleep(0.01) 


if __name__ == "__main__":
    # Start the worker thread
    worker_thread = threading.Thread(target=worker_thread_main, daemon=True)
    worker_thread.start()
    
    # Run the main UCI loop in the main thread (blocking on stdin)
    main_uci_loop()
    
    # Send quit command to worker and wait for it to join (clean exit)
    COMMAND_QUEUE.put("quit")
    worker_thread.join(timeout=2) # Wait a max of 2 seconds for clean exit
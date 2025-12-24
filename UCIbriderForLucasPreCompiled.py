import sys
import os
import threading
import time
from datetime import datetime
from queue import Queue, Empty

import traceback

def get_base_path():
    """ Get the base path, whether running from source or as a PyInstaller bundle. """
    if getattr(sys, 'frozen', False):
        # We are running in a bundle, use the executable's directory
        return os.path.dirname(sys.executable)
    else:
        # We are running in a normal Python environment
        return os.path.dirname(os.path.abspath(__file__))

def _pyinstaller_hooks():
    """Dummy function to ensure PyInstaller detects imports."""
    import berserk
    import chess

# --- LOGGING ---
LOG_FILE = os.path.join(get_base_path(), f"pyinstaller_bridge_{os.getpid()}.log")
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

def log_error(message: str):
    """Logs an error message along with a full traceback."""
    log(f"--- ERROR: {message} ---")
    log(traceback.format_exc())
    RESPONSE_QUEUE.put(f"info string ERROR: {message}")

# --- GLOBAL QUEUES ---
COMMAND_QUEUE = Queue()
RESPONSE_QUEUE = Queue()

# --- THREAD 1: STDIN READER ---
def stdin_reader_thread():
    """
    Reads stdin, handles fast commands directly, and dispatches slow commands
    to the worker thread.
    """
    log("--- Stdin Reader Thread Started ---")
    # The for-loop will block until a line is available or EOF is reached.
    for line in sys.stdin:
        command = line.strip()
        if command:
            log(f"<<< {command}")

            # Handle time-critical commands immediately
            if command == "uci":
                RESPONSE_QUEUE.put("id name Lucas Lichess Bridge by tidypy")
                RESPONSE_QUEUE.put("id author tidypy")
                RESPONSE_QUEUE.put("option name LichessToken type string default")
                RESPONSE_QUEUE.put("option name ChallengeColor type combo default Auto var Auto var White var Black")
                RESPONSE_QUEUE.put("option name Opponent type string default maia1")
                RESPONSE_QUEUE.put("option name TimeMode type combo default Realtime var Realtime var Correspondence")
                RESPONSE_QUEUE.put("option name Minutes type spin default 5 min 1 max 180")
                RESPONSE_QUEUE.put("option name Increment type spin default 3 min 0 max 180")
                RESPONSE_QUEUE.put("option name Rated type check default false")
                RESPONSE_QUEUE.put("option name VerifyConnection type button")
                RESPONSE_QUEUE.put("option name Resign type button")
                RESPONSE_QUEUE.put("uciok")
                RESPONSE_QUEUE.put(f"info string Logfile located at: {LOG_FILE}")
            elif command == "isready":
                RESPONSE_QUEUE.put("readyok")
            else:
                # Dispatch all other commands to the worker thread
                COMMAND_QUEUE.put(command)
    log("--- Stdin Reader Thread Finished (EOF) ---")
    COMMAND_QUEUE.put("quit")  # Signal other threads to exit

# --- THREAD 2: WORKER ---
class LichessWorker:
    def __init__(self):
        self.options = {
            "LichessToken": "",
            "ChallengeColor": "Auto",
            "Opponent": "maia1",
            "TimeMode": "Realtime",
            "Minutes": 5,
            "Increment": 3,
            "Rated": False,
        }
        self.client = None
        self.board = chess.Board()
        self.game_id = None
        self.my_color = None
        self.my_username = None

    def run(self):
        """Main loop for the worker thread."""
        log("--- Worker Thread Started ---")
        command = ""
        while True:
            try:
                command = COMMAND_QUEUE.get()
                log(f"WORKER: Processing command: '{command}'")

                if command == "quit":
                    self._handle_quit()
                    break
                elif command.startswith("ucinewgame"):
                    self._handle_ucinewgame()
                elif command.startswith("position"):
                    self._handle_position(command)
                elif command.startswith("go"):
                    self._handle_go(command)
                elif command.startswith("setoption"):
                    self._handle_setoption(command)
                else:
                    RESPONSE_QUEUE.put(f"info string WORKER: Unhandled command: {command}")
            except Exception:
                log_error(f"Unhandled exception in worker loop on command: {command}")

    def _handle_quit(self):
        log("WORKER: Quit command received. Shutting down.")
        RESPONSE_QUEUE.put("QUIT_SIGNAL")

    def _handle_ucinewgame(self):
        log("WORKER: Received ucinewgame, resetting board and game state.")
        self._resign_current_game()
        self.board.reset()
        self.game_id = None
        self.my_color = None

    def _handle_position(self, command):
        log(f"WORKER: Setting position: {command}")
        try:
            parts = command.split(" ", 1)
            if len(parts) > 1:
                self.board.reset()
                moves_str = ""
                if "startpos" in parts[1]:
                    if "moves" in parts[1]:
                        moves_str = parts[1].split("moves ", 1)[1]
                elif "fen" in parts[1]:
                    fen_parts = parts[1].split("moves ", 1)
                    self.board.set_fen(fen_parts[0].replace("fen ", ""))
                    if len(fen_parts) > 1:
                        moves_str = fen_parts[1]
                
                if moves_str:
                    for move in moves_str.split():
                        self.board.push_uci(move)
            log(f"WORKER: Board is now at FEN: {self.board.fen()}")
        except Exception:
            log_error(f"Failed to process position command: {command}")

    def _handle_go(self, command):
        if "ponder" in command:
            log("WORKER: Received 'go ponder'. Ignoring as pondering is not supported.")
            return

        if not self.client:
            RESPONSE_QUEUE.put("info string ERROR: LichessToken not set or invalid. Configure in engine options.")
            RESPONSE_QUEUE.put("bestmove 0000")
            return

        # Step 1: Find or create a game if we don't have one.
        if not self.game_id:
            self._find_or_create_game()

        # Step 2: If we still don't have a game, abort.
        if not self.game_id:
            log("WORKER: Failed to find or create a game.")
            RESPONSE_QUEUE.put("info string ERROR: Could not start a game. Check opponent name and settings.")
            RESPONSE_QUEUE.put("bestmove 0000")
            return

        # Step 3: Check if the human just made a move that needs to be sent.
        if self.my_color is not None and self.board.turn != self.my_color and self.board.move_stack:
            last_move = self.board.peek()
            log(f"WORKER: Human's turn is over. Sending move '{last_move.uci()}' to Lichess.")
            try:
                self.client.board.make_move(self.game_id, last_move)
                RESPONSE_QUEUE.put(f"info string Sent move {last_move.uci()} to Lichess.")
            except Exception:
                log_error(f"Lichess rejected move {last_move.uci()}")
                # Do not return a bestmove, as the state is now inconsistent.
                return

        # Step 4: Wait for the bot (opponent) to move.
        RESPONSE_QUEUE.put(f"info string WORKER: Waiting for {self.options['Opponent']} to move...")
        best_move = self._wait_for_bot_move()
        log(f"WORKER: Relaying bestmove {best_move} to GUI")
        RESPONSE_QUEUE.put(f"bestmove {best_move}")

    def _find_or_create_game(self):
        log(f"WORKER: Looking for ongoing game vs {self.options['Opponent']}")
        
        def check_ongoing(target_id=None):
            try:
                # OPTIMIZATION: If we have a target_id, check it directly first.
                # This bypasses get_ongoing() limits (default 10) which hides new games if user is busy.
                if target_id:
                    try:
                        log(f"WORKER: Verifying game {target_id} directly via export...")
                        game_data = self.client.games.export(target_id)
                        if game_data:
                            self.game_id = target_id
                            # 'color' might be in 'players' dict or top level depending on export format
                            # In export, usually it's implied by who is white/black. 
                            # We'll trust the challenge logic for color if not explicit, or derive from username.
                            return True
                    except Exception:
                        log(f"WORKER: Direct export of {target_id} failed (game might not exist yet).")

                games = self.client.games.get_ongoing()
                log(f"DEBUG: get_ongoing returned {len(games)} games. Raw: {games}")
                if games:
                    log(f"WORKER: API returned {len(games)} ongoing games.")
                for g in games:
                    # Handle both dict (newer berserk) and object (older berserk) responses safely
                    g_id = g.get('gameId') if isinstance(g, dict) else getattr(g, 'gameId', None)
                    g_color = g.get('color') if isinstance(g, dict) else getattr(g, 'color', None)
                    
                    if target_id:
                        if g_id == target_id:
                            self.game_id = g_id
                            self.my_color = chess.WHITE if g_color == 'white' else chess.BLACK
                            return True
                    
                    # Fallback: Check opponent name if ID check wasn't used or failed
                    g_opp = g.get('opponent', {}) if isinstance(g, dict) else getattr(g, 'opponent', None)
                    g_opp_name = g_opp.get('username') if isinstance(g_opp, dict) else getattr(g_opp, 'username', '') if g_opp else ''
                    
                    if not target_id and g_opp_name and g_opp_name.lower() == self.options['Opponent'].lower():
                        log(f"WORKER: Checking game {g_id} vs {g_opp_name}")
                        self.game_id = g_id
                        self.my_color = chess.WHITE if g_color == 'white' else chess.BLACK
                        return True
            except Exception as e:
                log(f"WORKER: check_ongoing failed: {e}")
            return False

        if check_ongoing():
            log(f"WORKER: Found existing game: {self.game_id}")
            RESPONSE_QUEUE.put(f"info string Found and resumed game: {self.game_id}")
            return

        log(f"WORKER: No existing game found. Creating new challenge.")
        RESPONSE_QUEUE.put(f"info string Challenging {self.options['Opponent']}...")
        
        # Determine color logic
        # If Engine is White (board.turn == WHITE), we want Bot to be White? 
        # No. If Engine is White, Engine moves first. But Engine is a Bridge.
        # The Bridge relays moves. If Lucas thinks Engine is White, Lucas expects Engine to move.
        # Engine asks Bot. So Bot must be White.
        # If Bot is White, we (Challenger) must be Black.
        if self.options['ChallengeColor'] == 'Auto':
            color_param = 'black' if self.board.turn == chess.WHITE else 'white'
        else:
            color_param = self.options['ChallengeColor'].lower()

        challenge_id = None

        try:
            challenge_params = {
                "username": self.options['Opponent'],
                "rated": self.options['Rated'],
                "color": color_param,
            }
            if self.options['TimeMode'] == 'Realtime':
                challenge_params.update({
                    "clock_limit": self.options['Minutes'] * 60,
                    "clock_increment": self.options['Increment'],
                })
            # Add other time modes (correspondence, etc.) here if needed

            # Capture and log the response to verify acceptance/status
            response = self.client.challenges.create(**challenge_params)
            log(f"WORKER: Challenge created. Response: {response}")
            
            if isinstance(response, dict) and response.get('status') == 'declined':
                RESPONSE_QUEUE.put("info string Challenge DECLINED by opponent.")
                log("WORKER: Challenge was declined.")
                return
            
            if isinstance(response, dict):
                challenge_id = response.get('id')
                log(f"WORKER: Extracted Challenge ID: {challenge_id}")
                log(f"DEBUG TEST: Will use Challenge ID {challenge_id} to verify game start.")

            # CRITICAL FIX: Lichess needs time to propagate the new game to the API.
            log("WORKER: Pausing 2 seconds to allow Lichess to index the new game...")
            time.sleep(2.0)
            RESPONSE_QUEUE.put("info string Challenge sent. Waiting for acceptance...")
        except Exception as e:
            log_error(f"Failed to create Lichess challenge: {e}")
            return

        # Wait for game to start
        for i in range(30):
            if check_ongoing(target_id=challenge_id):
                log(f"WORKER: Game started: {self.game_id}")
                RESPONSE_QUEUE.put(f"info string Game started: {self.game_id}")
                return
            time.sleep(1)
        
        log("WORKER: Timed out waiting for game start.")

    def _wait_for_bot_move(self):
        """
        Polls the Lichess API for the game state until the bot makes a move.
        Returns the UCI string of the move (e.g., "e2e4") or "0000" on failure.
        """
        start_ply = self.board.ply()
        retries = 0
        # Poll for up to 10 minutes (600 seconds)
        while retries < 600:
            # Check for interrupt commands (stop/quit) from GUI
            if not COMMAND_QUEUE.empty():
                try:
                    cmd = COMMAND_QUEUE.get_nowait()
                    if cmd in ["stop", "quit"]:
                        log(f"WORKER: Received '{cmd}' while waiting for move. Aborting wait.")
                        return "0000"
                except Empty:
                    pass

            try:
                # We use export instead of stream for simpler synchronous polling
                game_json = self.client.games.export(self.game_id, moves=True)
                moves_str = game_json.get('moves', '')
                
                # Reconstruct board from moves to check for progress
                temp_board = chess.Board()
                if moves_str:
                    for m in moves_str.split():
                        temp_board.push_uci(m)
                
                if temp_board.ply() > start_ply:
                    # A new move has been made!
                    last_move = temp_board.peek()
                    self.board.push(last_move) # Sync local board
                    log(f"WORKER: Detected new move from API: {last_move.uci()}")
                    log(f"WORKER: Bot played {last_move.uci()}")
                    return last_move.uci()
                
                # Check if game ended
                if game_json.get('status') in ['mate', 'resign', 'outoftime', 'draw', 'aborted']:
                    log(f"WORKER: Game ended with status {game_json.get('status')}")
                    return "0000"

            except Exception as e:
                log(f"WORKER: Polling error: {e}")
            
            time.sleep(1.0)
            retries += 1
        
        log_error("Timed out waiting for bot move.")
        return "0000"

    def _handle_setoption(self, command):
        try:
            parts = command.split(" value ", 1)
            name_part = parts[0].replace("setoption name ", "").strip()
            value = parts[1].strip() if len(parts) > 1 else ""

            log(f"WORKER: Setting option '{name_part}' to '{value}'")

            if name_part == "VerifyConnection":
                self._validate_connection()
                return

            if name_part == "Resign":
                self._resign_current_game()
                return

            if name_part in self.options:
                # Type conversion for spin and check options
                if isinstance(self.options[name_part], int):
                    self.options[name_part] = int(value)
                elif isinstance(self.options[name_part], bool):
                    self.options[name_part] = value.lower() == 'true'
                else:
                    self.options[name_part] = value

                log(f"WORKER: Set option '{name_part}' to '{self.options[name_part]}'")

                if name_part == "LichessToken" and value:
                    self._authenticate(value)
            else:
                log(f"WORKER: Unknown option: {name_part}")
        except Exception:
            log_error(f"Failed to parse setoption command: {command}")

    def _authenticate(self, token):
        try:
            RESPONSE_QUEUE.put("info string WORKER: Token received. Authenticating...")
            session = berserk.TokenSession(token)
            self.client = berserk.Client(session)
            account = self.client.account.get()
            self.my_username = account['id']
            RESPONSE_QUEUE.put(f"info string WORKER: Auth successful as {self.my_username}.")
        except Exception:
            self.client = None
            self.my_username = None
            log_error("Lichess authentication failed. Check token and connection.")

    def _validate_connection(self):
        """Performs a pre-flight check of the token and opponent."""
        if not self.client:
            RESPONSE_QUEUE.put("info string [ERROR] No token set. Please set LichessToken first.")
            return

        RESPONSE_QUEUE.put("info string Validating connection...")
        try:
            # 1. Check Account
            account = self.client.account.get()
            username = account.get('id')
            RESPONSE_QUEUE.put(f"info string [SUCCESS] Logged in as: {username}")

            # 2. Check Opponent
            opp_name = self.options['Opponent']
            try:
                self.client.users.get_public_data(opp_name)
                RESPONSE_QUEUE.put(f"info string [SUCCESS] Opponent '{opp_name}' found.")
            except Exception:
                RESPONSE_QUEUE.put(f"info string [WARNING] Opponent '{opp_name}' not found or invalid.")

        except Exception as e:
            RESPONSE_QUEUE.put(f"info string [ERROR] Validation failed: {e}")

    def _resign_current_game(self):
        """Resigns or aborts the current game if one exists."""
        if self.game_id and self.client:
            try:
                log(f"WORKER: Attempting to resign/abort game {self.game_id}...")
                self.client.board.resign(self.game_id)
                RESPONSE_QUEUE.put(f"info string Resigned game {self.game_id}")
            except Exception as e:
                log(f"WORKER: Failed to resign game (might already be over): {e}")
        self.game_id = None

def worker_thread_main():
    global berserk, chess
    try:
        log("Loading dependencies (berserk, chess)...")
        
        # FIX: PyInstaller often fails to bundle package metadata.
        # We monkey-patch importlib.metadata.version to return a dummy version
        # if berserk's metadata is missing, preventing the crash.
        import importlib.metadata
        _orig_version = importlib.metadata.version
        def _patched_version(distribution_name):
            try:
                return _orig_version(distribution_name)
            except Exception: # Catch PackageNotFoundError and others
                if distribution_name == 'berserk':
                    return '0.0.0'
                raise
        importlib.metadata.version = _patched_version

        import berserk
        import chess
        log(f"Dependencies loaded. Berserk version: {getattr(berserk, '__version__', 'unknown')}")
        log("Dependencies loaded.")
    except Exception as e:
        log_error(f"Failed to import dependencies: {e}")
        return
    worker = LichessWorker()
    worker.run()

# --- MAIN THREAD: STDOUT WRITER ---
def main():
    """Sets up threads and runs the main loop to print responses to stdout."""
    log("--- Engine Starting ---")

    # Configure unbuffered I/O
    try:
        sys.stdout.reconfigure(line_buffering=True, encoding='utf-8')
        sys.stdin.reconfigure(encoding='utf-8')
        log("Reconfigured stdout/stdin for UTF-8 and line buffering.")
    except Exception as e:
        log(f"Could not reconfigure stdio: {e}. Using default buffering.")

    # Start the background threads
    stdin_thread = threading.Thread(target=stdin_reader_thread, daemon=True)
    worker = threading.Thread(target=worker_thread_main, daemon=True)
    stdin_thread.start()
    worker.start()
    log("Stdin reader and worker threads started.")

    # The main thread is now dedicated to printing responses.
    log("--- Stdout Thread (Main) Started ---")
    while True:
        try:
            # This blocks until the worker thread provides a response.
            message = RESPONSE_QUEUE.get()
            
            if message == "QUIT_SIGNAL":
                log("STDOUT: Received quit signal. Exiting.")
                break
            
            log(f">>> {message}")
            print(message, flush=True)
        except Exception:
            log_error("Unhandled exception in main stdout loop")
    
    log("--- Engine Finished ---")

if __name__ == "__main__":
    main()
#!/usr/bin/ python3
"""
Lichess UCI Bridge for Lucas Chess - v3.1
With enhanced file logging for debugging
"""

import sys
import os
import threading
import time
from datetime import datetime
import chess
import berserk
from queue import Queue, Empty
from typing import Optional, Dict, Any

# ============================================================================
# CONFIGURATION
# ============================================================================
VERSION = "3.1"

DEFAULT_OPPONENT = "maia1"
DEFAULT_PLAY_AS = "random"
DEFAULT_VARIANT = "standard"
DEFAULT_TIME_MODE = "realtime"
DEFAULT_MINUTES = 5
DEFAULT_INCREMENT = 3
DEFAULT_DAYS = 1
DEFAULT_RATED = False

CHALLENGE_TIMEOUT = 30
CHALLENGE_POLL_INTERVAL = 1.0
MOVE_TIMEOUT = 180
STREAM_POLL_INTERVAL = 0.5

DEBUG = True
LOG_TO_FILE = True  # Set True to write logs to file

# ============================================================================
# LOGGING
# ============================================================================
class Logger:
    def __init__(self):
        self.file = None
        self.lock = threading.Lock()

        if LOG_TO_FILE:
            # Create log file in same directory as script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            log_path = os.path.join(script_dir, "lichess_bridge.log")

            try:
                self.file = open(log_path, "a", encoding="utf-8")
                self._write_to_file(f"\n{'='*60}")
                self._write_to_file(f"SESSION STARTED: {datetime.now().isoformat()}")
                self._write_to_file(f"{'='*60}\n")
            except Exception as e:
                sys.stderr.write(f"[BRIDGE] Could not open log file: {e}\n")

    def _write_to_file(self, msg: str):
        if self.file:
            try:
                with self.lock:
                    self.file.write(msg + "\n")
                    self.file.flush()
            except:
                pass

    def log(self, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        formatted = f"[{timestamp}] {msg}"

        if DEBUG:
            sys.stderr.write(f"[BRIDGE] {msg}\n")
            sys.stderr.flush()

        self._write_to_file(formatted)

    def close(self):
        if self.file:
            self._write_to_file(f"\nSESSION ENDED: {datetime.now().isoformat()}\n")
            self.file.close()

# Global logger
logger = Logger()

def log(msg: str) -> None:
    logger.log(msg)

def send(msg: str) -> None:
    print(msg, flush=True)
    log(f">>> {msg}")

def info(msg: str) -> None:
    send(f"info string {msg}")

# ============================================================================
# LICHESS BRIDGE ENGINE
# ============================================================================
class LichessBridge:
    def __init__(self):
        log(f"Initializing Lichess Bridge v{VERSION}")

        # === UCI Options ===
        self.token: str = ""
        self.opponent: str = DEFAULT_OPPONENT
        self.play_as: str = DEFAULT_PLAY_AS
        self.variant: str = DEFAULT_VARIANT
        self.time_mode: str = DEFAULT_TIME_MODE
        self.minutes: int = DEFAULT_MINUTES
        self.increment: int = DEFAULT_INCREMENT
        self.days: int = DEFAULT_DAYS
        self.rated: bool = DEFAULT_RATED

        # === Lichess State ===
        self.client: Optional[berserk.Client] = None
        self.my_username: str = ""
        self.game_id: Optional[str] = None
        self.my_color: Optional[chess.Color] = None

        # === Chess State ===
        self.board = chess.Board()

        # === Threading ===
        self.search_thread: Optional[threading.Thread] = None
        self.stop_flag = threading.Event()
        self.move_queue: Queue = Queue()
        self.lock = threading.Lock()
        self.stream_thread: Optional[threading.Thread] = None
        self.stream_active = threading.Event()

        log("Initialization complete")

    # ========================================================================
    # UCI MAIN LOOP
    # ========================================================================
    def run(self) -> None:
        log(f"Starting UCI loop")

        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    log("EOF on stdin, exiting")
                    break

                line = line.strip()
                if not line:
                    continue

                log(f"<<< {line}")
                cmd = line.split()[0].lower()

                if cmd == "uci":
                    self._handle_uci()
                elif cmd == "setoption":
                    self._handle_setoption(line)
                elif cmd == "isready":
                    self._handle_isready()
                elif cmd == "ucinewgame":
                    self._handle_ucinewgame()
                elif cmd == "position":
                    self._handle_position(line)
                elif cmd == "go":
                    self._handle_go()
                elif cmd == "stop":
                    self._handle_stop()
                elif cmd == "quit":
                    log("Quit command received")
                    break
                else:
                    log(f"Unknown command: {cmd}")

            except KeyboardInterrupt:
                log("Keyboard interrupt")
                break
            except Exception as e:
                log(f"Main loop error: {e}")
                import traceback
                log(traceback.format_exc())

        self._cleanup()
        logger.close()

    # ========================================================================
    # UCI COMMAND HANDLERS
    # ========================================================================
    def _handle_uci(self) -> None:
        log("Handling UCI command")

        send(f"id name Lichess Bridge v{VERSION}")
        send("id author Human-Bot Bridge")

        send("option name LichessToken type string default ")
        send(f"option name Opponent type string default {self.opponent}")
        send(f"option name PlayAs type combo default {self.play_as} var white var black var random")
        send(f"option name Variant type combo default {self.variant} "
             "var standard var chess960 var crazyhouse var antichess "
             "var atomic var horde var kingOfTheHill var racingKings var threeCheck")
        send(f"option name TimeMode type combo default {self.time_mode} "
             "var realtime var correspondence var unlimited")
        send(f"option name Minutes type spin default {self.minutes} min 1 max 180")
        send(f"option name Increment type spin default {self.increment} min 0 max 180")
        send(f"option name Days type spin default {self.days} min 1 max 14")
        send(f"option name Rated type check default {'true' if self.rated else 'false'}")
        send(f"option name Debug type check default {'true' if DEBUG else 'false'}")

        send("uciok")
        log("UCI handshake complete")

    def _handle_setoption(self, line: str) -> None:
        try:
            line_lower = line.lower()

            if " value " in line_lower:
                value_pos = line_lower.index(" value ")
                name_part = line[10:value_pos].strip()
                value_part = line[value_pos + 7:].strip()
                if name_part.lower().startswith("name "):
                    name_part = name_part[5:]
            else:
                parts = line[10:].strip()
                name_part = parts[5:] if parts.lower().startswith("name ") else parts
                value_part = ""

            name_lower = name_part.lower()

            log(f"Setting option: {name_part} = '{value_part}'")

            if name_lower == "lichesstoken":
                self.token = value_part
                self.client = None
                self.my_username = ""
                log(f"Token set (length={len(value_part)})")

            elif name_lower == "opponent":
                self.opponent = value_part.strip()
                log(f"Opponent: {self.opponent}")

            elif name_lower == "playas":
                if value_part.lower() in ("white", "black", "random"):
                    self.play_as = value_part.lower()
                log(f"PlayAs: {self.play_as}")

            elif name_lower == "variant":
                self.variant = value_part
                log(f"Variant: {self.variant}")

            elif name_lower == "timemode":
                if value_part.lower() in ("realtime", "correspondence", "unlimited"):
                    self.time_mode = value_part.lower()
                log(f"TimeMode: {self.time_mode}")

            elif name_lower == "minutes":
                self.minutes = max(1, min(180, int(value_part)))
                log(f"Minutes: {self.minutes}")

            elif name_lower == "increment":
                self.increment = max(0, min(180, int(value_part)))
                log(f"Increment: {self.increment}")

            elif name_lower == "days":
                self.days = max(1, min(14, int(value_part)))
                log(f"Days: {self.days}")

            elif name_lower == "rated":
                self.rated = value_part.lower() in ("true", "1", "on")
                log(f"Rated: {self.rated}")

            elif name_lower == "debug":
                global DEBUG
                DEBUG = value_part.lower() in ("true", "1", "on")
                log(f"Debug: {DEBUG}")

        except Exception as e:
            log(f"setoption error: {e}")

    def _handle_isready(self) -> None:
        log("Handling isready")

        if self.token and not self.client:
            log("Token present, attempting connection...")
            self._connect()
        elif not self.token:
            log("No token set yet")
        else:
            log("Already connected")

        send("readyok")

    def _handle_ucinewgame(self) -> None:
        log("Handling ucinewgame")
        self._stop_threads()

        with self.lock:
            self.board.reset()
            self.game_id = None
            self.my_color = None

        self._clear_queue()
        log("Board reset, ready for new game")

    def _handle_position(self, line: str) -> None:
        log(f"Handling position: {line}")

        with self.lock:
            self.board.reset()
            line_lower = line.lower()

            if "fen " in line_lower:
                try:
                    fen_start = line_lower.index("fen ") + 4
                    fen_end = line_lower.index(" moves") if " moves" in line_lower else len(line)
                    fen = line[fen_start:fen_end].strip()
                    self.board.set_fen(fen)
                    log(f"FEN set: {fen}")
                except Exception as e:
                    log(f"FEN error: {e}")

            if " moves " in line_lower:
                try:
                    moves_start = line_lower.index(" moves ") + 7
                    moves = line[moves_start:].split()
                    for move_uci in moves:
                        self.board.push_uci(move_uci)
                    log(f"Applied {len(moves)} moves, position: {self.board.fen()}")
                except Exception as e:
                    log(f"Move error: {e}")

    def _handle_go(self) -> None:
        log("Handling go")
        self._handle_stop()

        if not self.token:
            log("ERROR: No token configured")
            info("ERROR: Set LichessToken in Parameters")
            send("bestmove 0000")
            return

        if not self.client:
            log("Client not connected, attempting connection...")
            if not self._connect():
                info("ERROR: Connection failed")
                send("bestmove 0000")
                return

        self.stop_flag.clear()
        self.search_thread = threading.Thread(target=self._play, daemon=True)
        self.search_thread.start()
        log("Search thread started")

    def _handle_stop(self) -> None:
        log("Handling stop")
        self.stop_flag.set()
        if self.search_thread and self.search_thread.is_alive():
            log("Waiting for search thread to stop...")
            self.search_thread.join(timeout=2)
            log("Search thread stopped")

    # ========================================================================
    # LICHESS API
    # ========================================================================
    def _connect(self) -> bool:
        if not self.token:
            log("Cannot connect: no token")
            return False

        try:
            log("Connecting to Lichess API...")
            session = berserk.TokenSession(self.token)
            self.client = berserk.Client(session)

            log("Fetching account info...")
            account = self.client.account.get()
            self.my_username = account['id']

            log(f"Connected successfully as: {self.my_username}")
            info(f"Logged in as {self.my_username}")
            return True

        except berserk.exceptions.ResponseError as e:
            log(f"Auth failed: {e}")
            info("Login failed - check token")
            self.client = None
            return False
        except Exception as e:
            log(f"Connection error: {e}")
            import traceback
            log(traceback.format_exc())
            self.client = None
            return False

    def _find_existing_game(self) -> bool:
        log(f"Looking for existing game vs {self.opponent}...")

        try:
            games = list(self.client.games.get_ongoing())
            log(f"Found {len(games)} ongoing games")

            for game in games:
                opp = game.get('opponent', {}).get('username', '').lower()
                log(f"  Game vs {opp}")

                if opp == self.opponent.lower():
                    with self.lock:
                        self.game_id = game['gameId']
                        self.my_color = chess.WHITE if game['color'] == 'white' else chess.BLACK

                    log(f"Found existing game: {self.game_id}, playing as {game['color']}")
                    info(f"Resuming game vs {self.opponent}")
                    return True

            log("No existing game found")
            return False

        except Exception as e:
            log(f"Error checking games: {e}")
            return False

    def _create_challenge(self) -> bool:
        try:
            # Build description
            if self.time_mode == "realtime":
                time_desc = f"{self.minutes}+{self.increment}"
            elif self.time_mode == "correspondence":
                time_desc = f"{self.days} days"
            else:
                time_desc = "unlimited"

            log(f"Creating challenge:")
            log(f"  Opponent: {self.opponent}")
            log(f"  Variant: {self.variant}")
            log(f"  Time: {time_desc}")
            log(f"  Rated: {self.rated}")
            log(f"  Color: {self.play_as}")

            info(f"Challenging {self.opponent} ({time_desc})...")

            # Build params
            params: Dict[str, Any] = {
                "username": self.opponent,
                "rated": self.rated,
                "color": self.play_as,
            }

            if self.variant.lower() != "standard":
                params["variant"] = self.variant

            if self.time_mode == "realtime":
                params["clock_limit"] = self.minutes * 60
                params["clock_increment"] = self.increment
            elif self.time_mode == "correspondence":
                params["days"] = self.days

            log(f"API params: {params}")

            # Send challenge
            response = self.client.challenges.create(**params)
            log(f"Challenge response: {response}")

            # Check immediate game start
            if 'game' in response:
                game_info = response['game']
                with self.lock:
                    self.game_id = game_info.get('id')
                    if 'color' in game_info:
                        self.my_color = chess.WHITE if game_info['color'] == 'white' else chess.BLACK
                log(f"Game started immediately: {self.game_id}")
                info("Game started!")
                return True

            challenge_id = response.get('challenge', {}).get('id', 'unknown')
            log(f"Challenge created: {challenge_id}, polling for game start...")
            info("Waiting for bot to accept...")

            return self._poll_for_game_start()

        except berserk.exceptions.ResponseError as e:
            log(f"Challenge API error: {e}")
            info(f"Challenge failed: {e}")
            return False
        except Exception as e:
            log(f"Challenge error: {e}")
            import traceback
            log(traceback.format_exc())
            return False

    def _poll_for_game_start(self) -> bool:
        start_time = time.time()
        poll_count = 0

        while time.time() - start_time < CHALLENGE_TIMEOUT:
            if self.stop_flag.is_set():
                log("Polling cancelled by stop flag")
                return False

            poll_count += 1
            elapsed = time.time() - start_time
            log(f"Poll #{poll_count} ({elapsed:.1f}s elapsed)")

            try:
                for game in self.client.games.get_ongoing():
                    opp = game.get('opponent', {}).get('username', '').lower()

                    if opp == self.opponent.lower():
                        with self.lock:
                            self.game_id = game['gameId']
                            color_str = game.get('color', 'white')
                            self.my_color = chess.WHITE if color_str == 'white' else chess.BLACK

                        log(f"Game found: {self.game_id}, playing as {color_str}")
                        info(f"Playing as {color_str}")
                        return True

            except Exception as e:
                log(f"Poll error: {e}")

            time.sleep(CHALLENGE_POLL_INTERVAL)

        log(f"Timeout after {CHALLENGE_TIMEOUT}s ({poll_count} polls)")
        info("Challenge timed out")
        info(f"Check {self.opponent}'s profile for accepted settings")
        return False

    def _start_stream(self) -> None:
        if self.stream_thread and self.stream_thread.is_alive():
            log("Stream already running")
            return

        log(f"Starting game stream for {self.game_id}")
        self.stream_active.set()
        self.stream_thread = threading.Thread(target=self._stream_worker, daemon=True)
        self.stream_thread.start()

    def _stream_worker(self) -> None:
        game_id = self.game_id
        if not game_id:
            log("Stream worker: no game_id")
            return

        log(f"Stream worker started for game {game_id}")
        last_move_count = 0

        try:
            for event in self.client.board.stream_game_state(game_id):
                if not self.stream_active.is_set():
                    log("Stream stopped by flag")
                    break

                event_type = event.get('type', '')
                log(f"Stream event: {event_type}")

                if event_type == 'gameFull':
                    state = event.get('state', {})

                    white_player = event.get('white', {})
                    white_id = white_player.get('id', '').lower()

                    with self.lock:
                        if white_id == self.my_username.lower():
                            self.my_color = chess.WHITE
                            log("Confirmed: playing as WHITE")
                        else:
                            self.my_color = chess.BLACK
                            log("Confirmed: playing as BLACK")

                    moves_str = state.get('moves', '')
                    last_move_count = len(moves_str.split()) if moves_str else 0
                    log(f"Initial state: {last_move_count} moves")

                    # Check if opponent already moved
                    if last_move_count > 0:
                        moves = moves_str.split()
                        self.move_queue.put(('move', moves[-1], last_move_count))

                elif event_type == 'gameState':
                    status = event.get('status', 'started')

                    if status not in ('created', 'started'):
                        winner = event.get('winner', '')
                        log(f"Game ended: {status}, winner: {winner}")
                        self.move_queue.put(('game_over', status, winner))
                        break

                    moves_str = event.get('moves', '')
                    moves = moves_str.split() if moves_str else []
                    move_count = len(moves)

                    log(f"State update: {move_count} moves (was {last_move_count})")

                    if move_count > last_move_count:
                        new_move = moves[-1]
                        log(f"New move: {new_move}")
                        self.move_queue.put(('move', new_move, move_count))
                        last_move_count = move_count

        except Exception as e:
            log(f"Stream error: {e}")
            import traceback
            log(traceback.format_exc())
            self.move_queue.put(('error', str(e)))

        log("Stream worker ended")

    def _send_move(self, move: chess.Move) -> bool:
        if not self.game_id:
            log("Cannot send move: no game_id")
            return False

        try:
            log(f"Sending move: {move.uci()}")
            self.client.board.make_move(self.game_id, move.uci())
            log(f"Move sent successfully")
            return True
        except berserk.exceptions.ResponseError as e:
            log(f"Move rejected: {e}")
            info(f"Move rejected: {e}")
            return False
        except Exception as e:
            log(f"Move error: {e}")
            return False

    # ========================================================================
    # MAIN GAME LOGIC
    # ========================================================================
    def _play(self) -> None:
        log("Play thread started")

        try:
            # Step 1: Ensure game exists
            if not self.game_id:
                log("No game_id, looking for existing game or creating challenge")

                if not self._find_existing_game():
                    if not self._create_challenge():
                        log("Failed to create game")
                        send("bestmove 0000")
                        return

            # Step 2: Start stream
            self._start_stream()
            time.sleep(0.5)

            # Step 3: Get current state
            with self.lock:
                local_move_count = len(self.board.move_stack)
                my_turn_locally = (self.board.turn == self.my_color)
                last_move = self.board.peek() if self.board.move_stack else None

            log(f"Local state:")
            log(f"  Move count: {local_move_count}")
            log(f"  My color: {'WHITE' if self.my_color == chess.WHITE else 'BLACK'}")
            log(f"  My turn locally: {my_turn_locally}")
            log(f"  Board turn: {'WHITE' if self.board.turn == chess.WHITE else 'BLACK'}")
            log(f"  Last move: {last_move}")
            log(f"  FEN: {self.board.fen()}")

            # Step 4: Send human's move if needed
            if not my_turn_locally and last_move:
                log("Human just moved, sending to Lichess")
                info("Sending your move...")
                self._send_move(last_move)

            # Step 5: Wait for opponent
            log(f"Waiting for opponent move...")
            info(f"Waiting for {self.opponent}...")
            bot_move = self._wait_for_move(local_move_count)

            # Step 6: Return result
            if bot_move:
                log(f"Got bot move: {bot_move}")
                with self.lock:
                    try:
                        self.board.push_uci(bot_move)
                        log(f"Applied to local board: {self.board.fen()}")
                    except ValueError as e:
                        log(f"Could not apply move: {e}")
                send(f"bestmove {bot_move}")
            else:
                log("No move received, sending null move")
                send("bestmove 0000")

        except Exception as e:
            log(f"Play error: {e}")
            import traceback
            log(traceback.format_exc())
            send("bestmove 0000")

        log("Play thread ended")

    def _wait_for_move(self, expected_count: int) -> Optional[str]:
        deadline = time.time() + MOVE_TIMEOUT
        log(f"Waiting for move (expecting > {expected_count} moves)")

        while time.time() < deadline:
            if self.stop_flag.is_set():
                log("Wait cancelled by stop flag")
                return None

            try:
                msg = self.move_queue.get(timeout=STREAM_POLL_INTERVAL)
                msg_type = msg[0]

                log(f"Queue message: {msg}")

                if msg_type == 'move':
                    move_uci, move_count = msg[1], msg[2]

                    if move_count > expected_count:
                        log(f"Accepting move: {move_uci} (count {move_count} > {expected_count})")
                        return move_uci
                    else:
                        log(f"Ignoring move (count {move_count} <= {expected_count})")

                elif msg_type == 'game_over':
                    status = msg[1]
                    winner = msg[2] if len(msg) > 2 else ''
                    log(f"Game over: {status}, winner: {winner}")
                    info(f"Game over: {status}")
                    with self.lock:
                        self.game_id = None
                    return None

                elif msg_type == 'error':
                    log(f"Stream error: {msg[1]}")
                    return None

            except Empty:
                continue

        log(f"Timeout after {MOVE_TIMEOUT}s")
        info("Timeout waiting for opponent")
        return None

    # ========================================================================
    # CLEANUP
    # ========================================================================
    def _clear_queue(self) -> None:
        count = 0
        while not self.move_queue.empty():
            try:
                self.move_queue.get_nowait()
                count += 1
            except Empty:
                break
        if count:
            log(f"Cleared {count} items from queue")

    def _stop_threads(self) -> None:
        log("Stopping threads...")
        self.stop_flag.set()
        self.stream_active.clear()

        if self.search_thread and self.search_thread.is_alive():
            self.search_thread.join(timeout=2)
        if self.stream_thread and self.stream_thread.is_alive():
            self.stream_thread.join(timeout=2)

        log("Threads stopped")

    def _cleanup(self) -> None:
        log("Cleanup started")
        self._stop_threads()

        if self.client and self.game_id:
            try:
                log(f"Resigning game {self.game_id}")
                self.client.board.resign_game(self.game_id)
            except Exception as e:
                log(f"Resign error: {e}")

        log("Cleanup complete")


# ============================================================================
# ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    bridge = LichessBridge()
    bridge.run()

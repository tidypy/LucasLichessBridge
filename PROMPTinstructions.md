# Role
You are an expert Python developer specializing in Chess Engines (UCI Protocol) and API integrations.

# Project Objective
I need a Python script that acts as a **UCI Chess Engine** to bridge **Lucas Chess** (GUI) with the **Lichess API**.
The goal is to play against Lichess Bots (e.g., Maia1) using the Lucas Chess interface.

# Technical Constraints
1.  **OS:** Linux (Arch/CachyOS).
2.  **Distribution:** The script must be compiled into a single-file executable using **PyInstaller**.
3.  **Libraries:** `berserk` (preferred) or `requests` (if raw API is more stable), `python-chess`.

# Critical Requirements (Based on previous failures)
1.  **Instant Startup (Lazy Loading):** Lucas Chess times out if the engine doesn't reply to the `uci` command instantly. Heavy imports (`berserk`, `chess`) MUST happen in a background thread, not at the top level.
2.  **PyInstaller Compatibility:** The code must handle missing metadata. `berserk` often crashes in frozen builds because `importlib.metadata` fails. Include a hook or patch to prevent this.
3.  **Robust Game Detection:**
    *   When a challenge is sent, Lichess takes 1-3 seconds to index the game.
    *   The code must robustly wait for the game to start, preferably using the **Challenge ID** returned by the create-challenge endpoint, rather than searching by opponent name.
4.  **Thread Safety:**
    *   **Thread 1 (Main/Stdin):** Must handle `uci`, `isready`, and `quit` instantly.
    *   **Thread 2 (Worker):** Handles the blocking API calls.
    *   **Thread 3 (Stdout):** Thread-safe printing to the GUI.
5.  **Berserk Versioning:** Assume the installed version of `berserk` might be older and does NOT support the `limit` parameter in `games.get_ongoing()`.

# The Specific Workflow to Implement
1.  **Init:** Engine starts, replies `id name ...`, `uciok`.
2.  **Config:** User sets `LichessToken` and `Opponent` via UCI options.
3.  **Play:**
    *   Lucas sends `position startpos ...` then `go`.
    *   Bridge checks if a game exists. If not, it challenges `Opponent`.
    *   Bridge **waits** for the challenge to be accepted.
    *   Bridge relays moves between Lichess and Lucas Chess.
4.  **Stop:** If Lucas sends `stop` or `ucinewgame`, the bridge must immediately stop polling the API and reset.

# Request
Please provide:
1.  The complete, robust Python script (`LichessBridge.py`).
2.  The `PyInstaller` command or `.spec` file configuration to build it correctly (handling hidden imports and metadata).

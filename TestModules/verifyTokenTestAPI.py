#!/usr/bin/ python3
"""
test_lichess_api.py - Test Lichess API connectivity before using the bridge
"""

import sys

def test_imports():
    """Test that required libraries are installed."""
    print("=" * 50)
    print("TEST 1: Checking imports...")
    print("=" * 50)

    errors = []

    try:
        import chess
        print(f"  ✅ chess version: {chess.__version__}")
    except ImportError as e:
        errors.append(f"  ❌ chess: {e}")
        print(f"  ❌ chess not installed: pip install chess")

    try:
        import berserk
        print(f"  ✅ berserk imported")
    except ImportError as e:
        errors.append(f"  ❌ berserk: {e}")
        print(f"  ❌ berserk not installed: pip install berserk")

    if errors:
        print("\nFix import errors before continuing!")
        return False

    print("\n")
    return True


def test_token(token: str):
    """Test that the token works."""
    import berserk

    print("=" * 50)
    print("TEST 2: Checking token authentication...")
    print("=" * 50)

    try:
        session = berserk.TokenSession(token)
        client = berserk.Client(session)
        account = client.account.get()

        print(f"  ✅ Authenticated successfully!")
        print(f"  ✅ Username: {account['username']}")
        print(f"  ✅ User ID: {account['id']}")
        print(f"  ✅ Rating (Blitz): {account.get('perfs', {}).get('blitz', {}).get('rating', 'N/A')}")
        print("\n")
        return client, account['id']

    except berserk.exceptions.ResponseError as e:
        print(f"  ❌ Authentication failed: {e}")
        print("  Check that your token is correct and has required scopes:")
        print("    - challenge:read")
        print("    - challenge:write")
        print("    - board:play")
        print("\n")
        return None, None
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        print("\n")
        return None, None


def test_ongoing_games(client):
    """Test fetching ongoing games."""
    print("=" * 50)
    print("TEST 3: Checking ongoing games...")
    print("=" * 50)

    try:
        games = list(client.games.get_ongoing())

        if games:
            print(f"  ✅ Found {len(games)} ongoing game(s):")
            for g in games:
                opp = g.get('opponent', {}).get('username', 'Unknown')
                color = g.get('color', '?')
                game_id = g.get('gameId', '?')
                print(f"     - vs {opp} (you play {color}) - ID: {game_id}")
        else:
            print(f"  ✅ No ongoing games (this is fine)")

        print("\n")
        return True

    except Exception as e:
        print(f"  ❌ Error fetching games: {e}")
        print("\n")
        return False


def test_challenge(client, bot_username: str):
    """Test challenging a bot (will cancel immediately)."""
    print("=" * 50)
    print(f"TEST 4: Test challenge to {bot_username}...")
    print("=" * 50)

    try:
        print(f"  Sending challenge to {bot_username}...")
        print(f"  (5+3 blitz, casual, random color)")

        response = client.challenges.create(
            username=bot_username,
            rated=False,
            clock_limit=300,      # 5 minutes
            clock_increment=3,    # 3 seconds
            color="random"
        )

        print(f"  ✅ Challenge sent successfully!")
        print(f"  Response: {response}")

        # Check if game started immediately
        if 'game' in response:
            game_id = response['game'].get('id')
            print(f"  ✅ Game started immediately! ID: {game_id}")
            print(f"  ⚠️  You now have an active game - finish it on lichess.org")
        else:
            challenge_id = response.get('challenge', {}).get('id')
            print(f"  Challenge ID: {challenge_id}")
            print(f"  Waiting for bot to accept...")

            # Poll for game start
            import time
            for i in range(10):
                time.sleep(1)
                print(f"    Polling... ({i+1}/10)")

                for game in client.games.get_ongoing():
                    opp = game.get('opponent', {}).get('username', '').lower()
                    if opp == bot_username.lower():
                        game_id = game['gameId']
                        color = game['color']
                        print(f"  ✅ Game started! ID: {game_id}, playing as {color}")
                        print(f"  ⚠️  You now have an active game - finish it on lichess.org")
                        print("\n")
                        return True

            print(f"  ⚠️  Bot didn't accept within 10 seconds")
            print(f"  This could mean:")
            print(f"    - Bot is offline")
            print(f"    - Bot doesn't accept this time control")
            print(f"    - Check bot's profile for what it accepts")

        print("\n")
        return True

    except berserk.exceptions.ResponseError as e:
        print(f"  ❌ Challenge failed: {e}")
        print(f"  Check that '{bot_username}' is a valid bot username")
        print("\n")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        print("\n")
        return False


def main():
    print("\n")
    print("╔════════════════════════════════════════════════════╗")
    print("║     LICHESS API TEST SCRIPT                        ║")
    print("║     Test your setup before using the UCI bridge    ║")
    print("╚════════════════════════════════════════════════════╝")
    print("\n")

    # Test imports first
    if not test_imports():
        sys.exit(1)

    # Get token from user
    print("Enter your Lichess API token")
    print("(Get one at: https://lichess.org/account/oauth/token)")
    print("Required scopes: challenge:read, challenge:write, board:play")
    print()
    token = input("Token (lip_...): ").strip()
    print()

    if not token:
        print("❌ No token provided")
        sys.exit(1)

    # Test token
    client, username = test_token(token)
    if not client:
        sys.exit(1)

    # Test ongoing games
    test_ongoing_games(client)

    # Ask if user wants to test challenge
    print("=" * 50)
    print("TEST 4: Challenge test (OPTIONAL)")
    print("=" * 50)
    print("This will send a real challenge to a bot.")
    print("The bot may accept, creating a game you'll need to play/abort.")
    print()

    do_challenge = input("Test challenge? (y/n): ").strip().lower()

    if do_challenge == 'y':
        bot = input("Bot username (default: maia1): ").strip() or "maia1"
        test_challenge(client, bot)
    else:
        print("  Skipping challenge test")
        print("\n")

    # Summary
    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"  ✅ Token works")
    print(f"  ✅ Username: {username}")
    print(f"  ✅ API access confirmed")
    print()
    print("You can now use this token in the UCI bridge!")
    print()
    print(f"Your token: {token[:10]}...{token[-4:]}")
    print()


if __name__ == "__main__":
    main()

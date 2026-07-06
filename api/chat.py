"""
api/chat.py
Interactive CLI chat interface for the AI Clone Engine.

Can also be imported and used programmatically:
    from api.chat import ChatSession
    session = ChatSession()
    print(session.send("Hello!"))
"""

from __future__ import annotations

import sys

from engine.core import CloneEngine

_BANNER = r"""
 ██████╗██╗      ██████╗ ███╗   ██╗███████╗
██╔════╝██║     ██╔═══██╗████╗  ██║██╔════╝
██║     ██║     ██║   ██║██╔██╗ ██║█████╗
██║     ██║     ██║   ██║██║╚██╗██║██╔══╝
╚██████╗███████╗╚██████╔╝██║ ╚████║███████╗
 ╚═════╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝

 AI Clone Engine of Charles-Earl-Lipshay
 lippytm · lippytmai · v2.0
 Type  /help  for commands,  /quit  to exit.
"""

_HELP = """
Commands:
  /help      Show this help message
  /profile   Display the active personality profile
  /reset     Clear current session memory
  /quit      Exit the chat
"""


class ChatSession:
    """
    Programmatic chat session wrapper.

    Parameters
    ----------
    session_id: Unique session name (used for persistent memory).
    """

    def __init__(self, session_id: str = "default") -> None:
        self.engine = CloneEngine(session_id=session_id)

    def send(self, message: str) -> str:
        """Send a message and return the engine's response."""
        return self.engine.chat(message)

    def reset(self) -> None:
        self.engine.reset()

    def profile(self) -> str:
        return self.engine.profile_summary()


def run_interactive(session_id: str = "default") -> None:
    """Launch the interactive CLI chat loop."""
    session = ChatSession(session_id=session_id)
    print(_BANNER)
    print(f"Session: {session_id}\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Engine] Goodbye. Stay curious.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("/quit", "/exit", "/q"):
            print("[Engine] Goodbye. Stay curious.")
            break
        elif user_input.lower() == "/help":
            print(_HELP)
            continue
        elif user_input.lower() == "/profile":
            print(session.profile())
            continue
        elif user_input.lower() == "/reset":
            session.reset()
            print("[Engine] Session memory cleared.")
            continue

        response = session.send(user_input)
        print(f"\nlippytmai: {response}\n")

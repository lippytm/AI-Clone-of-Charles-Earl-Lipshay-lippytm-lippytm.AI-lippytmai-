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

 AI Clone Engine of Charles-Earl-Lipshay  v3.0
 lippytm · lippytmai
 Type  /help  for commands,  /quit  to exit.
"""

_HELP = """
Commands:
  /help      Show this help message
  /profile   Display the active personality profile
  /reset     Clear current session memory
  /health    Show Self-Healing System health report
  /improve   Show Self-Improvement System report
  /perf      Show Performance Monitor report
  /toolkit   Show AI Toolkit usage report
  /sandbox <code>  Execute Python code in the AI Sandbox
  /rate <0-10>     Rate the last response (0–10 scale)
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

    def health(self) -> str:
        return self.engine.health_report()

    def improve(self) -> str:
        return self.engine.improvement_report()

    def perf(self) -> str:
        return self.engine.performance_report()

    def toolkit(self) -> str:
        return self.engine.toolkit_report()

    def sandbox(self, code: str) -> str:
        result = self.engine.sandbox.execute(code)
        lines = [f"[Sandbox] {'✓ OK' if result.success else '✗ FAILED'}  ({result.elapsed_ms:.1f} ms)"]
        if result.stdout:
            lines.append(f"stdout:\n{result.stdout.rstrip()}")
        if result.stderr:
            lines.append(f"stderr:\n{result.stderr.rstrip()}")
        if result.error:
            lines.append(f"error: {result.error}")
        if result.return_value is not None:
            lines.append(f"_result: {result.return_value!r}")
        return "\n".join(lines)

    def rate_last(self, score_str: str) -> str:
        try:
            score = float(score_str.strip()) / 10.0
            self.engine.self_improvement.rate_last(score)
            return f"[Engine] Last response rated {float(score_str.strip()):.1f}/10 ({score:.2f}). Thank you!"
        except ValueError:
            return "[Engine] Invalid rating — use a number between 0 and 10."


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
        elif user_input.lower() == "/health":
            print(session.health())
            continue
        elif user_input.lower() == "/improve":
            print(session.improve())
            continue
        elif user_input.lower() == "/perf":
            print(session.perf())
            continue
        elif user_input.lower() == "/toolkit":
            print(session.toolkit())
            continue
        elif user_input.lower().startswith("/sandbox "):
            code = user_input[len("/sandbox "):].strip()
            print(session.sandbox(code))
            continue
        elif user_input.lower().startswith("/rate "):
            score_str = user_input[len("/rate "):].strip()
            print(session.rate_last(score_str))
            continue

        response = session.send(user_input)
        print(f"\nlippytmai: {response}\n")

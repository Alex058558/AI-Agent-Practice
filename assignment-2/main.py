import os

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion

from agent import ReActAgent


# Pre-defined tasks from the assignment
TASKS = {
    "1": "What fraction of Japan's population is Taiwan's population as of 2025?",
    "2": "Compare the main display specs of iPhone 15 and Samsung S24.",
    "3": "Who is the CEO of the startup 'Morphic' AI search?",
}

SLASH_COMMANDS = {
    "/help": "Show available commands",
    "/clear": "Reset the agent",
    "/run": "Run a preset task: /run 1, /run 2, /run 3",
    "/tasks": "Show all preset tasks",
    "/exit": "Exit the program",
}


class SlashCommandCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()
        if not text.startswith("/"):
            return

        parts = text.split(maxsplit=1)

        # Complete /run with task numbers
        if len(parts) >= 1 and parts[0] == "/run" and (len(parts) == 2 or text.endswith(" ")):
            arg = parts[1] if len(parts) == 2 else ""
            for num, desc in TASKS.items():
                if num.startswith(arg):
                    yield Completion(num, start_position=-len(arg), display=f"{num} - {desc[:50]}")
            return

        for cmd in SLASH_COMMANDS:
            if cmd.startswith(text) or text in cmd:
                yield Completion(cmd, start_position=-len(text), display=f"{cmd:10} {SLASH_COMMANDS[cmd]}")


# ANSI color helpers
def dim(text):
    return f"\033[2m{text}\033[0m"

def cyan(text):
    return f"\033[36m{text}\033[0m"

def yellow(text):
    return f"\033[33m{text}\033[0m"

def green(text):
    return f"\033[32m{text}\033[0m"

def red(text):
    return f"\033[31m{text}\033[0m"

def bold(text):
    return f"\033[1m{text}\033[0m"


def step_callback(step_type, content):
    """Print each ReAct step with color coding."""
    if step_type == "iteration":
        print(f"\n{dim(content)}")
    elif step_type == "thought":
        print(f"  {cyan(content)}")
    elif step_type == "action":
        print(f"  {yellow('Action: ' + content)}")
    elif step_type == "observation":
        # Truncate long observations for readability
        lines = content.split("\n")
        preview = "\n    ".join(lines[:8])
        if len(lines) > 8:
            preview += f"\n    {dim(f'... ({len(lines) - 8} more lines)')}"
        print(f"  {dim('Observation:')}\n    {preview}")
    elif step_type == "answer":
        print(f"\n{green(bold('Answer:'))} {content}")
    elif step_type == "error":
        print(f"  {red('[!] ' + content)}")


def handle_help():
    print("\n[Available Commands]")
    print("-" * 50)
    for cmd, desc in SLASH_COMMANDS.items():
        print(f"  {cmd:10} {desc}")
    print("-" * 50)
    print("\n  Or type any question to ask the agent directly.")


def handle_tasks():
    print("\n[Preset Tasks]")
    print("-" * 50)
    for num, desc in TASKS.items():
        print(f"  Task {num}: {desc}")
    print("-" * 50)


def main():
    agent = ReActAgent(on_step=step_callback)
    completer = SlashCommandCompleter()

    print("=" * 50)
    print("  ReAct Agent - Assignment 2")
    print("  Type '/' for commands, '/help' for help")
    print("=" * 50)

    while True:
        try:
            user_input = prompt(
                "\nYou: ",
                completer=completer,
                complete_while_typing=True,
            ).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            break

        if not user_input:
            continue

        # Legacy exit
        if user_input.lower() in ("exit", "quit", "bye"):
            print("\nBye!")
            break

        # Slash commands
        if user_input.startswith("/"):
            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""

            if cmd == "/exit":
                print("\nBye!")
                break
            elif cmd == "/help":
                handle_help()
            elif cmd == "/clear":
                agent = ReActAgent(on_step=step_callback)
                print("\n[System] Agent reset.")
            elif cmd == "/tasks":
                handle_tasks()
            elif cmd == "/run":
                if arg not in TASKS:
                    print(f"\n[Error] Invalid task number: '{arg}'")
                    print(f"  Available: {', '.join(TASKS.keys())}")
                    continue
                question = TASKS[arg]
                print(f"\n{bold(f'[Task {arg}]')} {question}")
                answer = agent.run(question)
            else:
                print(f"\n[Error] Unknown command: {cmd}")
                print("  Type /help for available commands.")
            continue

        # Free-form question
        agent.run(user_input)


if __name__ == "__main__":
    main()

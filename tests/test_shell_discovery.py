from app.process.discovery import find_shell_processes


shells = find_shell_processes()


print("Shell processes:")

for session in shells:

    print(
        f"PID={session.pid} "
        f"COMMAND={session.command} "
        f"TTY={session.tty} "
        f"CWD={session.cwd}"
    )

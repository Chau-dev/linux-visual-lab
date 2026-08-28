from app.process.focused_session import FocusedSession


focused = FocusedSession()

print("Initially:", focused.pid)

focused.set_pid(8798)

print("Selected:", focused.pid)

focused.clear()

print("After clear:", focused.pid)

"""
SmartPlate Browser Launcher
Starts Flask server and automatically opens http://127.0.0.1:5000 in default browser.
"""

import socket
import sys
import threading
import time
import webbrowser


def is_port_in_use(port=5000):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def open_browser():
    time.sleep(1.2)
    print("\n[SmartPlate] Opening http://127.0.0.1:5000 in your web browser...")
    webbrowser.open("http://127.0.0.1:5000")


def print_banner():
    print("=" * 65)
    print("   PCCOE SmartPlate: Campus Canteen Sustainability System")
    print("=" * 65)
    print(" > Web Application URL : http://127.0.0.1:5000")
    print(" > DT FA2 Exam Poster   : http://127.0.0.1:5000/poster")
    print(" > Login Credentials:")
    print("   - Admin & Canteen Ops : admin@pccoe.edu / admin1234")
    print("   - Student Sign-Up     : http://127.0.0.1:5000/register")
    print("=" * 65)


if __name__ == "__main__":
    print_banner()

    if is_port_in_use(5000):
        print(" > Note: SmartPlate server is already running on port 5000.")
        print(" > Opening http://127.0.0.1:5000 in your browser now...")
        webbrowser.open("http://127.0.0.1:5000")
        print("\nPress Enter to close this launcher window...")
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            pass
        sys.exit(0)

    from app import app

    threading.Thread(target=open_browser, daemon=True).start()
    print(" > Press Ctrl+C in this window to stop the server.")
    print("=" * 65)
    app.run(host="127.0.0.1", port=5000, debug=False)

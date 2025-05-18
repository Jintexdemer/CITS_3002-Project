"""
client.py

Connects to a Battleship server which runs the single-player game.
Simply pipes user input to the server, and prints all server responses.

TODO: Fix the message synchronization issue using concurrency (Tier 1, item 1).
"""

import socket
import threading

HOST = '127.0.0.1'
PORT = 50043

running = True  # Flag to control thread loop


def receive_messages(rfile):
    """Continuously receive and display messages from the server."""
    while running:
        try:
            line = rfile.readline()
            if not line:
                print("[INFO] Server disconnected.")
                break

            line = line.strip()

            if line == "GRID":
                print("\n[Board]")
                while True:
                    board_line = rfile.readline()
                    if not board_line or board_line.strip() == "":
                        break
                    print(board_line.strip())
            else:
                print(line)
                
        except Exception as e:
            print(f"[ERROR] Exception in receiving messages: {e}")
            break


def main():
    global running
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        rfile = s.makefile('r')
        wfile = s.makefile('w')

        # Start receiver thread
        receiver_thread = threading.Thread(target=receive_messages, args=(rfile,), daemon=True)
        receiver_thread.start()

        try:
            while True:
                user_input = input(">> ")
                wfile.write(user_input + '\n')
                wfile.flush()
        except KeyboardInterrupt:
            print("\n[INFO] Client exiting.")
        finally:
            running = False  # Signal the receiver thread to stop


if __name__ == "__main__":
    main()
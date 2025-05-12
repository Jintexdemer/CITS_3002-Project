"""
server.py

Serves a single-player Battleship session to one connected client.
Game logic is handled entirely on the server using battleship.py.
Client sends FIRE commands, and receives game feedback.

TODO: For Tier 1, item 1, you don't need to modify this file much. 
The core issue is in how the client handles incoming messages.
However, if you want to support multiple clients (i.e. progress through further Tiers), you'll need concurrency here too.
"""

import socket
import threading
from battleship import run_two_player_game_online  # You’ll write this


HOST = '127.0.0.1'
PORT = 50007

def main():
    print(f"[INFO] Server listening on {HOST}:{PORT}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen(2)
        clients = []
        while len(clients) < 2:
            conn, addr = s.accept()
            print(f"[INFO] Client connected from {addr}")
            rfile = conn.makefile('r')
            wfile = conn.makefile('w')
            clients.append((conn, rfile, wfile))
            wfile.write("Waiting for another player to join...\n")
            wfile.flush()
        
        threading.Thread(target=run_two_player_game_online, args=(clients[0], clients[1])).start()

# HINT: For multiple clients, you'd need to:
# 1. Accept connections in a loop
# 2. Handle each client in a separate thread
# 3. Import threading and create a handle_client function

if __name__ == "__main__":
    main()
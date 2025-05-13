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
from battleship import run_two_player_game_online 
from queue import Queue

HOST = '127.0.0.1'
PORT = 50021

game = threading.Event()

input_1 = threading.Event()
input_2 = threading.Event()
player_Status = [input_1,input_2]
players = []
spectators = []

def handle_client(rfile, wfile, player): #input[0], input[1], input[2]|| status, input_queue, id
    print(f"[INFO] Handling {player[2]}")
    try:
        while True:
            line = rfile.readline()
            if not line:
                break
            if player[0].is_set():
                player[1].put(line.strip())
            elif not game.is_set():
                wfile.write("Waiting for player 2\n")
                wfile.flush()
            else:
                wfile.write("Ignored input.\n")
                wfile.flush()
    except Exception as e:
        print(f"[ERROR] {player[2]} unknown player connection error: {player[1]} \n {e}")
    finally:
        game.clear()
        if len(players) > 1:
            print(f"[INFO] PLAYER DISCONNECTED {player[2]} ")
            if players[1][0][0].is_set():
                players[1][0][1].put(" ")
            if players[0][0][0].is_set():
                players[0][0][1].put(" ")
            players.pop(player[2])
            players[0][1].write(f"Player {player[2]+1} forfeits the match\n")
            players[0][1].flush()
            players[0][0][0] = player_Status[0]
            players[0][0][2] = 0
        else:
            players.pop()
        player_Status[0].clear
        player_Status[1].clear


def main():
    print(f"[INFO] Server listening on {HOST}:{PORT}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen(8)
        while True:
                conn, addr = s.accept()
                print(f"[INFO] Client connected from {addr}")
                rfile = conn.makefile('r')
                wfile = conn.makefile('w')
                if len(players) < 2:
                    input = [player_Status[len(players)], Queue(), len(players)]  #[Player's status, input queue, id]
                    players.append((input, wfile))
                    threading.Thread(target=handle_client, args=(rfile, wfile, players[len(players)-1][0]), daemon=True).start() #input[0], input[1], input[2]
                    if len(players) < 2:
                        wfile.write("Waiting for another player to join...\n")
                        wfile.flush()
                    else:
                        game.set()
                        threading.Thread(target=run_two_player_game_online, args=(game, players[0], players[1])).start()
                else:
                    spectators.append((rfile, wfile))
                    wfile.write("The current Game is full.\n")
                    wfile.flush()
            
        

if __name__ == "__main__":
    main()
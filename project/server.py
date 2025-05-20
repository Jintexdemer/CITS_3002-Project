"""
NEED TO ADD:
RECONNECT FUNCTIONAILTY
COMMENTS
"""


import socket
import threading
from queue import Queue
from battleship import run_two_player_game_online
import time

HOST = '127.0.0.1'
PORT = 50045

disconnected_players = []
RECONNECT_TIMEOUT = 60

# Game state flags
new_game = threading.Event()
game_active = threading.Event()

# Input control flags: [spec, player1, player2]
input_status_flags = [threading.Event(), threading.Event(), threading.Event()]

clients = []  # List of all client dicts
id_queue = Queue()

# Player slots
player1 = None
player2 = None

client_id_counter = 0

def spectator_announcer():
    while True:
        time.sleep(15)
        if not game_active.is_set():
            continue

        # Clean invalid IDs from queue
        while not id_queue.empty():
            id_list = list(id_queue.queue)
            valid_ids = [c['client_id'] for c in clients]
            if id_list[0] not in valid_ids:
                id_queue.get()  # remove invalid client
            else:
                break  # first one is valid, continue

        id_list = list(id_queue.queue)
        next1 = next2 = None

        # Determine next players
        if len(id_list) >= 2:
            cid1, cid2 = id_list[0], id_list[1]
        elif len(id_list) == 1:
            cid1 = id_list[0]
            cid2 = player2['client_id'] if player2 else None
        else:
            cid1 = player1['client_id'] if player1 else None
            cid2 = player2['client_id'] if player2 else None

        # Get usernames
        for c in clients:
            if c['client_id'] == cid1:
                next1 = c['username']
            if c['client_id'] == cid2:
                next2 = c['username']

        # If still missing info, skip this cycle
        if not next1 or not next2:
            continue

        msg = f"[INFO] After actve game ends: Next game will be between: {next1} and {next2}\n"

        # Send to all spectators
        for c in clients:
            if c['p'] == 0:
                try:
                    c['wfile'].write(msg)
                    c['wfile'].flush()
                except:
                    continue


def handle_client(client_info):
    rfile = client_info['rfile']
    wfile = client_info['wfile']
    client_id = client_info['client_id']

    print(f"[INFO] Handling client {client_id}")

    try:
        while True:
            line = rfile.readline()
            if not line:
                break
            line = line.strip()

            if client_info['p'] == 0:
                wfile.write("You are spectating.\n")
                wfile.flush()
            elif not game_active.is_set():
                wfile.write("Waiting for players to join...\n")
                wfile.flush()
            elif client_info['input_flag'].is_set():
                client_info['input_queue'].put(line)
            else:
                wfile.write("You cannot input right now.\n")
                wfile.flush()

    except (socket.timeout, ConnectionResetError, BrokenPipeError) as e:
        print(f"[ERROR] Client {client_id} disconnected or error: {e}")
    except Exception as e:
        print(f"[ERROR] Unexpected error with client {client_id}: {e}")
    finally:
        cleanup_disconnect(client_info)



def cleanup_disconnect(client_info):
    global player1, player2

    print(f"[INFO] Cleaning up client {client_info['client_id']}")

    # Remove client from clients list
    if client_info in clients:
        clients.remove(client_info)

    # If not a player, nothing more to do
    if client_info['p'] not in [1, 2]:
        return

    print(f"[INFO] Client was a player")

    if game_active.is_set():
        # Game is active — must kill the game safely
        print(f"[INFO] Game is active — force ending")

        game_active.clear()  # Immediately end game logic
        

        # Clean up both players
        for player in [player1, player2]:
            if player:
                # Clear input queue
                try:
                    while not player['input_queue'].empty():
                        player['input_queue'].get_nowait()
                except:
                    pass

                # Queue dummy input to unblock .get()
                try:
                    player['input_queue'].put("__DISCONNECTED__")
                except:
                    pass

                # Force input flag so any .wait() is released
                try:
                    player['input_flag'].set()
                except:
                    pass

        # Notify the other player (if they exist and aren't the one disconnecting)
        other = player1 if client_info['p'] == 2 else player2
        if other and other != client_info:
            try:
                other['wfile'].write("Opponent has disconnected. You win!\n")
                other['wfile'].flush()
            except:
                pass

    else:
        # Game is not running, just clear disconnecting player's queue
        print(f"[INFO] No active game — clearing input queue only")
        try:
            while not client_info['input_queue'].empty():
                client_info['input_queue'].get_nowait()
        except:
            pass
    # Always try to close connection
    try:
        client_info['conn'].close()
    except:
        pass

    # Remove from player1/player2
    if client_info['p'] == 1:
        player1 = None
    elif client_info['p'] == 2:
        player2 = None

def lobby_manager():
    global player1, player2
    while True:
        if player1 is None and not id_queue.empty()  and new_game.is_set():
            print(f"[INFO] Player 1 added")
            print(f"{list(id_queue.queue)}")
            client_id = id_queue.get()
            print(f"{client_id}")
            client = next((c for c in clients if c['client_id'] == client_id), None)
            if client is None:
                print(f"[WARN] Skipping missing client_id: {client_id}")
                continue 
            client['p'] = 1
            client['input_flag'] = input_status_flags[1]
            client['input_queue'].empty()
            player1 = client
            continue

        if player2 is None and not id_queue.empty() and new_game.is_set():
            print(f"[INFO] Player 2 added")
            print(f"{list(id_queue.queue)}")
            client_id = id_queue.get()
            print(f"{client_id}")
            client = next((c for c in clients if c['client_id'] == client_id), None)
            if client is None:
                print(f"[WARN] Skipping missing client_id: {client_id}")
                continue 
            client['p'] = 2
            client['input_flag'] = input_status_flags[2]
            client['input_queue'].empty()
            player2 = client
            continue

        if player1 and player2 and new_game.is_set():
            new_game.clear()
            game_active.set()
            print(f"[INFO] Game started")
            run_two_player_game_online(
                game_active,
                (player1, player1['wfile']),
                (player2, player2['wfile']),
                clients
            )
            print(f"[INFO] Game ended")
            # Reset input flags
            input_status_flags[1].clear()
            input_status_flags[2].clear()

            for client in clients:
                client['p'] = 0

            
            # Put players back into the client queue
            if player2 is not None:
                if player2 in clients:
                    id_queue.put(player2['client_id'])
                player2 = None
            
            if player1 is not None:
                if player1 in clients:
                    id_queue.put(player1['client_id'])
                player1 = None

            new_game.set()




def initialize_client(conn, addr):
    global client_id_counter
    print(f"[INFO] Initializing client from {addr}")

    try:
        rfile = conn.makefile('r')
        wfile = conn.makefile('w')

        wfile.write("Enter your username:\n")
        wfile.flush()
        username = rfile.readline().strip()
        p = 0

        client_info = {
            'client_id': client_id_counter,
            'username': username,
            'p': p,
            'input_queue': Queue(),
            'rfile': rfile,
            'wfile': wfile,
            'conn': conn,
            'input_flag': input_status_flags[0],
        }

        clients.append(client_info)
        id_queue.put(client_id_counter)

        wfile.write(f"Welcome, {username}!\n")
        wfile.flush()

        threading.Thread(target=handle_client, args=(client_info,), daemon=True).start()
        client_id_counter += 1

    except Exception as e:
        print(f"[ERROR] Failed to initialize client from {addr}: {e}")
        try:
            conn.close()
        except:
            pass


def main():
    print(f"[INFO] Server starting at {HOST}:{PORT}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind((HOST, PORT))
        server.listen(8)
        new_game.set()
        threading.Thread(target=lobby_manager, daemon=True).start()
        threading.Thread(target=spectator_announcer, daemon=True).start()


        while True:
            try:
                conn, addr = server.accept()
                threading.Thread(target=initialize_client, args=(conn, addr), daemon=True).start()
            except Exception as e:
                print(f"[ERROR] Error accepting new connection: {e}")


if __name__ == '__main__':
    main()







"""
client_id queue()

new_game = threading.Event()
game_active = threading.Event()

input_status_flags = [threading.Event(),threading.Event(), threading.Event()] spec,player1,player2

clients = [id, p, inputQueue]  #p=0 is spec, p=1 is player 1, p=2 is player 2
player1 = [input_status_flags[1], wfile, rfile, inputqueue]
player2 = [input_status_flags[2], wfile, rfile, inputqueue]
"""
















"""
Main

1. set up socket server
2. start lobby thread
3. new game is set
loop->:
get incomming client
add to client list info and to id queue
id += 1
start client handler thread
:<-loop

"""


"""
Client handler

loop->:
watch for input
1. is non player ->( you are spectating )
2. is player but no game ->( waiting for players)
3. is player and matches player input flag -> ( add input to queue)
:<-loop
if they leave then call cleanup and then end this thread
"""


"""
Clean up

remove their client info
if they were player:
    if there is a game ongoing:
        flag game as inactive (this removes inputs)
        clear input queues
        Tell the other player that they won
        turn off the input flag and queue one rubbish input for player if they have an input flag on
        new game flag is active
        # ends game
    else: 
        clear input queue
        remove player info
"""


"""
lobby

loop->:
Is player 1 open:
    copy first in id client queue to player 1
    remove that id from queue
    change the p of the client to 1
    continue
Is player 2 open:
    copy first in id client queue to player 2
    remove that id from queue
    change the p of the client to 2
    continue
if both are full and new game is set:
    new game flag is inactive
    set game flag as active
    run_two_player_game_online(player 1, player 2)
:<-loop
"""



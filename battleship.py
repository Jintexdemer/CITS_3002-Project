"""
battleship.py

Contains core data structures and logic for Battleship, including:
 - Board class for storing ship positions, hits, misses
 - Utility function parse_coordinate for translating e.g. 'B5' -> (row, col)
 - A test harness run_single_player_game() to demonstrate the logic in a local, single-player mode

"""
import time
import random

BOARD_SIZE = 3
SHIPS = [
   #("Carrier", 5),
   #("Battleship", 4),
   #("Cruiser", 3),
   # ("Submarine", 3),
    ("Destroyer", 2)
]

def send(wfile, msg, game):
    time.sleep(0.1)
    if not game.is_set():
        return
    try:
        wfile.write(msg + '\n')
        wfile.flush()
    except (BrokenPipeError, ConnectionResetError) as e:
        print(f"[SEND ERROR] Could not send to client: {e}")

def recv(player_info, game, timeout=30):
    time.sleep(0.1)
    if not game.is_set(): return #Check if game is over
    player_info['input_flag'].set()
    try:
        result = player_info['input_queue'].get(timeout=timeout)
    except Exception:
        # Timeout expired without input
        result = "__TIMEOUT__"
    finally:
        player_info['input_flag'].clear()

    if result in ("__DISCONNECTED__", "__TIMEOUT__"):
        return None  # Treat both as no valid input / disconnect

    return result

def send_board(wfile, board, game):
    time.sleep(0.1)
    if not game.is_set(): return #Check if game is over
    wfile.write("GRID\n")
    wfile.write("  " + " ".join(str(i + 1).rjust(2) for i in range(board.size)) + '\n')
    for r in range(board.size):
        row_label = chr(ord('A') + r)
        row_str = " ".join(board.display_grid[r][c] for c in range(board.size))
        wfile.write(f"{row_label:2} {row_str}\n")
    wfile.write('\n')
    wfile.flush()

class Board:
    """
    Represents a single Battleship board with hidden ships.
    We store:
      - self.hidden_grid: tracks real positions of ships ('S'), hits ('X'), misses ('o')
      - self.display_grid: the version we show to the player ('.' for unknown, 'X' for hits, 'o' for misses)
      - self.placed_ships: a list of dicts, each dict with:
          {
             'name': <ship_name>,
             'positions': set of (r, c),
          }
        used to determine when a specific ship has been fully sunk.

    In a full 2-player networked game:
      - Each player has their own Board instance.
      - When a player fires at their opponent, the server calls
        opponent_board.fire_at(...) and sends back the result.
    """

    def __init__(self, size=BOARD_SIZE):
        self.size = size
        # '.' for empty water
        self.hidden_grid = [['.' for _ in range(size)] for _ in range(size)]
        # display_grid is what the player or an observer sees (no 'S')
        self.display_grid = [['.' for _ in range(size)] for _ in range(size)]
        self.placed_ships = []  # e.g. [{'name': 'Destroyer', 'positions': {(r, c), ...}}, ...]

    def place_ships_randomly(self, ships=SHIPS):
        """
        Randomly place each ship in 'ships' on the hidden_grid, storing positions for each ship.
        In a networked version, you might parse explicit placements from a player's commands
        (e.g. "PLACE A1 H BATTLESHIP") or prompt the user for board coordinates and placement orientations; 
        the self.place_ships_manually() can be used as a guide.
        """
        for ship_name, ship_size in ships:
            placed = False
            while not placed:
                orientation = random.randint(0, 1)  # 0 => horizontal, 1 => vertical
                row = random.randint(0, self.size - 1)
                col = random.randint(0, self.size - 1)

                if self.can_place_ship(row, col, ship_size, orientation):
                    occupied_positions = self.do_place_ship(row, col, ship_size, orientation)
                    self.placed_ships.append({
                        'name': ship_name,
                        'positions': occupied_positions
                    })
                    placed = True

    def place_ships_manually(self, ships=SHIPS):
        """
        Prompt the user for each ship's starting coordinate and orientation (H or V).
        Validates the placement; if invalid, re-prompts.
        """
        print("\nPlease place your ships manually on the board.")
        for ship_name, ship_size in ships:
            while True:
                self.print_display_grid(show_hidden_board=True)
                print(f"\nPlacing your {ship_name} (size {ship_size}).")
                coord_str = input("  Enter starting coordinate (e.g. A1): ").strip()
                orientation_str = input("  Orientation? Enter 'H' (horizontal) or 'V' (vertical): ").strip().upper()

                try:
                    row, col = parse_coordinate(coord_str)
                except ValueError as e:
                    print(f"  [!] Invalid coordinate: {e}")
                    continue

                # Convert orientation_str to 0 (horizontal) or 1 (vertical)
                if orientation_str == 'H':
                    orientation = 0
                elif orientation_str == 'V':
                    orientation = 1
                else:
                    print("  [!] Invalid orientation. Please enter 'H' or 'V'.")
                    continue

                # Check if we can place the ship
                if self.can_place_ship(row, col, ship_size, orientation):
                    occupied_positions = self.do_place_ship(row, col, ship_size, orientation)
                    self.placed_ships.append({
                        'name': ship_name,
                        'positions': occupied_positions
                    })
                    break
                else:
                    print(f"  [!] Cannot place {ship_name} at {coord_str} (orientation={orientation_str}). Try again.")

    def place_ships_manually_online(self, rfile, wfile, game, ships=SHIPS):
        """
        Prompt the user for each ship's starting coordinate and orientation (H or V).
        Validates the placement; if invalid, re-prompts.
        """
        if not game.is_set(): return #Check if game is over
        send(wfile, "\nPlease place your ships manually on the board.", game)
        if not game.is_set(): return #Check if game is over
        for ship_name, ship_size in ships:
            while True:
                self.print_display_grid_online(wfile, game, show_hidden_board=True)
                send(wfile, f"\nPlacing your {ship_name} (size {ship_size}).", game)
                send(wfile, "Enter starting coordinate (e.g. A1): ", game)

                if not game.is_set(): return #Check if game is over
                coord_str = recv(rfile,game)
                if not game.is_set(): return #Check if game is over

                send(wfile, "  Orientation? Enter 'H' (horizontal) or 'V' (vertical): ", game)

                if not game.is_set(): return #Check if game is over
                orientation_str = recv(rfile,game).upper()
                if not game.is_set(): return #Check if game is over

                try:
                    row, col = parse_coordinate(coord_str)
                except ValueError as e:
                    send(wfile, f"  [!] Invalid coordinate: {e}", game)
                    continue

                # Convert orientation_str to 0 (horizontal) or 1 (vertical)
                if orientation_str == 'H':
                    orientation = 0
                elif orientation_str == 'V':
                    orientation = 1
                else:
                    send(wfile, "  [!] Invalid orientation. Please enter 'H' or 'V'.", game)
                    continue

                # Check if we can place the ship
                if self.can_place_ship(row, col, ship_size, orientation):
                    occupied_positions = self.do_place_ship(row, col, ship_size, orientation)
                    self.placed_ships.append({
                        'name': ship_name,
                        'positions': occupied_positions
                    })
                    break
                else:
                    send(wfile, f"  [!] Cannot place {ship_name} at {coord_str} (orientation={orientation_str}). Try again.", game)


    def can_place_ship(self, row, col, ship_size, orientation):
        """
        Check if we can place a ship of length 'ship_size' at (row, col)
        with the given orientation (0 => horizontal, 1 => vertical).
        Returns True if the space is free, False otherwise.
        """
        if orientation == 0:  # Horizontal
            if col + ship_size > self.size:
                return False
            for c in range(col, col + ship_size):
                if self.hidden_grid[row][c] != '.':
                    return False
        else:  # Vertical
            if row + ship_size > self.size:
                return False
            for r in range(row, row + ship_size):
                if self.hidden_grid[r][col] != '.':
                    return False
        return True

    def do_place_ship(self, row, col, ship_size, orientation):
        """
        Place the ship on hidden_grid by marking 'S', and return the set of occupied positions.
        """
        occupied = set()
        if orientation == 0:  # Horizontal
            for c in range(col, col + ship_size):
                self.hidden_grid[row][c] = 'S'
                occupied.add((row, c))
        else:  # Vertical
            for r in range(row, row + ship_size):
                self.hidden_grid[r][col] = 'S'
                occupied.add((r, col))
        return occupied

    def fire_at(self, row, col):
        """
        Fire at (row, col). Return a tuple (result, sunk_ship_name).
        Possible outcomes:
          - ('hit', None)          if it's a hit but not sunk
          - ('hit', <ship_name>)   if that shot causes the entire ship to sink
          - ('miss', None)         if no ship was there
          - ('already_shot', None) if that cell was already revealed as 'X' or 'o'

        The server can use this result to inform the firing player.
        """
        cell = self.hidden_grid[row][col]
        if cell == 'S':
            # Mark a hit
            self.hidden_grid[row][col] = 'X'
            self.display_grid[row][col] = 'X'
            # Check if that hit sank a ship
            sunk_ship_name = self._mark_hit_and_check_sunk(row, col)
            if sunk_ship_name:
                return ('hit', sunk_ship_name)  # A ship has just been sunk
            else:
                return ('hit', None)
        elif cell == '.':
            # Mark a miss
            self.hidden_grid[row][col] = 'o'
            self.display_grid[row][col] = 'o'
            return ('miss', None)
        elif cell == 'X' or cell == 'o':
            return ('already_shot', None)
        else:
            # In principle, this branch shouldn't happen if 'S', '.', 'X', 'o' are all possibilities
            return ('already_shot', None)

    def _mark_hit_and_check_sunk(self, row, col):
        """
        Remove (row, col) from the relevant ship's positions.
        If that ship's positions become empty, return the ship name (it's sunk).
        Otherwise return None.
        """
        for ship in self.placed_ships:
            if (row, col) in ship['positions']:
                ship['positions'].remove((row, col))
                if len(ship['positions']) == 0:
                    return ship['name']
                break
        return None

    def all_ships_sunk(self):
        """
        Check if all ships are sunk (i.e. every ship's positions are empty).
        """
        for ship in self.placed_ships:
            if len(ship['positions']) > 0:
                return False
        return True

    def print_display_grid(self, show_hidden_board=False):
        """
        Print the board as a 2D grid.
        
        If show_hidden_board is False (default), it prints the 'attacker' or 'observer' view:
        - '.' for unknown cells,
        - 'X' for known hits,
        - 'o' for known misses.
        
        If show_hidden_board is True, it prints the entire hidden grid:
        - 'S' for ships,
        - 'X' for hits,
        - 'o' for misses,
        - '.' for empty water.
        """
        # Decide which grid to print
        grid_to_print = self.hidden_grid if show_hidden_board else self.display_grid

        # Column headers (1 .. N)
        print("  " + "".join(str(i + 1).rjust(2) for i in range(self.size)))
        # Each row labeled with A, B, C, ...
        for r in range(self.size):
            row_label = chr(ord('A') + r)
            row_str = " ".join(grid_to_print[r][c] for c in range(self.size))
            print(f"{row_label:2} {row_str}")
    
    def print_display_grid_online(self, wfile, game, show_hidden_board=False):
        """
        Print the board as a 2D grid.
        
        If show_hidden_board is False (default), it prints the 'attacker' or 'observer' view:
        - '.' for unknown cells,
        - 'X' for known hits,
        - 'o' for known misses.
        
        If show_hidden_board is True, it prints the entire hidden grid:
        - 'S' for ships,
        - 'X' for hits,
        - 'o' for misses,
        - '.' for empty water.
        """
        # Decide which grid to print
        grid_to_print = self.hidden_grid if show_hidden_board else self.display_grid

        # Column headers (1 .. N)
        send(wfile, "  " + "".join(str(i + 1).rjust(2) for i in range(self.size)), game)
        # Each row labeled with A, B, C, ...
        for r in range(self.size):
            row_label = chr(ord('A') + r)
            row_str = " ".join(grid_to_print[r][c] for c in range(self.size))
            send(wfile, f"{row_label:2} {row_str}",game)


def parse_coordinate(coord_str):
    coord_str = coord_str.strip().upper()
    if len(coord_str) < 2:
        raise ValueError("Coordinate too short.")

    row_letter = coord_str[0]
    if (not row_letter.isalpha() or not 'A' <= row_letter <= chr(ord('A') + BOARD_SIZE - 1)):
        raise ValueError(f"Invalid row letter: {row_letter}")

    col_digits = coord_str[1:]
    if (not col_digits.isdigit() ):
        raise ValueError(f"Invalid column number: {col_digits}")

    row = ord(row_letter) - ord('A')
    col = int(col_digits) - 1

    if not (0 <= col < BOARD_SIZE):
        raise ValueError(f"Column out of bounds: {col + 1}")

    return (row, col)

def run_two_player_game_online(game, p1, p2):
    
    rfile1, wfile1 = p1
    rfile2, wfile2 = p2 

    if not game.is_set(): return #Check if game is over
    send(wfile1, "You are Player 1.", game)
    if not game.is_set(): return #Check if game is over
    send(wfile2, "You are Player 2.", game)
    if not game.is_set(): return #Check if game is over

    board1 = Board(BOARD_SIZE)
    board2 = Board(BOARD_SIZE)

    #Place ships.
    if not game.is_set(): return #Check if game is over
    send(wfile2, "Wait for Player 1 to place their ships...", game)
    if not game.is_set(): return #Check if game is over
    send(wfile1, "Place ships manually (M) or randomly (R)? [M/R]: ", game)
    if not game.is_set(): return #Check if game is over
    while True:
        
        if not game.is_set(): return #Check if game is over
        Place = recv(rfile1,game).upper()
        if not game.is_set(): return #Check if game is over

        if Place == 'M':
            board1.place_ships_manually_online(rfile1, wfile1, game, SHIPS)
            break
        elif Place == 'R':
            board1.place_ships_randomly(SHIPS)
            break
        else:
            if not game.is_set(): return #Check if game is over
            send(wfile1, "Invalid input", game)
            if not game.is_set(): return #Check if game is over
    
    if not game.is_set(): return
    send(wfile1, "Wait for Player 2 to place their ships...", game)
    if not game.is_set(): return #Check if game is over
    send(wfile2, "Place ships manually (M) or randomly (R)? [M/R]: ", game)
    if not game.is_set(): return #Check if game is over
    while True:

        if not game.is_set(): return #Check if game is over
        Place = recv(rfile2,game).upper()
        if not game.is_set(): return #Check if game is over

        if Place == 'M':
            board2.place_ships_manually_online(rfile2, wfile2, game, SHIPS)
            break
        elif Place == 'R':
            board2.place_ships_randomly(SHIPS)
            break
        else:
            if not game.is_set(): return #Check if game is over
            send(wfile2, "Invalid input", game)
            if not game.is_set(): return #Check if game is over

    if not game.is_set(): return #Check if game is over
    send(wfile1, "Welcome to Online Single-Player Battleship! Try to sink all the ships. Type 'quit' to exit.", game)
    if not game.is_set(): return #Check if game is over
    send(wfile2, "Welcome to Online Single-Player Battleship! Try to sink all the ships. Type 'quit' to exit.", game)
    if not game.is_set(): return #Check if game is over

    moves = 0

    while True:
        if not game.is_set(): return #Check if game is over

        # Player 1 turn
        if not game.is_set(): return #Check if game is over
        send_board(wfile1, board2, game)
        if not game.is_set(): return #Check if game is over
        send(wfile2, "Wait for player 1 turn...", game)
        if not game.is_set(): return #Check if game is over
        send(wfile1, "Enter coordinate to fire at (e.g. B5):", game)

        if not game.is_set(): return #Check if game is over
        guess = recv(rfile1,game)
        if not game.is_set(): return #Check if game is over
        
        send(wfile2, f"Player 1 Inputs: {guess}", game)
        if not game.is_set(): return #Check if game is over
        if guess.lower() == 'quit':
            if not game.is_set(): return #Check if game is over
            send(wfile1, "Thanks for playing. Goodbye.", game)
            if not game.is_set(): return #Check if game is over
            send(wfile2, "Player 1 quit the game.", game)
            if not game.is_set(): return #Check if game is over
            game.clear()
            return

        try:
            row, col = parse_coordinate(guess)
            result, sunk_name = board2.fire_at(row, col)
            moves += 1

            if result == 'hit':
                if sunk_name:
                    if not game.is_set(): return #Check if game is over
                    send(wfile1, f"HIT! You sank the {sunk_name}!", game)
                    if not game.is_set(): return #Check if game is over
                    send(wfile2, f"HIT! Player 1 sank the {sunk_name}!", game)
                    if not game.is_set(): return #Check if game is over
                else:
                    if not game.is_set(): return #Check if game is over
                    send(wfile1, "HIT!")
                    if not game.is_set(): return #Check if game is over
                    send(wfile2, "Player 1: HIT!")
                    if not game.is_set(): return #Check if game is over
                if board2.all_ships_sunk():
                    if not game.is_set(): return #Check if game is over
                    send_board(wfile1, board2, game)
                    if not game.is_set(): return #Check if game is over
                    send_board(wfile2, board2, game)
                    if not game.is_set(): return #Check if game is over
                    send(wfile1, f"Congratulations! You sank all ships in {moves} moves.", game)
                    if not game.is_set(): return #Check if game is over
                    send(wfile2, f"You lose! Player 2 sank all ships in {moves} moves.", game)
                    if not game.is_set(): return #Check if game is over
                    game.clear()
                    return
            elif result == 'miss':
                    if not game.is_set(): return #Check if game is over
                    send(wfile1, "MISS!", game)
                    if not game.is_set(): return #Check if game is over
                    send(wfile2, "Player 1: MISS!", game)
                    if not game.is_set(): return #Check if game is over
            elif result == 'already_shot':
                if not game.is_set(): return #Check if game is over
                send(wfile1, "You've already fired at that location.", game)
                if not game.is_set(): return #Check if game is over
                send(wfile2, "Player 1: You've already fired at that location.", game)
                if not game.is_set(): return #Check if game is over
        except ValueError as e:
            if not game.is_set(): return #Check if game is over
            send(wfile1, f"Invalid input: {e}",game)
            if not game.is_set(): return #Check if game is over

        # Player 2 turn
        if not game.is_set(): return #Check if game is over
        send_board(wfile2, board1)
        if not game.is_set(): return #Check if game is over
        send(wfile1, "Wait for player 2 turn...", game)
        if not game.is_set(): return #Check if game is over
        send(wfile2, "Enter coordinate to fire at (e.g. B5):", game)
        if not game.is_set(): return #Check if game is over

        if not game.is_set(): return #Check if game is over
        guess = recv(rfile2,game)
        if not game.is_set(): return #Check if game is over

        send(wfile1, f"Player 2 Inputs: {guess}", game)
        if not game.is_set(): return #Check if game is over
        if guess.lower() == 'quit':
            if not game.is_set(): return #Check if game is over
            send(wfile2, "Thanks for playing. Goodbye.", game)
            if not game.is_set(): return #Check if game is over
            send(wfile1, "Player 2 quit the game.", game)
            if not game.is_set(): return #Check if game is over
            return
        
        try:
            row, col = parse_coordinate(guess)
            result, sunk_name = board1.fire_at(row, col)

            if result == 'hit':
                if sunk_name:
                    if not game.is_set(): return #Check if game is over
                    send(wfile2, f"HIT! You sank the {sunk_name}!", game)
                    if not game.is_set(): return #Check if game is over
                    send(wfile1, f"HIT! Player 2 sank the {sunk_name}!", game)
                    if not game.is_set(): return #Check if game is over
                else:
                    if not game.is_set(): return #Check if game is over
                    send(wfile2, "HIT!", game)
                    if not game.is_set(): return #Check if game is over
                    send(wfile1, "Player 2: HIT!", game)
                    if not game.is_set(): return #Check if game is over
                if board1.all_ships_sunk():
                    if not game.is_set(): return #Check if game is over
                    send_board(wfile2, board1, game)
                    if not game.is_set(): return #Check if game is over
                    send_board(wfile1, board1, game)
                    if not game.is_set(): return #Check if game is over
                    send(wfile2, f"Congratulations! You sank all ships in {moves} moves.", game)
                    if not game.is_set(): return #Check if game is over
                    send(wfile1, f"You lose! Player 1 sank all ships in {moves} moves.", game)
                    game.clear()
                    return
            elif result == 'miss':
                    if not game.is_set(): return #Check if game is over
                    send(wfile2, "MISS!", game)
                    if not game.is_set(): return #Check if game is over
                    send(wfile1, "Player 2: MISS!", game)
                    if not game.is_set(): return #Check if game is over
            elif result == 'already_shot':
                if not game.is_set(): return #Check if game is over
                send(wfile2, "You've already fired at that location.", game)
                if not game.is_set(): return #Check if game is over
                send(wfile1, "Player 2: You've already fired at that location.", game)
                if not game.is_set(): return #Check if game is over
        except ValueError as e:
            if not game.is_set(): return #Check if game is over
            send(wfile2, f"Invalid input: {e}", game)
            if not game.is_set(): return #Check if game is over


if __name__ == "__main__":
    pass




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
players cant enter input into game if game inactive flag or if they dont have input flag.
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






"""
game checks:
end if flagged = F

send: F -> send -> return
input: F -> flag player input -> wait for input -> unflag player input -> F -> return



"""
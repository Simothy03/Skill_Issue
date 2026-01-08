import requests
import chess
import chess.pgn
import chess.engine
from io import StringIO
from dotenv import load_dotenv
import os
from datetime import datetime
from . import db_helpers # Import the helper file

# --- Constants ---
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path)

CHESS_COM_API_URL = os.environ.get('CHESS_COM_API_URL')
CHESS_USER_AGENT = os.environ.get('CHESS_USER_AGENT')

# CPL thresholds
CPL_BLUNDER = 300
CPL_MISTAKE = 100
CPL_INACCURACY = 50

# Tactic definition
TACTIC_DIFFERENCE_THRESHOLD = 150 # 1.5 pawns difference between best and 2nd best move

PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 100 # Internal value, not for material count
}

# --- Chess.com API Functions ---

def get_player_matches(username, year, month):
    """
    Fetches all games for a given user from the Chess.com API.
    """
    url = f"{CHESS_COM_API_URL}/{username}/games/{year:04d}/{month:02d}"
    headers = {"User-Agent": CHESS_USER_AGENT}
    print(f"Requesting URL: {url}")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status() 
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching games for {username}: {e}")
        return None

def pgn_parse(pgn_file):
    """
    Parses a single PGN string into a chess.Game object.
    """
    if not pgn_file:
        return None
    try:
        pgn_io = StringIO(pgn_file)
        game = chess.pgn.read_game(pgn_io)
        return game
    except Exception as e:
        print(f"Error parsing PGN: {e}")
        return None

# --- Full Analysis Function ---

def analyze_game_fully(game, username, engine):
    """
    Analyzes a single game for a specific user, move by move.
    Returns a list of dictionaries, where each dictionary is a mistake
    containing the full feature vector.
    """
    
    mistakes_list = []
    board = game.board()
    
    user_color = None
    if game.headers["White"].lower() == username.lower():
        user_color = chess.WHITE
    elif game.headers["Black"].lower() == username.lower():
        user_color = chess.BLACK
    else:
        print(f"Error: User {username} not found in game headers.")
        return []

    print(f"Analyzing game as {chess.COLOR_NAMES[user_color]} ({username})...")

    for move in game.mainline_moves():
        
        prior_fen = board.fen()
        
        if board.turn == user_color:
            
            if board.is_game_over():
                print(f"Move {board.fullmove_number}: Game is over, skipping analysis.")
                board.push(move) 
                continue       
            
            analysis_limit = chess.engine.Limit(time=0.1)
            analysis = None
            try:
                analysis = engine.analyse(board, analysis_limit, multipv=2)
            except Exception as e:
                print(f"ERROR during engine.analyse: {e}. FEN: {prior_fen}")

            
            # --- FIX #1: Check for 'pv' (Principal Variation) list, not 'move' ---
            if not analysis or 'pv' not in analysis[0] or not analysis[0]['pv']:
                print(f"No valid analysis for move {board.fullmove_number} ({chess.COLOR_NAMES[board.turn]}). FEN: {prior_fen}. Analysis result: {analysis}")
            
            else:
                # --- Analysis was successful ---
                best_move_info = analysis[0]
                
                # --- FIX #2: Get the best move from the 'pv' list ---
                best_move = best_move_info['pv'][0] 
                best_score = best_move_info['score'].relative.score(mate_score=10000)
                
                user_move_score = None
                
                # --- FIX #3: Check the 'pv' list in the loop ---
                for move_info in analysis:
                    if 'pv' in move_info and move_info['pv'] and move_info['pv'][0] == move:
                        user_move_score = move_info['score'].relative.score(mate_score=10000)
                        break
                
                if user_move_score is None:
                    # User's move was not in the top 2, analyze it specifically
                    board.push(move) 
                    user_analysis = engine.analyse(board, analysis_limit)
                    
                    if user_analysis['score'].is_mate():
                         user_move_score = -user_analysis['score'].relative.score(mate_score=10000)
                    else:
                         user_move_score = user_analysis['score'].relative.score(mate_score=10000) * -1
                    
                    board.pop() 

                cpl = max(0, best_score - user_move_score)
                mistake_type = get_mistake_type(cpl)

                if mistake_type != "Good":
                    print(f"Found mistake! Move: {board.fullmove_number}, Type: {mistake_type}, CPL: {cpl}")
                    
                    moved_piece = board.piece_at(move.from_square)
                    
                    mistake_data = {
                        "move_number": board.fullmove_number,
                        "player_color": chess.COLOR_NAMES[user_color],
                        "prior_fen": prior_fen,
                        "move_made": move.uci(),
                        "best_move": best_move.uci(),
                        "cpl": cpl,
                        "mistake_type": mistake_type,
                        "mistake_category": get_mistake_category(board, move, analysis),
                        "game_phase": get_game_phase(board),
                        "material_balance": get_material_balance(board, user_color),
                        "board_complexity": get_board_complexity(board),
                        "king_self_safety": get_king_safety(board, user_color),
                        "king_opponent_status": get_king_safety(board, not user_color),
                        "castling_status_self": get_castling_status(board, user_color),
                        "piece_moved": chess.PIECE_NAMES[moved_piece.piece_type].upper() if moved_piece else 'UNKNOWN',
                        "move_type": get_move_type(board, move),
                        "piece_was_attacked": board.is_attacked_by(not user_color, move.from_square),
                        "piece_was_defended": board.is_attacked_by(user_color, move.from_square),
                        "piece_was_defending": is_piece_defending(board, move.from_square, user_color),
                        "piece_was_pinned": board.is_pinned(user_color, move.from_square)
                    }
                    mistakes_list.append(mistake_data)
        
        board.push(move)
        
    return mistakes_list

# --- Analysis Helper Functions ---

def get_mistake_type(cpl):
    if cpl >= CPL_BLUNDER: return "Blunder"
    if cpl >= CPL_MISTAKE: return "Mistake"
    if cpl >= CPL_INACCURACY: return "Inaccuracy"
    return "Good"

def get_mistake_category(board, move, analysis):
    """
    Categorizes the mistake based on tactical and positional checks.
    """
    # 1. Check for Missed Tactic
    if len(analysis) > 1:
        best_score = analysis[0]['score'].relative.score(mate_score=10000)
        second_best_score = analysis[1]['score'].relative.score(mate_score=10000)
        if (best_score - second_best_score) > TACTIC_DIFFERENCE_THRESHOLD:
            return "Missed_Tactic"
            
    # 2. Check for Hanging Piece
    if is_move_a_hang(board, move):
        return "Hanging_Piece"
    
    # 3. Default to Positional Error
    return "Positional_Error"

def is_move_a_hang(board, move):
    """
    Checks if a move results in hanging a piece or a bad trade.
    """
    to_square = move.to_square
    moved_piece = board.piece_at(move.from_square)
    if moved_piece is None: return False
    
    moved_piece_value = PIECE_VALUES[moved_piece.piece_type]
    user_color = board.turn
    opponent_color = not user_color
    
    opponent_attackers = board.attackers(opponent_color, to_square)
    if not opponent_attackers:
        return False # Not attacked, not a hang

    our_defenders = board.attackers(user_color, to_square)
    
    if not our_defenders:
        return True # Attacked and undefended

    lowest_attacker_value = 100
    for attacker_square in opponent_attackers:
        attacker_piece = board.piece_at(attacker_square)
        if attacker_piece:
            lowest_attacker_value = min(lowest_attacker_value, PIECE_VALUES[attacker_piece.piece_type])
    
    if moved_piece_value > lowest_attacker_value:
        return True

    return False

def get_game_phase(board):
    pieces = len(board.piece_map())
    if board.fullmove_number < 12 and pieces > 28:
        return "Opening"
    if pieces < 14:
        return "Endgame"
    return "Middlegame"

def get_material_balance(board, user_color):
    user_score = 0
    opp_score = 0
    for piece_type in PIECE_VALUES:
        if piece_type == chess.KING: continue
        user_score += len(board.pieces(piece_type, user_color)) * PIECE_VALUES[piece_type]
        opp_score += len(board.pieces(piece_type, not user_color)) * PIECE_VALUES[piece_type]

    diff = user_score - opp_score
    if diff > 1.5: return "Winning"
    if diff < -1.5: return "Losing"
    return "Equal"

def get_king_safety(board, color):
    """A simple heuristic for king safety."""
    if board.is_check():
        return "In_Check"
        
    king_square = board.king(color)
    if king_square is None: return "Safe" # Should not happen
        
    nearby_squares = board.attacks(king_square)
    attackers = 0
    for square in nearby_squares:
        if board.is_attacked_by(not color, square):
            attackers += 1
            
    if attackers > 3:
        return "Exposed"
        
    return "Safe"

def get_board_complexity(board):
    piece_count = len(board.piece_map())
    if piece_count > 26: return "High"
    if piece_count < 10: return "Low"
    return "Medium"

def get_castling_status(board, color):
    """
    Returns the exact castling status: Has_Castled, Can_Castle, or Cannot_Castle.
    """
    # 1. Check if they HAVE CASTLED
    # We check if the king is on a traditional castled square 
    # AND that all castling rights for that player are gone.
    king_square = board.king(color)
    if color == chess.WHITE:
        castled_squares = [chess.G1, chess.C1]
    else:
        castled_squares = [chess.G8, chess.C8]

    # If King is on a castled square and rights are gone, they have castled.
    if king_square in castled_squares and not board.has_castling_rights(color):
        return "Has_Castled"

    # 2. Check if they CAN CASTLE
    # This checks the FEN/internal state to see if rights still exist.
    if board.has_castling_rights(color):
        return "Can_Castle"

    # 3. Otherwise, they CANNOT CASTLE
    # This covers cases where the king is stuck in the center or 
    # rights were lost due to moving the king/rooks.
    return "Cannot_Castle"

def get_move_type(board, move):
    if board.is_capture(move): return "Capture"
    if board.gives_check(move): return "Check"
    return "Quiet"

def is_piece_defending(board, square, color):
    """Check if the piece on 'square' is defending another piece."""
    piece = board.piece_at(square)
    if piece is None: return False
    
    # 1. Remove the piece temporarily
    board.remove_piece_at(square)
    
    # 2. Check all other pieces of the same color
    defended_any = False
    for sq in board.pieces(piece.piece_type, color):
        if board.is_attacked_by(not color, sq):
            defended_any = True
            break
            
    # 3. Put the piece back
    board.set_piece_at(square, piece)
    return defended_any


# --- Main Processing Function ---

def process_user_games(username, year, month, engine, conn):
    """
    Main logic function. Fetches, analyzes, and saves games and mistakes.
    This function EXPECTS an active engine and db connection.
    """
    
    all_mistakes_to_insert = []
    games_processed_count = 0
    
    with conn.cursor() as cur:
        # --- 1. Get User ID ---
        user_id = db_helpers.get_user_by_username(cur, username)
        if not user_id:
            return 

        # --- 2. Fetch Games from Chess.com ---
        games_data = get_player_matches(username, year, month)
        if not games_data or not games_data.get("games"):
            print("No games found for this user and month.")
            return

        # --- 3. Process Each Game ---
        for i, game_json in enumerate(games_data["games"]):
            pgn = game_json.get("pgn")
            game_url = game_json.get("url")
            game_obj = pgn_parse(pgn)
            
            if not game_obj:
                print(f"Skipping game {i+1} (PGN parse error).")
                continue
            
            print(f"Processing game {i+1}/{len(games_data['games'])}...")
            
            # --- 4. Insert Game into 'games' table ---
            game_date_str = game_obj.headers.get("UTCDate", "1970.01.01") + " " + game_obj.headers.get("UTCTime", "00:00:00")
            game_date_obj = datetime.strptime(game_date_str, '%Y.%m.%d %H:%M:%S')
            source_game_id = game_url.split('/')[-1]
            
            new_game_id = db_helpers.insert_game(
                cur, user_id, 'chess.com', source_game_id, 
                game_url, pgn, game_date_obj
            )
            
            if not new_game_id:
                continue # Game already existed, skip analysis
                
            games_processed_count += 1
            
            # --- 5. Analyze Game for Mistakes ---
            # *** USE THE FULL ANALYSIS FUNCTION ***
            mistakes_from_game = analyze_game_fully(game_obj, username, engine)
            print(f"Found {len(mistakes_from_game)} mistakes in this game.")
            
            # --- 6. Prepare Mistakes for Batch Insert ---
            for mistake_dict in mistakes_from_game:
                mistake_dict['game_id'] = new_game_id
                all_mistakes_to_insert.append(mistake_dict)

        # --- 7. Perform Batch Insert ---
        if all_mistakes_to_insert:
            print(f"\nQueueing {len(all_mistakes_to_insert)} total mistakes from {games_processed_count} new games for insert...")
            # This helper function MUST be updated
            db_helpers.batch_insert_mistakes(cur, all_mistakes_to_insert)
        else:
            print("\nNo new mistakes to insert.")
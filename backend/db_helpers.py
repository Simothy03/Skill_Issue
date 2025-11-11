import psycopg2
from psycopg2.extras import execute_values, RealDictCursor # Added RealDictCursor
from datetime import datetime

def get_user_by_username(cur, username):
    """
    Fetches a user's ID from the database using their chess.com username.
    """
    try:
        cur.execute("SELECT id FROM users WHERE chess_com_username = %s", (username,))
        user_row = cur.fetchone()
        if user_row:
            return user_row[0]
        else:
            print(f"Error: User '{username}' not found in 'users' table.")
            return None
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error fetching user: {error}")
        return None

def insert_game(cur, user_id, source, source_game_id, game_url, pgn_data, game_date):
    """
    Inserts a single game into the 'games' table.
    Handles conflicts if the game already exists.
    Returns the new game_id or None if it already existed.
    """
    insert_game_sql = """
    INSERT INTO games (user_id, source, source_game_id, game_url, pgn_data, game_date)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (user_id, source, source_game_id) DO NOTHING
    RETURNING id;
    """
    try:
        cur.execute(insert_game_sql, (
            user_id, source, source_game_id, game_url, pgn_data, game_date
        ))
        game_id_row = cur.fetchone()
        
        if game_id_row:
            return game_id_row[0]
        else:
            print(f"Game {source_game_id} already exists in DB. Skipping.")
            return None
            
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error inserting game: {error}")
        return None

def batch_insert_mistakes(cur, mistakes_list_of_dicts):
    """
    Efficiently inserts a list of mistake dictionaries into the 'mistakes' table.
    This function is now updated for the FULL schema.
    """
    if not mistakes_list_of_dicts:
        print("No mistakes to insert.")
        return

    # *** IMPORTANT ***
    # This list MUST match the order of columns in your 'mistakes' table
    # AND the keys in the 'mistake_data' dictionary from matches.py
    columns = [
        'game_id',
        # Core Move Info
        'move_number', 'player_color', 'prior_fen', 'move_made', 'best_move',
        # Stockfish Analysis
        'cpl', 'mistake_type', 'mistake_category',
        # Feature Vector
        'game_phase', 'material_balance', 'board_complexity',
        # King Safety Context
        'king_self_safety', 'king_opponent_status', 'castling_status_self',
        # Move/Piece Context
        'piece_moved', 'move_type',
        # Tactical Context
        'piece_was_attacked', 'piece_was_defended', 'piece_was_defending', 'piece_was_pinned'
    ]
    
    # Create a list of tuples from the list of dictionaries
    # This ensures the data is in the correct order for execute_values
    values_list = []
    for mistake in mistakes_list_of_dicts:
        # Use .get(col) to safely retrieve values (it returns None if key is missing)
        values_list.append(tuple(mistake.get(col) for col in columns))

    # Create the SQL query
    insert_mistakes_sql = f"""
    INSERT INTO mistakes ({', '.join(columns)}) 
    VALUES %s;
    """
    
    try:
        execute_values(cur, insert_mistakes_sql, values_list)
        print(f"Successfully batch-inserted {len(values_list)} mistakes.")
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error batch-inserting mistakes: {error}")

def get_all_mistakes_for_user(cur, user_id):
    """
    Fetches the full feature vector for every mistake a user has made.
    Uses RealDictCursor to return a list of dictionaries.
    """
    # These are all the columns we'll use for clustering
    feature_columns = [
        'id', # We need the mistake ID to link it back to the habit
        'mistake_type', 'mistake_category', 'game_phase', 'material_balance', 
        'board_complexity', 'king_self_safety', 'king_opponent_status', 
        'castling_status_self', 'piece_moved', 'move_type', 'piece_was_attacked', 
        'piece_was_defended', 'piece_was_defending', 'piece_was_pinned'
    ]
    
    # Select only mistakes that haven't been assigned a habit yet
    select_sql = f"""
    SELECT {', '.join(feature_columns)} 
    FROM mistakes 
    WHERE game_id IN (SELECT id FROM games WHERE user_id = %s)
    AND habit_id IS NULL; 
    """
    
    try:
        # We use a RealDictCursor to get back dicts instead of tuples
        with cur.connection.cursor(cursor_factory=RealDictCursor) as dict_cur:
            dict_cur.execute(select_sql, (user_id,))
            mistakes = dict_cur.fetchall()
        
        print(f"Fetched {len(mistakes)} new mistakes for user {user_id}.")
        return mistakes
        
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error fetching mistakes for user: {error}")
        return []

def create_habit_entry(cur, user_id, habit_name, description=""):
    """
    Creates a new row in the 'habits' table for a user.
    Returns the new habit's ID.
    """
    insert_sql = """
    INSERT INTO habits (user_id, habit_name, description)
    VALUES (%s, %s, %s)
    RETURNING id;
    """
    try:
        cur.execute(insert_sql, (user_id, habit_name, description))
        habit_id = cur.fetchone()[0]
        return habit_id
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error creating habit entry: {error}")
        return None

def link_mistakes_to_habit(cur, habit_id, list_of_mistake_ids):
    """
    Updates the 'habit_id' for a list of mistakes.
    """
    if not list_of_mistake_ids:
        print("No mistake IDs to link.")
        return

    # We use execute_values for an efficient UPDATE
    # It requires a list of tuples, so we format it as (habit_id, mistake_id)
    data_to_update = [(habit_id, mistake_id) for mistake_id in list_of_mistake_ids]

    update_sql = """
    UPDATE mistakes AS m
    SET habit_id = data.habit_id
    FROM (VALUES %s) AS data(habit_id, mistake_id)
    WHERE m.id = data.mistake_id;
    """
    
    try:
        execute_values(cur, update_sql, data_to_update)
        print(f"Linked {len(list_of_mistake_ids)} mistakes to habit {habit_id}.")
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error linking mistakes to habit: {error}")

def get_mistakes_by_habit_id(cur, habit_id):
    """
    Fetches all feature vectors for mistakes associated with a specific habit_id.
    """
    # Define the features we care about for rule mining
    feature_columns = [
        'mistake_type', 'mistake_category', 'game_phase', 'material_balance', 
        'board_complexity', 'king_self_safety', 'king_opponent_status', 
        'castling_status_self', 'piece_moved', 'move_type', 'piece_was_attacked', 
        'piece_was_defended', 'piece_was_defending', 'piece_was_pinned'
    ]
    
    select_sql = f"""
    SELECT {', '.join(feature_columns)} 
    FROM mistakes 
    WHERE habit_id = %s;
    """
    
    try:
        # We use a RealDictCursor to get back dicts instead of tuples
        with cur.connection.cursor(cursor_factory=RealDictCursor) as dict_cur:
            dict_cur.execute(select_sql, (habit_id,))
            mistakes = dict_cur.fetchall()
        
        print(f"Fetched {len(mistakes)} mistakes for habit {habit_id}.")
        return mistakes
        
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error fetching mistakes for habit: {error}")
        return []
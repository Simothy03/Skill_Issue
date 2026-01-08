import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
from datetime import datetime
import json

def get_user_by_username(cur, username):
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
    if not mistakes_list_of_dicts:
        print("No mistakes to insert.")
        return

    columns = [
        'game_id', 'move_number', 'player_color', 'prior_fen', 'move_made', 'best_move',
        'cpl', 'mistake_type', 'mistake_category', 'game_phase', 'material_balance', 
        'board_complexity', 'king_self_safety', 'king_opponent_status', 
        'castling_status_self', 'piece_moved', 'move_type', 'piece_was_attacked', 
        'piece_was_defended', 'piece_was_defending', 'piece_was_pinned'
    ]
    
    values_list = [tuple(mistake.get(col) for col in columns) for mistake in mistakes_list_of_dicts]
    insert_mistakes_sql = f"INSERT INTO mistakes ({', '.join(columns)}) VALUES %s;"
    
    try:
        execute_values(cur, insert_mistakes_sql, values_list)
        print(f"Successfully batch-inserted {len(values_list)} mistakes.")
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error batch-inserting mistakes: {error}")

def clear_old_habits_and_feedback(cur, user_id):
    """
    Deletes all existing habits and feedback for a user before
    re-analyzing them. Also unlinks all mistakes.
    """
    try:
        print(f"Clearing old analysis data for user {user_id}...")
        
        # unlink all mistakes from habits
        cur.execute(
            """
            UPDATE mistakes SET habit_id = NULL 
            WHERE game_id IN (SELECT id FROM games WHERE user_id = %s)
            """, 
            (user_id,)
        )
        
        cur.execute("DELETE FROM habits WHERE user_id = %s", (user_id,))
        print("Old analysis cleared.")
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error clearing old habits: {error}")
        raise

def get_all_mistakes_for_user_v6(cur, user_id):
    """
    Fetches ALL mistakes for a user, regardless of habit_id.
    This is the main dataset for HDBSCAN.
    """
    sql = """
    SELECT 
        id, cpl, move_number, -- Numeric features
        mistake_type, mistake_category, game_phase, material_balance, -- Categorical features
        board_complexity, king_self_safety, king_opponent_status, 
        castling_status_self, piece_moved, move_type, piece_was_attacked, 
        piece_was_defended, piece_was_defending, piece_was_pinned
    FROM mistakes
    WHERE game_id IN (SELECT id FROM games WHERE user_id = %s);
    """
    try:
        with cur.connection.cursor(cursor_factory=RealDictCursor) as dict_cur:
            dict_cur.execute(sql, (user_id,))
            mistakes = dict_cur.fetchall()
        print(f"Fetched {len(mistakes)} total mistakes for user {user_id} for clustering.")
        return [dict(row) for row in mistakes]
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error fetching all mistakes: {error}")
        return []

def link_mistakes_to_habit(cur, new_serial_habit_id, list_of_mistake_ids):
    """
    Updates the 'habit_id' for a list of mistakes.
    This is called *after* a new habit is created.
    """
    if not list_of_mistake_ids:
        print("No mistake IDs to link.")
        return

    # Create a list of tuples: (new_serial_habit_id, mistake_id)
    data_to_update = [(new_serial_habit_id, mistake_id) for mistake_id in list_of_mistake_ids]

    update_sql = """
    UPDATE mistakes AS m
    SET habit_id = data.habit_id
    FROM (VALUES %s) AS data(habit_id, mistake_id)
    WHERE m.id = data.mistake_id;
    """
    
    try:
        execute_values(cur, update_sql, data_to_update)
        print(f"Linked {len(list_of_mistake_ids)} mistakes to new habit_id {new_serial_habit_id}.")
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error linking mistakes to habit: {error}")
        # This will rollback the transaction in main_analysis_pipeline

def save_habit_analysis(cur, user_id, hdbscan_cluster_id, habit_name, triggers, confidence, prime_example_id, feedback_text, improvement_tip):
    """
    Saves the results of the analysis to the 'habits' and 'feedback' tables.
    Returns the new 'habit' table ID (the serial key).
    """
    try:
        # Assuming int/float conversions are already handled:
        hdbscan_cluster_id_int = int(hdbscan_cluster_id)
        prime_example_id_int = int(prime_example_id)
        confidence_float = float(confidence) # Must convert numpy float to standard float
        
        # 1. --- Save ML/Clustering Data to 'habits' table ---
        habit_sql = """
        INSERT INTO habits 
            (user_id, habit_name, description, cluster_id, confidence, triggers_json, prime_example_mistake_id)
        VALUES 
            (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, habit_name) DO NOTHING
        RETURNING id;
        """
        description = f"HDBSCAN Cluster {hdbscan_cluster_id_int} ({confidence_float * 100:.0f}% confidence)"
        triggers_json = json.dumps(triggers)
        
        cur.execute(habit_sql, (
            user_id, habit_name, description, 
            hdbscan_cluster_id_int, confidence_float, triggers_json, prime_example_id_int
        ))
        
        habit_id_row = cur.fetchone()
        if not habit_id_row:
             print(f"Habit '{habit_name}' already exists in DB. Skipping analysis save.")
             return None
             
        new_serial_habit_id = habit_id_row[0]

        # 2. --- Save LLM Feedback to 'feedback' table ---
        feedback_sql = """
        INSERT INTO feedback 
            (habit_id, feedback_text, coaching_feedback, improvement_tip)
        VALUES 
            (%s, %s, %s, %s);  -- 4 placeholders
        """
        
        cur.execute(
            feedback_sql, 
            (
                new_serial_habit_id, 
                feedback_text,         # Value for DB column: feedback_text
                feedback_text,         # Value for DB column: coaching_feedback
                improvement_tip        # Value for DB column: improvement_tip
            )
        )
        
        print(f"Saved analysis for new habit {new_serial_habit_id} (Cluster {hdbscan_cluster_id}).")
        return new_serial_habit_id
        
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error saving habit analysis: {error}")
        return None
    
def get_all_habits_for_user(cur, user_id):
    cur.execute("""
        SELECT 
            h.cluster_id AS hdbscan_cluster_id,
            h.habit_name,                   
            h.confidence,
            f.coaching_feedback AS feedback_text,
            f.improvement_tip,
            h.prime_example_mistake_id,
            h.triggers_json,
            COUNT(m.id) AS total_mistakes          
        FROM 
            habits h
        JOIN 
            feedback f ON f.habit_id = h.id
        JOIN 
            mistakes m ON m.habit_id = h.id           
        WHERE 
            h.user_id = %s
        GROUP BY 
            h.id, f.id, h.cluster_id, h.habit_name, h.confidence, f.coaching_feedback, 
            f.improvement_tip, h.prime_example_mistake_id, h.triggers_json
        ORDER BY 
            h.confidence DESC;
    """, (user_id,))
    
    columns = [
        "hdbscan_cluster_id", "habit_name", "confidence", "feedback_text", 
        "improvement_tip", "prime_example_mistake_id", "triggers_json", "total_mistakes"
    ]
    return [dict(zip(columns, row)) for row in cur.fetchall()]

def update_user_info(cur, user_id, new_name, new_chess_username):
    """
    Updates the user's name and linked chess.com username in the 'users' table.
    """
    # SQL to update the user's name and chess_com_username based on their ID
    update_sql = """
    UPDATE users 
    SET name = %s, chess_com_username = %s
    WHERE id = %s
    RETURNING id;
    """
    
    try:
        cur.execute(update_sql, (new_name, new_chess_username, user_id))
        
        if cur.rowcount == 0:
            print(f"Error: User with ID {user_id} not found for update.")
            return False
            
        print(f"Successfully updated user ID {user_id}. Name: {new_name}, Chess Username: {new_chess_username}")
        return True
        
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error updating user info: {error}")
        return False
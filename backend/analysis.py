import os
import psycopg2
from dotenv import load_dotenv
import numpy as np
import pandas as pd
import gower
import hdbscan
import json
import requests
import time # For exponential backoff placeholder

# --- Key Imports from Scikit-learn ---
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.compose import ColumnTransformer
from sklearn.exceptions import NotFittedError

from openai import OpenAI
from openai.types.chat import ChatCompletionToolParam

from . import db_helpers # Use relative import

# --- LLM Configuration ---
client = OpenAI() 
LLM_MODEL = "gpt-5-mini"

# --- 1. Feature Definitions ---

NUMERIC_COLS = ['cpl', 'move_number']

CATEGORICAL_COLS = [
    'mistake_type', 'mistake_category', 'game_phase', 'material_balance', 
    'board_complexity', 'king_self_safety', 'king_opponent_status', 
    'castling_status_self', 'piece_moved', 'move_type', 'piece_was_attacked', 
    'piece_was_defended', 'piece_was_defending', 'piece_was_pinned'
]

CONTEXT_TRIGGERS = [
    'game_phase_', 'material_balance_', 'board_complexity_', 'castling_status_'
]
ACTION_TRIGGERS = [
    'mistake_type_', 'mistake_category_', 
    'piece_moved_', 'move_type_', 'piece_was_attacked_', 'piece_was_defended_',
    'piece_was_defending_', 'piece_was_pinned_', 'king_self_safety_', 'king_opponent_status_'
]

# Note: The manual TRANSLATIONS dict is removed as the LLM handles the natural language generation.

# --- 2. Main Analysis Pipeline ---

def main_analysis_pipeline(user_id, conn):
    """
    Main v9 pipeline:
    1. Clears old analysis.
    2. Fetches all mistakes.
    3. Runs HDBSCAN to find "Habit Archetypes".
    4. For each habit, runs L1 Model (One-vs-All) to find triggers.
    5. Uses LLM to generate feedback and saves it.
    """
    
    with conn.cursor() as cur:
        # 1. Clear old habits and feedback
        db_helpers.clear_old_habits_and_feedback(cur, user_id)
        
        # 2. Get all mistake data
        all_mistakes = db_helpers.get_all_mistakes_for_user_v6(cur, user_id)
        
        if len(all_mistakes) < 20: 
            print("Not enough mistakes to run analysis (need >= 20).")
            return {"new_habits_found": 0, "total_mistakes": len(all_mistakes)}
            
        df = pd.DataFrame(all_mistakes).set_index('id') 
        
        # 3. Step 1 (v9): Habit Discovery (HDBSCAN)
        print(f"\n--- Running Step 1: Habit Discovery (HDBSCAN) on {len(df)} mistakes ---")
        df_clustered = _run_hdbscan_clustering(df)
        
        # 4. Separate noise from habits
        noise_df = df_clustered[df_clustered['habit_id'] == -1]
        habits_df = df_clustered[df_clustered['habit_id'] != -1]
        
        if habits_df.empty:
            print("HDBSCAN found no significant habits. Only noise.")
            return {"new_habits_found": 0, "total_mistakes": len(all_mistakes)}

        print(f"HDBSCAN found {habits_df['habit_id'].nunique()} habits and {len(noise_df)} noise points.")
        
        # 5. Step 2 (v9): Trigger Identification (L1 Model)
        print("\n--- Running Step 2: Trigger Identification (L1 Logistic Regression) ---")
        
        preprocessor = _create_feature_preprocessor(df)
        if preprocessor is None:
            print("Failed to create feature preprocessor. Aborting analysis.")
            return {"new_habits_found": 0, "total_mistakes": len(all_mistakes)}

        new_habit_count = 0
        
        for hdbscan_label in habits_df['habit_id'].unique():
            print(f"\n--- Analyzing Habit Cluster {hdbscan_label} ---")
            cluster_df = habits_df[habits_df['habit_id'] == hdbscan_label]
            
            # Use "One-vs-All" (Habit vs. All Other Mistakes, including noise)
            control_df = df_clustered[df_clustered['habit_id'] != hdbscan_label]
            
            model, feature_names = _find_triggers_for_cluster(cluster_df, control_df, preprocessor)
            
            if model is None:
                continue
                
            # 6. Step 3 (v9): Generate, Save, and Link
            new_serial_id = _generate_and_save_feedback(
                cur, user_id, hdbscan_label, cluster_df, model, feature_names
            )
            
            if new_serial_id:
                # Link all mistakes in this cluster to the new habit ID
                list_of_mistake_ids = cluster_df.index.tolist()
                db_helpers.link_mistakes_to_habit(cur, new_serial_id, list_of_mistake_ids)
                new_habit_count += 1

        print(f"\nAnalysis pipeline complete for user {user_id}")
        return {"new_habits_found": new_habit_count, "total_mistakes": len(all_mistakes)}

# --- 3. Pipeline Helper Functions ---

def _run_hdbscan_clustering(df):
    """
    Prepares data and runs HDBSCAN to find clusters.
    """
    df_features = df.copy()
    
    scaler = StandardScaler()
    df_features[NUMERIC_COLS] = scaler.fit_transform(df_features[NUMERIC_COLS])
    
    for col in CATEGORICAL_COLS:
        df_features[col] = df_features[col].astype(str).fillna('None')

    print("Computing Gower distance matrix...")
    gower_matrix = gower.gower_matrix(df_features[NUMERIC_COLS + CATEGORICAL_COLS])
    gower_matrix_double = gower_matrix.astype(np.float64)

    print("Running HDBSCAN...")
    clusterer = hdbscan.HDBSCAN(
        metric='precomputed',
        min_cluster_size=5, # Find habits with as few as 5 mistakes
        min_samples=3,
        allow_single_cluster=False,
        gen_min_span_tree=True
    )
    clusterer.fit(gower_matrix_double)
    
    df['habit_id'] = clusterer.labels_
    df['habit_confidence'] = clusterer.probabilities_
    return df

def _create_feature_preprocessor(df):
    """
    Creates a scikit-learn ColumnTransformer to one-hot encode
    categorical features for the Logistic Regression model.
    """
    try:
        # Fill NAs and ensure string type for encoder
        df_cat = df[CATEGORICAL_COLS].astype(str).fillna('None')
        
        preprocessor = ColumnTransformer(
            transformers=[
                ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), CATEGORICAL_COLS)
            ],
            remainder='drop' 
        )
        
        preprocessor.fit(df_cat)
        return preprocessor
    except Exception as e:
        print(f"Error creating preprocessor: {e}")
        return None

def _find_triggers_for_cluster(cluster_df, control_df, preprocessor):
    """
    Trains a balanced L1 Logistic Regression model (Habit vs. Control).
    """
    positive_df = cluster_df
    negative_df = control_df
    
    if negative_df.empty:
        print("Cannot train model: No 'control' examples to compare against.")
        return None, None
        
    training_df = pd.concat([positive_df, negative_df])
    # The label is 1 if it belongs to the current cluster, 0 otherwise
    Y_train = (training_df['habit_id'] == cluster_df['habit_id'].iloc[0]).astype(int) 
    
    X_train_raw = training_df[CATEGORICAL_COLS].astype(str).fillna('None')
    
    try:
        X_train_processed = preprocessor.transform(X_train_raw)
    except Exception as e:
        print(f"Error during feature transformation: {e}")
        return None, None
    
    # Get the names of the features created by the OneHotEncoder
    feature_names = list(preprocessor.named_transformers_['cat'].get_feature_names_out(CATEGORICAL_COLS))

    model = LogisticRegression(
        penalty='l1', 
        solver='liblinear', 
        class_weight='balanced', 
        C=1.0, # Use 1.0 for less strict regularization (more triggers)
        random_state=42
    )
    model.fit(X_train_processed, Y_train)
    
    return model, feature_names
    
def _generate_llm_feedback(context, action, confidence, cluster_summary, triggers):
    """
    Uses the OpenAI SDK and structured output feature for GPT-4o Mini
    to generate habit name, coaching feedback, and a tip in reliable JSON format.
    """
    
    # Clean up the feature names for better readability in the prompt
    clean_context = context.replace("_", " ").split(" ", 1)[-1].capitalize() if context else "General Context"
    clean_action = action.replace("_", " ").split(" ", 1)[-1].capitalize() if action else "Imprecise Move"
    
    # Format L1 Triggers for LLM
    trigger_list = [f"{k.split('_', 1)[-1]} (Weight: {v:.2f})" for k, v in triggers.items()]
    
    # --- 1. Define the desired output structure (Tool/Function Calling) ---
    tools: list[ChatCompletionToolParam] = [
        {
            "type": "function",
            "function": {
                "name": "generate_habit_feedback",
                "description": "Generates a habit name, coaching feedback, and an improvement tip for a chess player.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "habit_name": {"type": "string", "description": "A short, unique, descriptive name for the habit (max 6 words)."},
                        "feedback": {"type": "string", "description": "A friendly coaching insight (1-2 sentences) explaining the cause of the habit."},
                        "tip": {"type": "string", "description": "One concrete improvement tip to correct the habit, addressing the strongest action trigger."},
                    },
                    "required": ["habit_name", "feedback", "tip"],
                },
            }
        }
    ]
    
    # --- 2. Construct the system and user messages ---
    system_prompt = (
        "You are a friendly, encouraging, non-judgmental chess coach AI. "
        "Your task is to analyze a player's recurring mistake pattern based on ML clustering. "
        "Use the provided statistical context (Cluster Summary and L1 Triggers) to make your advice specific. "
        "You MUST output the result by calling the 'generate_habit_feedback' function."
    )
    
    user_prompt = f"""
HDBSCAN Cluster Summary:
{json.dumps(cluster_summary, indent=2)}

L1 Model's Strongest Triggers (Statistical Context):
- Top Context Feature: {clean_context}
- Top Action Feature: {clean_action}
- All Significant Triggers: {trigger_list}
Confidence of Pattern: {confidence * 100:.0f}%

Your task:
1. Generate the content based on the data.
2. Output the result by calling the 'generate_habit_feedback' tool.
"""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    # --- 3. Call the OpenAI API ---
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                tools=tools,
                tool_choice={"type": "function", "function": {"name": "generate_habit_feedback"}}, # Force JSON output via function call
                temperature=1,
                timeout=30,
            )
            
            # Extract arguments from the function call
            if response.choices and response.choices[0].message.tool_calls:
                tool_call = response.choices[0].message.tool_calls[0]
                if tool_call.function.name == "generate_habit_feedback":
                    # The arguments are a JSON string, which we parse
                    return json.loads(tool_call.function.arguments)
            
            # If function call failed or wasn't found, fall through to error handling
            raise ValueError("LLM did not return a valid function call argument.")

        except Exception as e:
            if attempt < 2:
                print(f"LLM call failed on attempt {attempt + 1}: {e}. Retrying...")
                time.sleep(2 ** attempt)
            else:
                print(f"LLM call failed after all attempts: {e}. Returning fallback feedback.")
                # --- Fallback Feedback ---
                return {
                    'habit_name': 'LLM Error Fallback', 
                    'feedback': 'The AI coach could not generate personalized feedback. Please check the API status.', 
                    'tip': 'Review the cluster manually.'
                }


def _generate_and_save_feedback(cur, user_id, hdbscan_label, cluster_df, model, feature_names):
    """
    Extracts triggers, calls the LLM for feedback, and saves the structured result.
    """
    coefficients = model.coef_[0]
    # Get features with a meaningful *positive* association
    triggers = {name: coef for name, coef in zip(feature_names, coefficients) if coef > 0.1} 
    
    if not triggers:
        print(f"No strong positive triggers found for Habit {hdbscan_label}.")
        return None

    # Separate into Context and Action
    context_triggers = {f: c for f, c in triggers.items() if any(t in f for t in CONTEXT_TRIGGERS)}
    action_triggers = {f: c for f, c in triggers.items() if any(t in f for t in ACTION_TRIGGERS)}

    top_context = max(context_triggers, key=context_triggers.get, default=None)
    top_action = max(action_triggers, key=action_triggers.get, default=None)

    habit_confidence = cluster_df['habit_confidence'].mean()
    prime_example_id = int(cluster_df['cpl'].idxmax()) 
    
    # Generate Cluster Summary
    cluster_summary = _summarize_cluster_for_llm(cluster_df)
    
    # --- LLM Integration Point (Live Call) ---
    llm_output = _generate_llm_feedback(top_context, top_action, habit_confidence, cluster_summary, triggers) 
    
    # 1. Get the LLM-suggested name
    suggested_name = llm_output.get('habit_name', 'Unnamed Habit')

    # 2. FIX for Unique Constraint: Append the cluster ID
    habit_name = f"{suggested_name} (H{hdbscan_label})" 
    
    coaching_feedback = llm_output.get('feedback', 'No detailed feedback generated.')
    improvement_tip = llm_output.get('tip', 'No specific tip provided.')
    
    print(f"Generated feedback for cluster {hdbscan_label} ('{habit_name}'): {coaching_feedback}")
    
    # Save to DB and get the new serial ID
    new_serial_habit_id = db_helpers.save_habit_analysis(
        cur, 
        user_id, 
        int(hdbscan_label), 
        habit_name,
        triggers,      
        habit_confidence, 
        prime_example_id, 
        coaching_feedback, 
        improvement_tip    
    )
    return new_serial_habit_id

def _summarize_cluster_for_llm(cluster_df):
    """
    Calculates the most frequent and most severe characteristics of a cluster.
    """
    summary = {}
    
    summary['total_mistakes_in_habit'] = len(cluster_df)
    summary['avg_cpl'] = f"{cluster_df['cpl'].mean():.0f}"
    summary['most_severe_cpl'] = f"{cluster_df['cpl'].max():.0f}"
    
    # Categorical Summary (Top 3 most frequent values for key features)
    top_n = 3
    for col in ['mistake_type', 'game_phase', 'piece_moved', 'mistake_category']:
        top_counts = cluster_df[col].value_counts().nlargest(top_n)
        summary[f'top_{col}'] = [
            f"{val} ({count})" 
            for val, count in top_counts.items()
        ]
        
    return summary
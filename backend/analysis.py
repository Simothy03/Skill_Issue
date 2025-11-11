import os
import psycopg2
from dotenv import load_dotenv
import numpy as np
import pandas as pd
from kmodes.kmodes import KModes
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import apriori, association_rules
from . import db_helpers # Use relative import

# --- Main Analysis Pipeline ---

def main_analysis_pipeline(user_id, conn):
    """
    High-level function to run the full analysis pipeline for a user.
    EXPECTS an active database connection 'conn'.
    The calling function is responsible for commit/rollback.
    """
    
    with conn.cursor() as cur:

        # --- Step 3: Find Habit Clusters ---
        print(f"\n--- Running Step 3: Find Habit Clusters for user {user_id} ---")
        
        new_habit_ids, total_mistakes_found = find_habit_clusters(cur, user_id)
        
        print("--- Step 3 Complete ---")

        if new_habit_ids:
            # --- Step 4: Find Rules for new habits ---
            print(f"\n--- Running Step 4: Find Rules for new habits ---")
            
            all_rules_found = []
            for habit_id in new_habit_ids:
                print(f"\n--- Analyzing Rules for Habit {habit_id} ---")
                rules = get_rules_for_habit(cur, habit_id)
                
                # --- FIX: THIS ENTIRE BLOCK NEEDS TO BE INDENTED ---
                # This code block now runs *inside* the for loop for each habit_id.
                if rules is not None and not rules.empty:
                    # Sort by 'confidence' (high to low) and 'lift' (high to low)
                    rules = rules.sort_values(by=['confidence', 'lift'], ascending=[False, False])

                    print("--- Top 5 Most Confident Rules ---")
                    
                    # Get just the top 5
                    top_5_rules = rules.head(5)

                    # Loop and print them in a readable format
                    for index, rule in top_5_rules.iterrows():
                        print(f"  Rule: IF {set(rule['antecedents'])}")
                        print(f"  THEN {set(rule['consequents'])}")
                        print(f"  Confidence: {rule['confidence']:.2f}")
                        print("  ----")
                    
                    all_rules_found.append(rules.to_json()) # Still save all rules
                else:
                    print("No significant rules found for this habit.")
                # --- END OF FIX ---
            
            print("--- Step 4 Complete ---")
            
            # This is the function from Step 5:
            # generate_feedback_for_habits(cur, user_id, all_rules_found)
        
        print(f"\nAnalysis pipeline complete for user {user_id}")
        
        return {"new_habits_found": len(new_habit_ids), "total_new_mistakes": total_mistakes_found}

#
# (The rest of the file is unchanged)
#

# --- Step 3 Function ---

def find_habit_clusters(cur, user_id):
# ... (rest of function is the same) ...
    mistakes = db_helpers.get_all_mistakes_for_user(cur, user_id)
    total_mistakes_found = len(mistakes)
    
    if total_mistakes_found < 1: 
        print("Not enough new mistakes to run cluster analysis.")
        return [], total_mistakes_found 

    df = pd.DataFrame(mistakes)
    mistake_ids = df.pop('id') 
    
    data_for_clustering = df.fillna('None').astype(str).to_numpy()

    NUM_CLUSTERS = 5
    if len(data_for_clustering) < NUM_CLUSTERS:
        NUM_CLUSTERS = len(data_for_clustering) 
        
    print(f"Running K-Modes with {NUM_CLUSTERS} clusters on {len(data_for_clustering)} mistakes...")
    
    kmode = KModes(n_clusters=NUM_CLUSTERS, init='Cao', n_init=5, verbose=0)
    clusters = kmode.fit_predict(data_for_clustering)
    print("Clustering complete.")

    clustered_mistakes = {}
    for i, cluster_id in enumerate(clusters):
        cluster_id_int = int(cluster_id)
        if cluster_id_int not in clustered_mistakes:
            clustered_mistakes[cluster_id_int] = []
        clustered_mistakes[cluster_id_int].append(int(mistake_ids[i]))
        
    new_habit_ids = []
    for cluster_id, ids_in_cluster in clustered_mistakes.items():
        print(f"Cluster {cluster_id} has {len(ids_in_cluster)} mistakes.")
        
        habit_name = f"Habit Cluster {cluster_id + 1}"
        habit_desc = f"An automatically identified cluster of {len(ids_in_cluster)} similar mistakes."
        
        new_habit_id = db_helpers.create_habit_entry(cur, user_id, habit_name, habit_desc)
        
        if new_habit_id:
            db_helpers.link_mistakes_to_habit(cur, new_habit_id, ids_in_cluster)
            new_habit_ids.append(new_habit_id)
            
    return new_habit_ids, total_mistakes_found 


# --- Step 4 Function ---

def get_rules_for_habit(cur, habit_id):
    """
    Fetches all mistakes for a habit, runs Apriori, and finds
    high-confidence rules that lead to a mistake.
    """
    
    mistakes_data = db_helpers.get_mistakes_by_habit_id(cur, habit_id)
    
    if not mistakes_data or len(mistakes_data) < 5: 
        print(f"Skipping rule generation for habit {habit_id}: cluster is too small.")
        return None
        
    df = pd.DataFrame(mistakes_data)

    df_one_hot = pd.get_dummies(df.fillna('None').astype(str))
    
    if df_one_hot.empty:
        print("Data was empty after one-hot encoding.")
        return None

    print("Running Apriori with min_support=0.7...")
    frequent_itemsets = apriori(df_one_hot, min_support=0.7, use_colnames=True)
    
    if frequent_itemsets.empty:
        print("Apriori found no frequent itemsets with >= 70% support.")
        return None

    print("Generating association rules with min_threshold=0.9...")
    rules = association_rules(frequent_itemsets, metric="confidence", min_threshold=0.9)
    
    if rules.empty:
        print("Found no high-confidence rules.")
        return None
        
    consequent_cols = [col for col in df_one_hot.columns if 'mistake_type_' in col or 'mistake_category_' in col]
    if not consequent_cols:
        print("Could not find any mistake_type/category columns after encoding.")
        return None

    rules = rules[
        rules['consequents'].apply(lambda x: any(item in x for item in consequent_cols))
    ]
    
    rules = rules[
        rules['antecedents'].apply(lambda x: not any(item in x for item in consequent_cols))
    ]
    
    if rules.empty:
        print("No 'Context -> Mistake' rules found after filtering.")
        return None
    
    # --- THIS IS THE FIX ---
    # 1. Create a new column 'antecedent_len' to count the number of "IF" conditions
    rules['antecedent_len'] = rules['antecedents'].apply(lambda x: len(x))
    
    # 2. Sort by confidence, then by lift, then by the new length column.
    # This bubbles the *most specific* (longest), *most interesting* (highest lift),
    # and *most accurate* (highest confidence) rules to the top.
    return rules.sort_values(
        by=['confidence', 'lift', 'antecedent_len'], 
        ascending=[False, False, False]
    )
    
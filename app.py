import os
import random
import time
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
import json
from threading import Lock
import csv

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# File paths
DATA_DIR = 'game_data'
PLAYERS_FILE = os.path.join(DATA_DIR, 'players.json')
GROUPS_FILE = os.path.join(DATA_DIR, 'groups.json')
SCORES_FILE = os.path.join(DATA_DIR, 'scores.json')
WINNERS_FILE = os.path.join(DATA_DIR, 'winners.json')
CSV_FILE = os.path.join(DATA_DIR, 'game_data_export.csv')

# Create data directory if not exists
os.makedirs(DATA_DIR, exist_ok=True)

# Initialize files if they don't exist
for file in [PLAYERS_FILE, GROUPS_FILE, SCORES_FILE, WINNERS_FILE]:
    if not os.path.exists(file):
        with open(file, 'w') as f:
            json.dump({}, f)

# Thread lock for file operations
file_lock = Lock()

def load_json(file_path):
    with file_lock:
        with open(file_path, 'r') as f:
            return json.load(f)

def save_json(file_path, data):
    with file_lock:
        with open(file_path, 'w') as f:
            json.dump(data, f)

def generate_clean_csv():
    """Generate well-formatted CSV file from all JSON data"""
    players = load_json(PLAYERS_FILE)
    scores = load_json(SCORES_FILE)
    winners = load_json(WINNERS_FILE)
    groups = load_json(GROUPS_FILE)
    
    # Prepare group information for lookup
    group_info = {}
    for group_id, members in groups.items():
        group_info[group_id] = {
            'total_players': len(members),
            'members': members
        }
    
    # Prepare CSV data with proper headers
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'Player ID', 'Name', 'Phone', 'Age', 
            'Group ID', 'Position in Group', 'Total Players in Group',
            'Score', 'Is Winner', 'Winning Score', 'Registration Date'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for player_id, player_data in players.items():
            group_id = player_data['group']
            score = scores.get(player_id, 0)
            is_winner = player_id in winners
            winning_score = winners.get(player_id, {}).get('score', 0) if is_winner else 0
            
            # Format timestamp for better readability
            try:
                reg_date = datetime.fromisoformat(player_data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            except:
                reg_date = player_data['timestamp']
            
            writer.writerow({
                'Player ID': player_id,
                'Name': player_data['name'],
                'Phone': player_data['phone'],
                'Age': player_data['age'],
                'Group ID': group_id,
                'Position in Group': player_data['player_number'],
                'Total Players in Group': group_info.get(group_id, {}).get('total_players', 0),
                'Score': score,
                'Is Winner': 'Yes' if is_winner else 'No',
                'Winning Score': winning_score if is_winner else '',
                'Registration Date': reg_date
            })

def assign_to_group(player_id):
    groups = load_json(GROUPS_FILE)
    players = load_json(PLAYERS_FILE)
    
    # Find an existing group with less than 5 players
    for group_id, members in groups.items():
        if len(members) < 5:
            members.append(player_id)
            groups[group_id] = members
            save_json(GROUPS_FILE, groups)
            generate_clean_csv()  # Update CSV
            return group_id, len(members)
    
    # If no available group, create a new one
    new_group_id = f"group_{len(groups) + 1}"
    groups[new_group_id] = [player_id]
    save_json(GROUPS_FILE, groups)
    generate_clean_csv()  # Update CSV
    return new_group_id, 1

def get_group_leaderboard(group_id):
    scores = load_json(SCORES_FILE)
    players = load_json(PLAYERS_FILE)
    
    group_scores = []
    for player_id, score in scores.items():
        player_data = players.get(player_id, {})
        if player_data.get('group') == group_id:
            group_scores.append({
                'name': player_data['name'],
                'score': score,
                'player_number': player_data['player_number']
            })
    
    # Sort by score (descending)
    group_scores.sort(key=lambda x: x['score'], reverse=True)
    return group_scores

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['POST'])
def register():
    name = request.form.get('name')
    phone = request.form.get('phone')
    age = request.form.get('age')
    
    if not name or not phone or not age:
        return redirect(url_for('home'))
    
    try:
        age = int(age)
        if age < 18:
            return redirect(url_for('home'))
    except ValueError:
        return redirect(url_for('home'))
    
    # Create player ID
    player_id = f"player_{int(time.time())}_{random.randint(1000, 9999)}"
    
    # Assign to group
    group_id, player_number = assign_to_group(player_id)
    
    # Save player data
    players = load_json(PLAYERS_FILE)
    players[player_id] = {
        'name': name,
        'phone': phone,
        'age': age,
        'group': group_id,
        'player_number': player_number,
        'timestamp': datetime.now().isoformat()
    }
    save_json(PLAYERS_FILE, players)
    generate_clean_csv()  # Update CSV
    
    return redirect(url_for('game', player_id=player_id))

@app.route('/game/<player_id>')
def game(player_id):
    players = load_json(PLAYERS_FILE)
    if player_id not in players:
        return redirect(url_for('home'))
    
    player_data = players[player_id]
    group_id = player_data['group']
    
    # Get leaderboard for the group
    leaderboard = get_group_leaderboard(group_id)
    
    return render_template('game.html', 
                         player_id=player_id,
                         player_name=player_data['name'],
                         group_id=group_id,
                         player_number=player_data['player_number'],
                         leaderboard=leaderboard)

@app.route('/submit_score', methods=['POST'])
def submit_score():
    player_id = request.form.get('player_id')
    score = int(request.form.get('score', 0))
    
    players = load_json(PLAYERS_FILE)
    if player_id not in players:
        return jsonify({'status': 'error', 'message': 'Invalid player'})
    
    # Save score
    scores = load_json(SCORES_FILE)
    scores[player_id] = score
    save_json(SCORES_FILE, scores)
    
    # Check if this player is the winner in their group
    group_id = players[player_id]['group']
    leaderboard = get_group_leaderboard(group_id)
    
    if leaderboard and leaderboard[0]['name'] == players[player_id]['name']:
        winners = load_json(WINNERS_FILE)
        winners[player_id] = {
            'name': players[player_id]['name'],
            'score': score,
            'group': group_id,
            'timestamp': datetime.now().isoformat()
        }
        save_json(WINNERS_FILE, winners)
    
    generate_clean_csv()  # Update CSV
    return jsonify({'status': 'success'})

@app.route('/get_leaderboard/<group_id>')
def get_leaderboard(group_id):
    leaderboard = get_group_leaderboard(group_id)
    return jsonify(leaderboard)

@app.route('/download_csv')
def download_csv():
    generate_clean_csv()  # Ensure latest data
    return send_from_directory(DATA_DIR, 'game_data_export.csv', as_attachment=True)

if __name__ == '__main__':
    # Generate initial CSV file when starting the app
    generate_clean_csv()
    app.run(debug=True)
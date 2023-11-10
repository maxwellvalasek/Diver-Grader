from flask import Flask, jsonify, request, render_template
import os
import json
from jsonscores import create_diver_json, get_diver_number

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')
@app.route('/get-grades', methods=['POST'])

def get_grades():
    diver_name = request.form.get('diver_name')
    diver_id = get_diver_number(diver_name)  # Convert name to ID
    filepath = f'divers/{diver_id}.json'  # JSON filename uses the ID
    
    # Check if the JSON file already exists
    if not os.path.exists(filepath):
        # Only run create_diver_json if the file does not exist
        create_diver_json(diver_name)
    
    # After checking and potential creation, open and return the JSON data
    if os.path.exists(filepath):
        with open(filepath, 'r') as json_file:
            data = json.load(json_file)
        return jsonify(data)
    else:
        return jsonify({"error": "Diver not found"}), 404


if __name__ == '__main__':
    app.run(debug=True)

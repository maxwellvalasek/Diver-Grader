from jsonscores import create_diver_json
import os

input_file = 'extracted_numbers2019ncw.txt'
diver_directory = 'divers'  # Update this to the correct directory name if different

try:
    with open(input_file, 'r') as file:
        lines = file.readlines()
        current = 0
        for line in lines:
            diver_number = line.strip()  # Remove newline characters
            json_filename = f"{diver_number}.json"
            json_file_path = os.path.join(diver_directory, json_filename)
            if not os.path.isfile(json_file_path):  # Check if JSON file does not exist
                create_diver_json(diver_number)
            current += 1
except FileNotFoundError:
    print(f"File '{input_file}' not found.")
except Exception as e:
    print(f"An error occurred: {e}")
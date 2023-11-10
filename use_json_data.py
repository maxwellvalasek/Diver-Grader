import os
import json
from jsonscores import recalculate_and_save_rankings

def list_json_files(directory):
    """Lists JSON files in the given directory, extracts data, sorts by overall grade, and prints with aligned formatting."""
    if not os.path.exists(directory):
        print(f"Directory '{directory}' does not exist.")
        return

    json_files = [f for f in os.listdir(directory) if f.endswith('.json')]
    data_list = []
    if json_files:
        for file_name in json_files:
            file_path = os.path.join(directory, file_name)
            with open(file_path, 'r') as json_file:
                try:
                    data = json.load(json_file)
                    name = data.get('name', 'Name not found')
                    overall_grade = data.get('rankings', {}).get('overall_average_grade', 'Grade not found')
                    one_meter_grade = data.get('rankings', {}).get('1 Meter', {}).get('average_grade', 'Grade not found')
                    three_meter_grade = data.get('rankings', {}).get('3 Meter', {}).get('average_grade', 'Grade not found')
                    platform_grade = data.get('rankings', {}).get('Platform', {}).get('average_grade', 'Grade not found')
                    data_list.append((name, overall_grade, one_meter_grade, three_meter_grade, platform_grade))
                except json.JSONDecodeError:
                    print(f"Error decoding JSON in file: {file_name}")

        # Sort the list by overall grade
        data_list.sort(key=lambda x: x[1])

        # Determine the max length of the names for formatting
        max_name_length = max(len(name) for name, *_ in data_list)

        print("JSON files in directory, sorted by Overall Grade:")
        for name, overall, one_meter, three_meter, platform in data_list:
            print(f"{name.ljust(max_name_length)} | {overall} | {one_meter} | {three_meter} | {platform}")
    else:
        print("No JSON files found in the directory.")

if __name__ == "__main__":
    directory_path = "divers/"
    recalculate_and_save_rankings(directory_path)
    list_json_files(directory_path)

import requests
from concurrent.futures import ThreadPoolExecutor
import os
import argparse
from jsonscores import create_diver_json

def check_for_dive_statistics_and_json(number, session):
    url = f"https://secure.meetcontrol.com/divemeets/system/profile.php?number={number}"
    json_file_path = f"divers/{number}.json"

    if os.path.exists(json_file_path):
        return number, False

    try:
        with session.get(url, stream=True) as response:
            for line in response.iter_lines():
                if 'Dive Statistics' in line.decode('utf-8'):
                    create_diver_json(number)
                    return number, True
            return number, False
    except requests.RequestException:
        return number, False

def main():
    parser = argparse.ArgumentParser(description='Check Dive Statistics for a range of numbers.')
    parser.add_argument('start_number', type=int, help='Starting number of the range')
    parser.add_argument('end_number', type=int, help='Ending number of the range')
    parser.add_argument('--threads', type=int, default=8, help='Number of threads to use')
    args = parser.parse_args()

    max_threads = args.threads
    session = requests.Session()
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = [executor.submit(check_for_dive_statistics_and_json, number, session) for number in range(args.start_number, args.end_number + 1)]
        for future in futures:
            number, result = future.result()

if __name__ == "__main__":
    main()

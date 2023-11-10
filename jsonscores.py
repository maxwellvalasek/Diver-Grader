import asyncio
import aiohttp
from bs4 import BeautifulSoup
import json
import re
import pandas as pd
from bs4 import BeautifulSoup
import mechanize
import re
import os

def get_diver_number(name):
    br = mechanize.Browser()

    # Split name
    comps = name.split()
    if len(comps) != 2:
        raise Exception("Name provided must be two words (First Last)")
    first, last = comps

    # Submit member search form
    url = "https://secure.meetcontrol.com/divemeets/system/memberlist.php"
    br.open(url)
    br.select_form(nr=0)
    br.form["first"] = first
    br.form["last"] = last
    req = br.submit()
    soup = BeautifulSoup(req.read(), "html.parser")
    br.close()

    link = soup.find("a", attrs={"href": re.compile("profile.php")}).get("href")
    last_five = link[-5:]
    return last_five

# Function to extract the first date in the format "Aug 1, 2012" from text
def extract_first_date(text):
    pattern = r'(\bJan\b|\bFeb\b|\bMar\b|\bApr\b|\bMay\b|\bJun\b|\bJul\b|\bAug\b|\bSep\b|\bOct\b|\bNov\b|\bDec\b)\s+(\d{1,2}),\s+(\d{4})'
    match = re.search(pattern, text)
    if match:
        month_to_num = {
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', 'May': '05', 'Jun': '06',
            'Jul': '07', 'Aug': '08', 'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
        }
        month, day, year = match.groups()
        return f'{year}-{month_to_num[month]}-{day.zfill(2)}'
    return None

# Function to extract text before the first hyphen in the input text
def extract_text_before_hyphen(text):
    return text.split(" -", 1)[0] if " -" in text else text

# Async function to fetch a webpage using aiohttp
async def fetch(session, url, **params):
    async with session.get(url, params=params) as response:
        return await response.text()

# Async function to fetch a diver's profile page
async def get_diver_page(session, diver_number):
    return await fetch(session, "https://secure.meetcontrol.com/divemeets/system/profile.php", number=diver_number)

# Async function to fetch dive heights for a diver
async def fetch_dive_heights(session, diver_number):
    html_content = await get_diver_page(session, diver_number)
    if not html_content:
        return []
    soup = BeautifulSoup(html_content, 'html.parser')
    return [(row.find_all('td')[0].text, row.find_all('td')[1].text.replace("M", "").strip()) for row in soup.find_all('tr', {'bgcolor': True})]

# Async function to fetch scores for a specific dive and height
async def fetch_scores_for_dive_height(session, diver_number, dive, height):
    json_data = {}
    html_content = await fetch(session, "https://secure.meetcontrol.com/divemeets/system/diversdives.php", dvrnum=diver_number, height=height, dive=dive)
    
    if not html_content:
        return json_data
    
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table', {'width': '100%'})
    
    if not table:
        return json_data
    
    for row in table.find_all('tr')[3:]:
        cells = row.find_all('td')
        if len(cells) <= 1:
            continue
        
        event_info = cells[0].text.strip()
        score = float(cells[1].text.strip())
        date = extract_first_date(event_info)
        meet = extract_text_before_hyphen(event_info)
        event = "Platform" if height in ['5', '7', '10'] else f"{height} Meter"
        direction = {'1': 'Front', '2': 'Back', '3': 'Reverse', '4': 'Inward', '5': 'Twister', '6': 'Armstand'}.get(dive[0], 'Unknown')
        
        # Populate JSON structure
        if event not in json_data:
            json_data[event] = {}
        if direction not in json_data[event]:
            json_data[event][direction] = {"dives": {}}
        if dive not in json_data[event][direction]["dives"]:
            json_data[event][direction]["dives"][dive] = {
                "dd": dd_lookup.get((dive, height), "DD Not Found"),  # Look up DD
                "height": height,
                "performance": []
            }
        json_data[event][direction]["dives"][dive]["performance"].append({
            "date": date,
            "score": score,
            "meet": meet
        })
    
    return json_data

def add_count_and_average(json_data):
    for event, directions in json_data.items():
        for direction, dives in directions.items():
            for dive, details in dives["dives"].items():
                performances = details["performance"]
                count = len(performances)
                if count > 0:
                    average_score = sum(p["score"] for p in performances) / count
                else:
                    average_score = 0
                details["count"] = count
                details["average_score"] = round(average_score, 2)
     
def calculate_rankings(events_data):
    max_points = {
        "Platform": 63,
        "3 Meter": 60,
        "1 Meter": 57
    }
    
    rankings = {}
    event_grades = {}  # To store the average grade for each event
    total_grade_sum = 0  # Sum of all event grades
    total_grade_count = 0  # Count of all events with grades

    for event, directions in events_data.items():
        event_grade_sum = 0  # Sum of grades for the event
        event_grade_count = 0  # Count of grades for the event
        rankings[event] = {}
        for direction, dives_data in directions.items():
            if direction == "Unknown":  # Skip the "Unknown" direction
                continue
            # Initialize the direction with default values
            rankings[event][direction] = {
                "top_2_avg": None,
                "best_dive_id": None,
                "best_dive_avg": None,
                "grade": None
            }
            dives_with_scores = [
                {
                    "dive_number": dive_number,
                    "average_score": details["average_score"],
                    "count": details["count"]
                }
                for dive_number, details in dives_data["dives"].items()
                if details["count"] > 0  # Consider only dives with performances
            ]
            top_dives = sorted(dives_with_scores, key=lambda x: x["average_score"], reverse=True)[:2]
            if top_dives:
                total_count = sum(dive["count"] for dive in top_dives)
                weighted_sum = sum(dive["average_score"] * dive["count"] for dive in top_dives)
                combined_average = weighted_sum / total_count if total_count else 0
                best_dive = top_dives[0]
                grade = (combined_average / max_points[event]) * 10 if event in max_points else None
                rankings[event][direction] = {
                    "top_2_avg": round(combined_average, 2),
                    "best_dive_id": best_dive["dive_number"],
                    "best_dive_avg": round(best_dive["average_score"], 2),
                    "grade": round(grade, 1) if grade is not None else None
                }
                if grade is not None:
                    event_grade_sum += grade
                    event_grade_count += 1
            else:
                rankings[event][direction] = {
                    "top_2_avg": 0,
                    "best_dive_id": None,
                    "best_dive_avg": 0,
                    "grade": 0
                }
        
        # Calculate the average grade for the event
        if event_grade_count > 0:
            event_average_grade = event_grade_sum / event_grade_count
            event_grades[event] = round(event_average_grade, 1)
            total_grade_sum += event_average_grade
            total_grade_count += 1

    # Calculate the overall average grade
    overall_average_grade = (total_grade_sum / total_grade_count) if total_grade_count else 0

    # Add the event averages to the rankings
    for event in event_grades:
        rankings[event]["average_grade"] = event_grades[event]
    
    # Add the overall average grade to the rankings
    rankings["overall_average_grade"] = round(overall_average_grade, 1)

    return rankings

async def dive_scores(diver_name):
    diver_number = get_diver_number(diver_name)
    async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as session:
        dive_list = await fetch_dive_heights(session, diver_number)
        tasks = [fetch_scores_for_dive_height(session, diver_number, dive, height) for dive, height in dive_list]
        results = await asyncio.gather(*tasks)
        
        # Combine results from all tasks into a single JSON structure
        combined_json_data = {}
        for result in results:
            for event, directions in result.items():
                if event not in combined_json_data:
                    combined_json_data[event] = {}
                for direction, dives in directions.items():
                    if direction not in combined_json_data[event]:
                        combined_json_data[event][direction] = {"dives": {}}
                    for dive, details in dives["dives"].items():
                        if dive not in combined_json_data[event][direction]["dives"]:
                            combined_json_data[event][direction]["dives"][dive] = details
                        else:
                            combined_json_data[event][direction]["dives"][dive]["performance"] += details["performance"]
        
        # Add count and average score for each dive
        add_count_and_average(combined_json_data)
        
        # Calculate rankings based on the top 2 dives
        rankings = calculate_rankings(combined_json_data)
        
        # Include rankings in the wrapped JSON data
        wrapped_json_data = {
            "name": diver_name,
            "id": diver_number,
            "events": combined_json_data,
            "rankings": rankings
        }

        # Write to JSON file
        with open(f'divers/{diver_number}.json', 'w') as json_file:
            json.dump(wrapped_json_data, json_file, ensure_ascii=False, indent=2)

        return wrapped_json_data

dd_data = pd.read_csv('dd.csv')
dd_lookup = {(row['Dive'], str(row['Height'])): row['DD'] for index, row in dd_data.iterrows()}


def recalculate_and_save_rankings(directory):
    if not os.path.exists(directory):
        print(f"Directory '{directory}' does not exist.")
        return

    json_files = [f for f in os.listdir(directory) if f.endswith('.json')]
    if not json_files:
        print("No JSON files found in the directory.")
        return

    for file_name in json_files:
        file_path = os.path.join(directory, file_name)
        with open(file_path, 'r') as json_file:
            try:
                data = json.load(json_file)
                events_data = data.get('events', {})
                
                # Recalculate rankings
                new_rankings = calculate_rankings(events_data)

                # Update the JSON data with the new rankings
                data['rankings'] = new_rankings

                # Write the updated data back to the JSON file
                with open(file_path, 'w') as updated_json_file:
                    json.dump(data, updated_json_file, ensure_ascii=False, indent=2)

                print(f"Updated rankings for {file_name}")
            except json.JSONDecodeError:
                print(f"Error decoding JSON in file: {file_name}")



def create_diver_json(divername):
    wrapped_json_data = asyncio.run(dive_scores(divername))
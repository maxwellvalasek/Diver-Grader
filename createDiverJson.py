import asyncio
import aiohttp
import httpx
from bs4 import BeautifulSoup, SoupStrainer
import csv
import re
import time
from collections import defaultdict

# Global timing dictionary to store timing data
timing_stats = defaultdict(float)

# --- Setup Patterns and Lookups ---
MONTH_MAP = {
    'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', 'May': '05',
    'Jun': '06', 'Jul': '07', 'Aug': '08', 'Sep': '09', 'Oct': '10',
    'Nov': '11', 'Dec': '12'
}
date_pattern = re.compile(
    r'(\bJan\b|\bFeb\b|\bMar\b|\bApr\b|\bMay\b|\bJun\b|'
    r'\bJul\b|\bAug\b|\bSep\b|\bOct\b|\bNov\b|\bDec\b)\s+'
    r'(\d{1,2}),\s+(\d{4})'
)



def extract_name_gender_age(html_text):
    name_match = re.search(r"<strong>Name: </strong>([^<]+)<br><strong>", html_text)
    gender_match = re.search(r"Gender: </strong>([MF])<br><strong>", html_text)
    age_match = re.search(r"Age: </strong>(\d+)<br><strong>", html_text)
    return (
        name_match.group(1) if name_match else "Name not found",
        gender_match.group(1) if gender_match else "Gender not found",
        age_match.group(1) if age_match else "Age not found"
    )

def extract_first_date(text):
    match = date_pattern.search(text)
    if match:
        month, day, year = match.groups()
        return f"{year}-{MONTH_MAP[month]}-{day.zfill(2)}"
    return None

def add_count_and_average(json_data):
    for event, directions in json_data.items():
        for direction, dives in directions.items():
            for dive, details in dives["dives"].items():
                performances = details["performance"]
                count = len(performances)
                avg_score = sum(p["score"] for p in performances) / count if count > 0 else 0
                details["count"] = count
                details["average_score"] = round(avg_score, 2)

def transform_event_and_height(original_height):
    if original_height == '1':
        return '1 meter', '1'
    if original_height == '3':
        return '3 meter', '3'
    if original_height == '5':
        return 'platform', '5'
    if original_height in ['7', '7.5']:
        return 'platform', '7.5'
    if original_height == '10':
        return 'platform', '10'
    return 'unknown', original_height

async def fetch_page(session, url, **params):
    start_time = time.time()
    headers = {
        "Accept-Encoding": "gzip, deflate",
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Connection": "keep-alive"
    }
    
    # Log the request
    
    # For httpx, we need to await the get() call directly
    response = await session.get(url, params=params, headers=headers)
    content = response.text
    duration = time.time() - start_time
    return content, duration

# Add this new function for optimized parsing
def partial_html_parse(html):
    strainer = SoupStrainer("table", attrs={"width": "100%"})
    return BeautifulSoup(html, "html.parser", parse_only=strainer).find("table")

def partial_profile_parse(html):
    strainer = SoupStrainer("tr", attrs={"bgcolor": True})
    return BeautifulSoup(html, "html.parser", parse_only=strainer).find_all("tr")

async def fetch_diver_scores(session, diver_number, dive, height):
    local_timing = {
        'fetch_page': 0,
        'parse_html': 0,
        'process_data': 0,
        'fetch_dive_scores_total': 0
    }
    start_time = time.time()
    
    # Fetch page timing
    api_height = "7" if height == "7.5" else height
    html, fetch_duration = await fetch_page(
        session,
        "https://secure.meetcontrol.com/divemeets/system/diversdives.php",
        dvrnum=diver_number,
        height=api_height,
        dive=dive
    )
    local_timing['fetch_page'] = fetch_duration
    
    if not html:
        local_timing['fetch_dive_scores_total'] = time.time() - start_time
        return {}, local_timing

    # Parse HTML timing - using optimized parsing
    parse_start = time.time()
    table = partial_html_parse(html)
    local_timing['parse_html'] = time.time() - parse_start
    
    if not table:
        local_timing['fetch_dive_scores_total'] = time.time() - start_time
        return {}, local_timing

    # Process data timing
    process_start = time.time()
    event = "Platform" if height in ["5", "7", "7.5", "10"] else f"{height} Meter"
    direction = {
        '1': 'Front',
        '2': 'Back',
        '3': 'Reverse',
        '4': 'Inward',
        '5': 'Twister',
        '6': 'Armstand'
    }.get(dive[0], "Unknown")
    
    results = {}
    results.setdefault(event, {})
    results[event].setdefault(direction, {"dives": {}})
    if dive not in results[event][direction]["dives"]:
        results[event][direction]["dives"][dive] = {
            "height": height,
            "performance": [],
            "dive_number": dive
        }

    for row in table.find_all('tr')[3:]:
        cells = row.find_all('td')
        if len(cells) < 2:
            continue
        event_info = cells[0].text.strip()
        score = float(cells[1].text.strip())
        strong_tag = cells[0].find('strong')
        meet_name = strong_tag.get_text(strip=True) if strong_tag else 'Unknown Meet'
        date = extract_first_date(event_info)
        
        results[event][direction]["dives"][dive]["performance"].append({
            "date": date,
            "score": score,
            "meet": meet_name
        })
    local_timing['process_data'] = time.time() - process_start
    
    # Total timing
    local_timing['fetch_dive_scores_total'] = time.time() - start_time
    return results, local_timing

async def build_events_data(session, diver_number):
    local_timing = {'fetch_page': 0, 'fetch_dive_scores_total': 0, 'parse_html': 0}
    start_time = time.time()
    
    profile_html, fetch_duration = await fetch_page(
        session,
        "https://secure.meetcontrol.com/divemeets/system/profile.php",
        number=diver_number
    )
    local_timing['fetch_page'] += fetch_duration
    
    if not profile_html:
        return {}, "Unknown", "Unknown", "0", local_timing

    parse_start = time.time()
    name, gender, age = extract_name_gender_age(profile_html)
    rows = partial_profile_parse(profile_html)
    local_timing['parse_html'] = time.time() - parse_start
    
    dive_heights = [
        (
            row.find_all('td')[0].text.strip(),
            row.find_all('td')[1].text.replace("M", "").strip()
        )
        for row in rows
    ]
    
    tasks = [
        fetch_diver_scores(session, diver_number, dive, height)
        for dive, height in dive_heights
    ]
    results = await asyncio.gather(*tasks)

    # Combine results and timing data
    combined = {}
    for item, dive_timing in results:
        # Aggregate timing data
        for key, value in dive_timing.items():
            local_timing[key] = local_timing.get(key, 0) + value
            
        # Combine dive data
        for event, directions in item.items():
            combined.setdefault(event, {})
            for direction, dive_dict in directions.items():
                combined[event].setdefault(direction, {"dives": {}})
                for dive_id, details in dive_dict["dives"].items():
                    if dive_id not in combined[event][direction]["dives"]:
                        combined[event][direction]["dives"][dive_id] = details
                    else:
                        combined[event][direction]["dives"][dive_id]["performance"] += details["performance"]

    add_count_and_average(combined)
    local_timing['build_events_total'] = time.time() - start_time
    return combined, name, gender, age, local_timing

limits = httpx.Limits(
    max_keepalive_connections=50,
    max_connections=100
)
async def dive_scores(diver_number):
    # Use HTTP/2 enabled client with connection pooling
    async with httpx.AsyncClient(http2=True, timeout=30.0, limits=limits) as session:
        start_time = time.time()
        events_data, name, gender, age, timing_data = await build_events_data(session, diver_number)
        
        # Convert the data into CSV rows
        csv_rows = []
        for event_key, directions in events_data.items():
            for direction_key, dive_dict in directions.items():
                for dive_id, details in dive_dict["dives"].items():
                    original_height = details["height"]
                    csv_event, csv_height = transform_event_and_height(original_height)
                    
                    # Retrieve the actual dive number (e.g., 203B) from
                    # the 'dive_number' key we stored above
                    dive_number = details.get("dive_number", dive_id)  # <-- Using stored dive number

                    for perf in details["performance"]:
                        row = {
                            "name": name,
                            "gender": gender,
                            "age": age,
                            "diver_id": diver_number,  # Diver's unique ID from the site
                            "dive_number": dive_number,  # <-- The actual dive, e.g. 203B
                            "event": csv_event,
                            "height": csv_height,
                            "date": perf["date"],
                            "score": perf["score"],
                            "meet": perf["meet"]
                        }
                        csv_rows.append(row)

        # Write CSV
        csv_start = time.time()
        fieldnames = [
            "name",
            "gender",
            "age",
            "diver_id",
            "dive_number",   # New column for the actual dive number
            "event",
            "height",
            "date",
            "score",
            "meet"
        ]
        csv_filename = f"divers/{diver_number}.csv"
        with open(csv_filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)
        timing_data['csv_write'] = time.time() - csv_start
        
        total_time = time.time() - start_time
        timing_data['total_time'] = total_time
        
        # Print timing statistics
        print(f"\nTiming Statistics for {name} (ID: {diver_number}):")
        print("-" * 50)
        for operation, duration in timing_data.items():
            percentage = (duration / total_time) * 100
            print(f"{operation:<25}: {duration:6.2f}s ({percentage:5.1f}%)")

def create_diver_csv(divernumber):
    # Clear previous timing stats
    timing_stats.clear()
    asyncio.run(dive_scores(divernumber))

create_diver_csv("32577")

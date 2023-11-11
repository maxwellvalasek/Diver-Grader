import requests
import re

# Replace 'your_url_here' with the URL of the web page you want to scrape
url = 'https://secure.meetcontrol.com/divemeets/system/meetresultsext.php?meetnum=5856'


try:
    response = requests.get(url)
    if response.status_code == 200:
        html_content = response.text
        
        # Use a regular expression to find all matches of 'number=\d\d\d\d\d' in the HTML content
        numbers = re.findall(r'number=(\d{5})', html_content)
        
        if numbers:
            # Specify the name of the text file where you want to save the numbers
            output_file = 'extracted_numbers2019ncw.txt'
            
            # Write the numbers to the text file, one per line
            with open(output_file, 'w') as file:
                for number in numbers:
                    file.write(number + '\n')
            
            print(f"Extracted numbers saved to '{output_file}'")
        else:
            print("No matching numbers found in the HTML content.")
    else:
        print(f"Failed to retrieve the web page. Status code: {response.status_code}")
except requests.exceptions.RequestException as e:
    print(f"An error occurred: {e}")
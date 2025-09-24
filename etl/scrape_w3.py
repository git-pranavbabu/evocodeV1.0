# etl/scrape_w3.py
import requests
from bs4 import BeautifulSoup
import os
import time

# List of W3Schools Python tutorial pages to scrape
URLS = [
    "https://www.w3schools.com/python/python_intro.asp",
    "https://www.w3schools.com/python/python_syntax.asp",
    "https://www.w3schools.com/python/python_variables.asp",
    "https://www.w3schools.com/python/python_datatypes.asp",
    "https://www.w3schools.com/python/python_numbers.asp",
    "https://www.w3schools.com/python/python_strings.asp",
    "https://www.w3schools.com/python/python_booleans.asp",
    "https://www.w3schools.com/python/python_operators.asp",
    "https://www.w3schools.com/python/python_lists.asp",
    "https://www.w3schools.com/python/python_tuples.asp",
    "https://www.w3schools.com/python/python_sets.asp",
    "https://www.w3schools.com/python/python_dictionaries.asp",
    "https://www.w3schools.com/python/python_conditions.asp",
    "https://www.w3schools.com/python/python_while_loops.asp",
    "https://www.w3schools.com/python/python_for_loops.asp",
    "https://www.w3schools.com/python/python_functions.asp",
]

# Directory to save the cleaned text
OUTPUT_DIR = "etl/scraped_content"

def scrape_and_clean(url: str, session: requests.Session) -> str:
    """Scrapes a single URL and returns cleaned text content."""
    try:
        headers = {'User-Agent': 'EvocodeScraper/1.0'}
        response = session.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes

        soup = BeautifulSoup(response.text, 'lxml')

        # Find the main content div
        main_content = soup.find('div', id='main')

        if not main_content:
            return ""

        # Remove unwanted elements like nav buttons, ads, etc.
        for element in main_content.find_all(['div', 'a'], {'class': ['w3-clear', 'nextprev']}):
            element.decompose()

        return main_content.get_text(separator='\n', strip=True)

    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return ""

def main():
    """Main function to run the scraper."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    with requests.Session() as session:
        for url in URLS:
            print(f"Scraping: {url}")
            cleaned_text = scrape_and_clean(url, session)

            if cleaned_text:
                # Create a simple filename from the URL
                filename = url.split('/')[-1].replace('.asp', '.txt')
                filepath = os.path.join(OUTPUT_DIR, filename)

                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(cleaned_text)
                print(f"  -> Saved to {filepath}")

            # Be a good internet citizen: wait a second between requests
            time.sleep(1)

if __name__ == "__main__":
    main()
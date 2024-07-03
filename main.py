import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
import stat

# Function to fetch webpage content using Selenium
def fetch_webpage(url):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # Specify the path to the ChromeDriver
    chrome_driver_path = os.path.join(os.getcwd(), 'chromedriver.exe')
    
    # Set executable permissions for the ChromeDriver
    os.chmod(chrome_driver_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    
    service = Service(executable_path=chrome_driver_path)
    driver = webdriver.Chrome(service=service, options=options)
    driver.get(url)
    time.sleep(1)

    # Click the "Show More" button until it disappears
    while True:
        try:
            show_more_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.LINK_TEXT, "Show More"))
            )

            show_more_button.click()
            time.sleep(0.5)  # Wait for 0.5 seconds
        except Exception as e:
            print("No more 'Show More' button found or an error occurred:")
            break

    # Wait for the dynamic content to load
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )

    html = driver.page_source
    driver.quit()
    return html

# Function to parse the HTML content and extract job links
def parse_jobs(html):
    soup = BeautifulSoup(html, 'html.parser')
    links = soup.find_all('a', href=True)
    jobs = [a['href'] for a in links if a['href'].startswith("https://boards.greenhouse.io/")]
    return jobs

# Function to read job openings from a file
def read_job_openings(filename):
    if not os.path.exists(filename):
        return set()
    with open(filename, 'r') as file:
        return set(line.strip() for line in file)

# Function to write job openings to a file
def write_job_openings(filename, job_data):
    with open(filename, 'w') as file:
        for title, link in job_data:
            file.write(f"{title}\n{link}\n")

# Function to fetch job titles from stored links
def fetch_job_titles(links):
    job_data = []
    for job in links:
        response = requests.get(job)
        soup = BeautifulSoup(response.content, 'html.parser')
        app_title = soup.find(class_='app-title')
        if app_title:
            title = app_title.get_text().strip()
            print(f"Title: {title}, Link: {job}")
            job_data.append((title, job))
        else:
            print(f"Job title not found for {job}")
    return job_data

def main():
    url = "https://www.headout.com/careers/"
    filename = "New.txt"

    webpage = fetch_webpage(url)
    current_jobs = set(parse_jobs(webpage))
    previous_jobs = read_job_openings(filename)

    new_jobs = current_jobs - previous_jobs

    if new_jobs:
        for job in new_jobs:
            print(f"New job opening {job} has appeared")

    # Fetch job titles from stored links
    job_data = fetch_job_titles(current_jobs)

    # Write job titles and links to the file
    write_job_openings(filename, job_data)
    print("Finished fetching and saving job openings")

if __name__ == "__main__":
    main()

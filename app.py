import os
import sys
import time
import threading
import requests
import redis
from flask import Flask, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from mailersend import emails
from tenacity import retry, stop_after_attempt, wait_fixed

app = Flask(__name__)

# Read the REDIS_URL from the environment
REDIS_URL = os.getenv('REDIS_URL', 'redis://red-cq76dg6ehbks739bf0ag:6379')

# Initialize Redis client
redis_client = redis.StrictRedis.from_url(REDIS_URL)

def fetch_webpage(url):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(options=options)
    driver.get(url)
    time.sleep(1)

    while True:
        try:
            show_more_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.LINK_TEXT, "Show More"))
            )
            show_more_button.click()
            time.sleep(2)
        except Exception:
            break

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )

    html = driver.page_source
    driver.quit()
    return html

def parse_jobs(html):
    soup = BeautifulSoup(html, 'html.parser')
    links = soup.find_all('a', href=True)
    jobs = [a['href'] for a in links if a['href'].startswith("https://boards.greenhouse.io/")]
    return jobs

def fetch_job_titles(links):
    map_title_link = {}
    for job in links:
        response = requests.get(job)
        soup = BeautifulSoup(response.content, 'html.parser')
        app_title = soup.find(class_='app-title')
        if app_title:
            title = app_title.get_text().strip()
            map_title_link[title] = job
    return map_title_link


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def safe_hgetall(client, key):
    return client.hgetall(key)


def update_jobs_in_redis(web_fetched_jobs):
    try:
        # Fetch old jobs with retry logic
        old_redis_jobs = safe_hgetall(redis_client, "old_redis_jobs")
        if not old_redis_jobs:
            print("Warning: No old jobs found in Redis.")
            old_redis_jobs = {}
            return old_redis_jobs

        old_redis_jobs = {key.decode('utf-8'): value.decode('utf-8') for key, value in old_redis_jobs.items()}
        new_jobs = {}
        for key in web_fetched_jobs:
            if key not in old_redis_jobs:
                new_jobs[key]= web_fetched_jobs[key]
        
        # Remove keys from old_redis_jobs that are not in web_fetched_jobs
        jobs_removed = []
        for key in old_redis_jobs:
            if key not in web_fetched_jobs:
                jobs_removed.append(key)

        if new_jobs:
            redis_client.hset("all_jobs", mapping=new_jobs)
            redis_client.hset("old_redis_jobs", mapping=new_jobs)
            print("New jobs found and added to Redis:")
            for title, link in new_jobs.items():
                print(f"{title}: {link}")
        else:
            print("No new jobs found.")

        if (len(jobs_removed)>7):
            return new_jobs

        if jobs_removed:
            redis_client.hdel("old_redis_jobs", *jobs_removed)
            print("Jobs removed from old_redis_jobs in Redis:", jobs_removed)
        else:
            print("No old jobs were removed.")

        return new_jobs
    
    except redis.exceptions.ConnectionError as e:
        print(f"Redis connection error: {e}")
        return {}
    except redis.exceptions.TimeoutError as e:
        print(f"Redis timeout error: {e}")
        return {}
    except Exception as e:
        print(f"An error occurred: {e}")
        return {}

def sendmail(new_jobs):
    api_key = os.getenv('MAILER_API_KEY')
    mailer = emails.NewEmail(api_key)
    mail_body = {}
    
    mail_from = {
        "name": "python",
        "email": os.getenv('MAIL_FROM'),
    }
    
    recipients = [
        {
            "name": "King",
            "email": os.getenv('MAIL_TO'),
        }
    ]
    
    html_content = "<html><body><h3>New Jobs Found</h3><ul>"
    for key, value in new_jobs.items():
        html_content += f"<li><strong>{key}:</strong> {value}</li>"
    html_content += "</ul></body></html>"

    mailer.set_mail_from(mail_from , mail_body)
    mailer.set_mail_to(recipients, mail_body)
    mailer.set_subject("New one", mail_body)
    mailer.set_html_content(html_content, mail_body)
    mailer.set_plaintext_content("This is the text content", mail_body)
    
    response = mailer.send(mail_body)
    if response.status_code == 200:
        print("Emails sent successfully")
    else:
        print("Emails may not have sent. Response was: ", response.status_code)


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def fetch_url_with_retry(url, timeout=10):
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()  # Raise an HTTPError if the response was unsuccessful
    return response


@app.route('/trigger', methods=['GET'])
def trigger_script():
    def background_task():
        try:
            url = "https://www.headout.com/careers/"

            try:
                response = fetch_url_with_retry(url)
            except requests.exceptions.RequestException as e:
                print(f"Failed to fetch the webpage: {e}")
                return
            
            print("fetching all jobs links")
            webpage = fetch_webpage(url)
            map_web_fetched_jobs = fetch_job_titles(parse_jobs(webpage))
            if len(map_web_fetched_jobs) <= 0:
                print("Headout careers website is not accessible.")
                return

            print("updating redis")
            new_jobs = update_jobs_in_redis(map_web_fetched_jobs)
            if len(new_jobs) > 0:
                print("Now trying to send mails for new job openings.")
                sendmail(new_jobs)
            print("Script executed successfully.")
        except Exception as e:
            print(f"An error occurred: {e}")

    # Start the background task in a new thread
    thread = threading.Thread(target=background_task)
    thread.start()

    # Return a success response immediately
    return jsonify({"status": "success", "message": "Script execution started."}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)


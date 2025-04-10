import random
import requests
import os
import csv
import logging
from collections import deque
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
    WebDriverException,
)
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from company_data import Get_Company_data
# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
SESSION_DIR = "sessions"
# User-Agent List
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]

class WebScraper:
    def __init__(self, base_url, max_urls, file_path, headless=True, timeout=30, max_workers=6):
        self.base_url = base_url
        self.max_urls = max_urls
        self.headless = headless
        self.visited_urls = set()
        self.to_scrape = deque([base_url]) 
        self.csv_filename = "company_data.csv" 
        self.content_hashes = set()
        self.timeout = timeout
        self.lock = Lock()
        self.max_workers = max_workers       
        self.existing_companies = set()  # ✅ Fix: Initialize this first!

        if os.path.exists(self.csv_filename):
            with open(self.csv_filename, "r", encoding="utf-8") as f:
                for line in f.readlines()[1:]:  # Skip header
                    try:
                        name = line.strip().split(",")[0].strip('"')
                        self.existing_companies.add(name)
                    except:
                        continue

    def initialize_driver(self):
        """Initializes Selenium WebDriver with stealth options."""
        options = Options()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-gpu")
        options.add_argument("--headless=new") if self.headless else None
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        return webdriver.Remote(
            command_executor="http://localhost:4444/wd/hub",
            options=options
        )
        
    def check_redirect(self,url):
        
        try: 
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url  
            response = requests.get(url, allow_redirects=True)
            final_url = response.url
            if final_url in self.visited_urls:
                print(f"{url} redirects to a known URL: {final_url}")
                return 0
            else:
                print(f"cleared redirection check")
            return 1
        except requests.RequestException as e:
            print(f"Error: {e}")
  
    def save_to_csv(self, data):
        """Appends a row of company data to a CSV file if it's not a duplicate."""
        company_name = data[0]

        if company_name in self.existing_companies:
            print(f"Duplicate found: {company_name}, skipping save.")
            return

        file_exists = os.path.isfile(self.csv_filename)
        with self.lock:
            with open(self.csv_filename, mode="a", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                if not file_exists:
                    writer.writerow(["Company Name", "Company Data"])  # Header
                writer.writerow(data)
                self.existing_companies.add(company_name)  # Update memory to avoid writing again

    def Infinite_Scroll(self,driver):
        infinite_scroll = driver.find_element(By.XPATH, "/html/body/div[1]/main/div[3]/div/div/div/div")

        # Get the 3 direct divs
        parent_divs = infinite_scroll.find_elements(By.XPATH, "./div")
        max=0
        # Loop through each parent div
        for i, div in enumerate(parent_divs, start=1):
            print(f"\n{i}st div:")

            # Find all <a> tags inside this div
            a_tags = div.find_elements(By.TAG_NAME, "a")
            # Loop through each a tag
            for j, a_tag in enumerate(a_tags, start=1):
                if(max<3):
                    try:
                        # Extract the span with company name
                        span = a_tag.find_element(By.XPATH, ".//div/div/div[2]/div/span[1]")
                        company_name = span.text.strip()

                        # Extract the link from the a tag
                        link = a_tag.get_attribute("href")

                        print(f"{company_name}: {link}")
                        company_data=Get_Company_data(link,1,1234)
                        print(company_data)
                        # print("==============================================")
                        # Inside Infinite_Scroll
                        self.save_to_csv([company_name, company_data])
                        

                    except Exception as e:
                        print(f"  Link {j}: [span or href not found]")
        
                    
    def fetch_page(self, url):
        """Scrapes a webpage and ensures content is not duplicated."""
        print("=====>>>Started Scrapping<<<=====",url)
        driver = None
        try:
            logging.info(f"Scraping {url}")
            driver = self.initialize_driver()
            driver.get(url)

            WebDriverWait(driver, self.timeout).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))  # Ensure page is loaded
                )
            
            self.Infinite_Scroll(driver)
            
            driver.quit()
        except (TimeoutException, WebDriverException) as e:
            logging.error(f"Error scraping {url}: {e}")
            if driver:
                driver.quit()


    def scrape_website(self):
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while self.to_scrape and len(self.visited_urls) < self.max_urls:
                futures = {}
                while self.to_scrape and len(futures) < self.max_workers:
                    url = self.to_scrape.popleft()
                    if url not in self.visited_urls and self.check_redirect(url):
                        self.visited_urls.add(url)
                        futures[executor.submit(self.fetch_page, url)] = url
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        logging.error(f"Error during scraping: {e}")


def save_processed_url(processed_file, url):
    """Save a processed URL to the session file."""
    with open(processed_file, "a", encoding="utf-8") as f:
        f.write(url + "\n")
        
def get_session_files(session_id):
    """Return file paths for storing scraped data and processed URLs"""
    return os.path.join(SESSION_DIR, f"scraped_data_{session_id}.txt")

def Get_Company_name_link(url,max_urls,session_id):
    #file_path=get_session_files(session_id)
    print(f"URL: {url}")
    file_path="results.txt"
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url  
    scraper = WebScraper(url, max_urls,file_path,headless=True)#call for Web Crawler
    scraper.scrape_website()

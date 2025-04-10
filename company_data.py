import time
import random
import requests
import hashlib
import os
import re
import logging
from collections import deque
from urllib.parse import urlparse
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

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
SESSION_DIR = "sessions"
# User-Agent List
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]

class WebScraper:
    def __init__(self, base_url, max_urls,file_path, headless=True,timeout=30,max_workers=6):
        self.base_url = base_url
        self.max_urls = max_urls
        self.headless = headless
        self.visited_urls = set()
        self.to_scrape = deque([base_url]) 
        self.content_hashes = set()
        self.timeout = timeout
        self.lock = Lock()
        self.max_workers = max_workers       

            
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
        
                
    def Company_data(self,driver):
        print("=======infinite scroll========")
        try:
            target_div = driver.find_element(By.XPATH, "/html/body/div[1]/main/div[2]/div/div[1]/div[4]")
            text_content = target_div.text.strip()
            #print("Extracted Text:\n", text_content)
            return text_content
        
        except Exception as e:
            print("Could not find or extract the element:", e)
            return None    
            
    def fetch_page(self, url):
        """Scrapes a webpage and ensures content is not duplicated."""
        print("=====>>>Started Scrapping<<<=====",url)
        driver = None
        try:
            logging.info(f"Scraping {url}")
            driver = self.initialize_driver()
            #driver.set_page_load_timeout(15)
            driver.get(url)
            WebDriverWait(driver, self.timeout).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))  # Ensure page is loaded
                )
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
           # WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            company_data=self.Company_data(driver)
            driver.quit()
            return company_data
        except (TimeoutException, WebDriverException) as e:
            logging.error(f"Error scraping {url}: {e}")
            if driver:
                driver.quit()
            return None

    def scrape_website(self):
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while self.to_scrape and len(self.visited_urls) < self.max_urls:
                futures = {}
                while self.to_scrape and len(futures) < self.max_workers:
                    url = self.to_scrape.popleft()
                    if url not in self.visited_urls:
                        self.visited_urls.add(url)
                        futures[executor.submit(self.fetch_page, url)] = url
                for future in as_completed(futures):
                    url = futures[future]
                    try:
                        result = future.result()  # <- this gets the value returned by fetch_page
                        if result is not None:
                            return result
                    except Exception as e:
                        logging.error(f"Error during scraping {url}: {e}")
                        return None

def get_session_files(session_id):
    """Return file paths for storing scraped data and processed URLs"""
    return os.path.join(SESSION_DIR, f"scraped_data_{session_id}.txt")

def Get_Company_data(url,max_urls,session_id):
    #file_path=get_session_files(session_id)
    print(f"URL: {url}")
    file_path="results.txt"
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url  
    scraper = WebScraper(url, max_urls,file_path,headless=True)#call for Web Crawler
    company_data=scraper.scrape_website()
    return company_data

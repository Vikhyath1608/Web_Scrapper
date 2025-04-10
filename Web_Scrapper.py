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
from Infinite_Scroll_Iframe import Get_Company_name_link
# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
SESSION_DIR = "sessions"
# User-Agent List
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]
#keywords for Cookie accept button 
COOKIE_BUTTON_TEXTS = [
    'accept', 'close','Save Choices','agree', 'ok', 'allow', 'i accept', 'got it', 'continue', 'yes','Accept All',
    'proceed', 'consent', 'enable', 'accept all', 'allow all', 'accept cookies',
    'allow cookies', 'agree to all', 'accept and close', 'accept and continue',
    'understood', 'accept terms', 'agree and proceed', 'confirm', 'i agree',
    'yes, accept', 'yes, i agree', 'allow tracking', 'accept & proceed',
    'accept & continue', 'ok, got it', 'yes, continue', 'allow all cookies',
    'enable cookies', 'agree & continue', 'yes, i accept', 'agree & proceed',
    'accept settings', 'agree & close', 'i understand', 'consent to all',
    'approve', 'agree to terms', 'grant permission', 'accept policy',
    'confirm & continue', 'allow & proceed', 'okay', 'sure', 'yes, allow',
    'yes, i consent', 'accept preferences', 'okay, i accept', 'ok, accept',
    'enable tracking', 'ok, agree', 'accept & close', 'yes, enable',
    'allow everything', 'approve all', 'ok, i agree', 'accept privacy terms',
    'allow necessary cookies', 'accept all tracking', 'yes, approve', 'accept usage',
    'grant access', 'i approve', 'confirm selection', 'yes, proceed',
    'allow and proceed', 'accept required', 'enable all', 'accept analytics cookies',
    'okay, continue', 'approve and continue', 'yes, allow all', 'accept marketing cookies',
    'consent & continue', 'i acknowledge', 'okay, accept all', 'agree to cookies',
    'continue with cookies', 'understand and accept', 'review and accept', 
    'set preferences', 'save and accept', 'confirm consent', 'accept site cookies',
    'allow functionality cookies', 'enable necessary settings', 'acknowledge & accept',
    'agree to usage', 'yes, confirm', 'agree to all terms', 'accept & proceed to site',
    'accept browsing settings', 'allow personalization', 'allow ad tracking',
    'okay, proceed', 'yes, go ahead', 'yes, confirm my choice', 'accept recommended settings',
    'accept & finalize', 'apply and accept', 'confirm my preferences', 'accept legal terms',
    'continue with settings', 'acknowledge terms', 'accept session cookies', 'accept all options',
    'proceed with cookies', 'okay, i agree to this', 'agree to data usage', 'allow all tracking',
    'accept full access', 'yes, apply settings', 'enable all features', 'consent and continue'
]
class WebScraper:
    def __init__(self, base_url, max_urls,file_path, headless=True,timeout=30,max_workers=6):
        self.base_url = base_url
        self.max_urls = max_urls
        self.headless = headless
        self.visited_urls = set()
        self.to_scrape = deque([base_url]) 
        self.output_file = "result.txt" 
        self.visited_links_file = "visited_links.txt" 
        self.content_hashes = set()
        self.timeout = timeout
        self.lock = Lock()
        self.max_workers = max_workers       
        if not os.path.exists(self.output_file):
            open(self.output_file, "w").close()
        if not os.path.exists(self.visited_links_file):
            open(self.visited_links_file, "w").close()
            
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
    def accept_cookies(self, driver):
        """Clicks the 'Accept Cookies' button if found, then clicks 'Save Choices' if present."""
        try:
            # Locate and click the 'Accept Cookies' button
            lower_case_texts = [text.lower() for text in COOKIE_BUTTON_TEXTS]
            xpath_query = " | ".join(
                [f"//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text}')]" 
                 for text in lower_case_texts]
            )
            
            buttons = WebDriverWait(driver, 5).until(
                EC.presence_of_all_elements_located((By.XPATH, xpath_query))
            )
            
            if not buttons:
                logging.info("No cookie consent button found on this page.")
                return False
            
            for button in buttons:
                try:
                    WebDriverWait(driver, 5).until(EC.element_to_be_clickable(button))
                    button.click()
                    time.sleep(2)
                    logging.info("Cookies accepted successfully.")
                    break  # Exit loop after clicking the first matching button
                except (ElementClickInterceptedException, StaleElementReferenceException):
                    continue
            
            # Locate and click the 'Save Choices' button if present
            save_choices_xpath = "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'save choices')or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'reject all')]"
            save_choices_buttons = driver.find_elements(By.XPATH, save_choices_xpath)
            
            for save_button in save_choices_buttons:
                try:
                    WebDriverWait(driver, 5).until(EC.element_to_be_clickable(save_button))
                    save_button.click()
                    time.sleep(2)
                    logging.info("Save Choices clicked successfully.")
                    break
                except (ElementClickInterceptedException, StaleElementReferenceException):
                    continue
            
        except (NoSuchElementException, TimeoutException):
            logging.info("No cookie consent popup detected.")
        
        return False
    
    def click_read_more_buttons(self, driver):
        """Finds and interacts with dynamically loaded hidden content if it stays on the same page."""
        expanded_count = 0
        elements_to_check = [{
            "tag": "button",
            "text": [
                "Read More", "Show More", "Expand", "Learn More", "See More",
                "View More", "Discover More", "Continue Reading", "More Info",
                "Details", "Open", "See Details", "Unfold", "Show Details",
                "Explore", "Get Details", "Full Story", "See Full Text",
                "Reveal", "Show Full Article", "Read Full Article",
                "Keep Reading", "See Full Story", "View Full Post",
                "Click for More", "Find Out More", "Access Full Content",
                "Enlarge", "Read Full Content", "Show Full Description",
                "Get More Information", "Expand Details", "Go Deeper",
                "Continue Exploring", "Dive In", "See Everything",
                "More About This", "Browse More", "Uncover More",
                "Unlock Details", "Gain More Insight", "Dig Deeper",
                "Expand for More", "Load More", "Extend", "Show Complete Text",
                "Read Entire Article", "Show Entire Post", "Keep Exploring",
                "View Complete Info", "Find More", "More Details"
            ]
        }]

        while True:
            found_new = False
            for element in elements_to_check:
                try:
                    buttons = driver.find_elements(By.TAG_NAME, element["tag"])

                    for btn in buttons:
                        try:
                            btn_text = btn.text.strip()
                            if any(keyword.lower() in btn_text.lower() for keyword in element["text"]):
                                logging.info(f"Checking button: {btn_text}")

                                original_url = driver.current_url
                                original_tabs = driver.window_handles
                                driver.execute_script("arguments[0].scrollIntoView();", btn)
                                time.sleep(1)
                                
                                WebDriverWait(driver, 5).until(EC.element_to_be_clickable(btn))
                                btn.click()
                                time.sleep(2)

                                new_tabs = driver.window_handles
                                if len(new_tabs) > len(original_tabs):
                                    logging.info(f"Skipping button '{btn_text}' as it opened a new tab.")
                                    driver.switch_to.window(new_tabs[-1])
                                    driver.close()
                                    driver.switch_to.window(original_tabs[0])
                                elif driver.current_url == original_url:
                                    logging.info(f"Expanded content using button: {btn_text}")
                                    expanded_count += 1
                                    found_new = True
                                else:
                                    logging.info(f"Skipping button '{btn_text}' as it redirected to another page.")
                                    driver.back()
                                    time.sleep(2)
                                
                        except (StaleElementReferenceException, ElementClickInterceptedException, NoSuchElementException):
                            continue
                except NoSuchElementException:
                    pass  
            if not found_new:
                break
        
        logging.info(f"Expanded {expanded_count} hidden elements.")

    def get_internal_links(self, driver):
        """Extracts all internal links from the page."""
        links = set()
        len_href=0
        for link in driver.find_elements(By.TAG_NAME, "a"):
            try:
                href = link.get_attribute("href")
                len_href+=1
                if href and self.is_internal_link(href) and (href not in self.visited_urls) and (href not in links):
                    links.add(href)

            except StaleElementReferenceException:
                continue
        return links
    
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
           

    def is_internal_link(self, url):
        
        def get_domain(url):
            """Extracts the domain and removes 'www.' if present."""
            domain = urlparse(url).netloc.lower()  # Convert to lowercase for consistency
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        return get_domain(url) == get_domain(self.base_url)

    def compute_hash(self, text):
        """Generates a hash of the content to check for duplicates."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    
    def preprocess_text(self,text):
        """Preprocess the unstructured text to clean and normalize it."""
        text = text.strip()  # Remove leading/trailing spaces
        text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces/newlines with a single space
        return text

    def Infinite_Scroll(self,driver):
        print("=======infinite scroll========")
        iframe_container_xpath = "/html/body/div[1]/div/div[3]/div/div/div[2]/div/div/div/div/div/div/div[2]/div/div"

        try:
            container = driver.find_element(By.XPATH, iframe_container_xpath)
            print("✅ Container located!")

            iframe = container.find_element(By.TAG_NAME, "iframe")
            iframe_src = iframe.get_attribute("src")
            print("🔗 Iframe src URL:")
            print(iframe_src)
            Get_Company_name_link(iframe_src,1,1234)
            #print("✅ <iframe> tag found!")
            #print(iframe)
        except NoSuchElementException as e:
            print("❌ Could not locate iframe:", e)
            
    def fetch_page(self, url):
        """Scrapes a webpage and ensures content is not duplicated."""
        print("=====>>>Started Scrapping<<<=====",url)
        driver = None
        try:
            logging.info(f"Scraping {url}")
            driver = self.initialize_driver()
            #driver.set_page_load_timeout(15)
            driver.get(url)
            internal_links = self.get_internal_links(driver)
            self.accept_cookies(driver)
            WebDriverWait(driver, self.timeout).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))  # Ensure page is loaded
                )
            self.click_read_more_buttons(driver)
            #self.scroll_page(driver)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
           # WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            content = driver.find_element(By.TAG_NAME, "body").text
            
            self.Infinite_Scroll(driver)
            cookie_phrases = ["We use cookies", "This website uses cookies", "By continuing, you accept cookies","cookies"]
            filtered_content = "\n".join([line for line in content.split("\n") if not any(phrase in line for phrase in cookie_phrases)])

            content_hash = self.compute_hash(filtered_content)
            if content_hash not in self.content_hashes:
                self.content_hashes.add(content_hash)
                with open(self.output_file, "a", encoding="utf-8") as f:
                    f.write(f"\n===== Scraped Content from {url} =====\n")
                    unstrucured_data=self.preprocess_text(filtered_content)
                    f.write(unstrucured_data[:5000])
                    f.write("\n\n")
                    unstrucured_data="Scraped Content from "+url+" "+unstrucured_data
                    #convert_json(unstrucured_data)
                logging.info(f"Saved scraped content from {url} to file.")
            else:
                logging.info(f"Skipping duplicate content from {url}")

            with open(self.visited_links_file, "a", encoding="utf-8") as f:
                f.write(url + "\n")

           
            driver.quit()
            
            for link in internal_links:
                if link not in self.visited_urls and len(self.visited_urls) < self.max_urls:
                    self.to_scrape.append(link)
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

def Scrap_website(url,max_urls,session_id):
    #file_path=get_session_files(session_id)
    print(f"URL: {url}")
    file_path="results.txt"
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url  
    scraper = WebScraper(url, max_urls,file_path,headless=True)#call for Web Crawler
    scraper.scrape_website()

url="https://www.middleeast-energy.com/en/exhibit/exhibitor-directory.html"
Scrap_website(url,1,1234)
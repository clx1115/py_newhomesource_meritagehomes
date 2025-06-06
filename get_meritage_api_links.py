from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import json
import time
import logging
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
sys.stdout.reconfigure(encoding='utf-8')
logger = logging.getLogger(__name__)

def setup_driver():
    """Set up Chrome driver with appropriate options"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.page_load_strategy = 'eager'
    return webdriver.Chrome(options=chrome_options)

def get_city_links():
    """Get initial city links from Meritage Homes website"""
    url = "https://www.meritagehomes.com/homes"
    driver = setup_driver()
    city_links = []
    
    try:
        logger.info("Starting to fetch initial page...")
        driver.get(url)
        wait = WebDriverWait(driver, 30)
        time.sleep(5)
        
        # Save initial page HTML
        os.makedirs('data', exist_ok=True)
        with open('data/meritage_initial.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        logger.info("Initial page HTML has been saved")
        
        # Parse page to get links
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Find all city-link class elements
        city_elements = soup.find_all('a', class_='city-link')
        for element in city_elements:
            href = element.get('href')
            if href:
                if not href.startswith('http'):
                    href = 'https://www.meritagehomes.com' + href
                if href not in city_links:
                    city_links.append(href)
                    logger.info(f"Found city link: {href}")
        
        logger.info(f"Total city links found: {len(city_links)}")
        return city_links
        
    except Exception as e:
        logger.error(f"Error getting city links: {str(e)}")
        return []
    finally:
        driver.quit()

def get_community_links(city_links):
    """Get community links from each city page"""
    driver = setup_driver()
    community_links = []
    
    try:
        for url in city_links:
            logger.info(f"Processing URL: {url}")
            try:
                driver.get(url)
                time.sleep(5)
                
                # Save each page's HTML
                filename = url.rstrip('/').split('/')[-1] or 'index'
                with open(f'data/meritage_{filename}.html', 'w', encoding='utf-8') as f:
                    f.write(driver.page_source)
                
                # Parse page to get community links
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                # Find all community-horizontal containers
                community_containers = soup.find_all('div', class_='community-horizontal')
                for container in community_containers:
                    # Find button--blue--solid links within each container
                    links = container.find_all('a', class_='button--blue--solid')
                    for link in links:
                        href = link.get('href')
                        if href:
                            if not href.startswith('http'):
                                href = 'https://www.meritagehomes.com' + href
                            if href not in community_links:
                                community_links.append(href)
                                logger.info(f"Found community link: {href}")
            
            except Exception as e:
                logger.error(f"Error processing URL {url}: {str(e)}")
                continue
        
        return list(set(community_links))  # Remove duplicates
    except Exception as e:
        logger.error(f"Error getting community links: {str(e)}")
        return []
    finally:
        driver.quit()

def main():
    try:
        # Get city links
        city_links = get_city_links()
        logger.info(f"Found {len(city_links)} city links")
        
        if not city_links:
            logger.error("No city links found")
            return
        
        # Get community links
        community_links = get_community_links(city_links)
        logger.info(f"Found {len(community_links)} community links")
        
        if not community_links:
            logger.error("No community links found")
            return
        
        # Save links to JSON file
        with open('meritage_links.json', 'w', encoding='utf-8') as f:
            json.dump(community_links, f, indent=2, ensure_ascii=False)
        logger.info("Links have been saved to meritage_links.json")
        
    except Exception as e:
        logger.error(f"Main program execution error: {str(e)}")

if __name__ == "__main__":
    main() 
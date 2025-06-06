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
from datetime import datetime
import re
import argparse
import random

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

def extract_price(text):
    """Extract price from text"""
    if not text:
        return None
    price_match = re.search(r'\$[\d,]+', text)
    return price_match.group(0) if price_match else None

def extract_beds_baths(text):
    """Extract number of beds and baths from text"""
    if not text:
        return None, None
    beds_match = re.search(r'(\d+)\s*(?:Bedroom|Bed|BR)', text)
    baths_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:Bathroom|Bath|BA)', text)
    beds = beds_match.group(1) if beds_match else None
    baths = baths_match.group(1) if baths_match else None
    return beds, baths

def extract_sqft(text):
    """Extract square footage from text"""
    if not text:
        return None
    sqft_match = re.search(r'([\d,]+)\s*sq\s*ft', text.lower())
    return sqft_match.group(1).replace(',', '') if sqft_match else None

def fetch_page(url, output_dir='data/meritagehomes'):
    """Fetch and parse page data"""
    driver = None
    try:
        # Generate output filename
        community_name = url.split('/')[-1]
        json_file = f"{output_dir}/json/meritage_{community_name}.json"
        
        # Check if file already exists
        if os.path.exists(json_file):
            logger.info(f"JSON file already exists: {json_file}, skipping...")
            return None
            
        logger.info(f"Processing URL: {url}")
        driver = setup_driver()
        driver.get(url)
        time.sleep(5)  # Wait for page load
        
        # Save HTML
        os.makedirs(f"{output_dir}/html", exist_ok=True)
        os.makedirs(f"{output_dir}/json", exist_ok=True)
        html_file = f"{output_dir}/html/meritage_{community_name}.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        logger.info(f"HTML saved to: {html_file}")

        # Parse data
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        data = {
            "timestamp": datetime.now().isoformat(),
            "name": None,
            "status": None,
            "url": url,
            "price_from": None,
            "address": None,
            "phone": None,
            "description": None,
            "images": [],
            "location": {
                "latitude": None,
                "longitude": None,
                "address": {
                    "city": None,
                    "state": None,
                    "market": None
                }
            },
            "details": {
                "price_range": None,
                "sqft_range": None,
                "bed_range": None,
                "bath_range": None,
                "stories_range": None,
                "community_count": 1
            },
            "amenities": [],
            "homeplans": [],
            "homesites": [],
            "nearbyplaces": [],
            "collections": []
        }

        # Extract community name
        overview_section = soup.find('div', class_='community-detail-overview')
        if overview_section:
            h1_elem = overview_section.find('article').find('h1')
            if h1_elem:
                data["name"] = h1_elem.text.strip()
                logger.info(f"Found community name: {data['name']}")

        # Extract price from
        price_text = soup.text
        price_match = re.search(r'Starting at\s+(\$[\d,]+)', price_text)
        if price_match:
            data["price_from"] = f"From {price_match.group(1)}"
            data["details"]["price_range"] = data["price_from"]
            logger.info(f"Found price: {data['price_from']}")

        # Extract address
        location_elem = soup.find('div', id='community-driving-directions--location')
        if location_elem:
            address_elem = location_elem.find('div', class_='has-dividers')
            if address_elem and address_elem.find('p'):
                data["address"] = address_elem.find('p').text.strip()
                logger.info(f"Found address: {data['address']}")

        # Extract description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            data["description"] = meta_desc.get('content', '').strip()
            logger.info("Found description from meta tag")

        # Extract first image
        slides = soup.find_all('li', class_='slick-slide orbit-slide')
        if slides:
            first_imageParent = slides[0]
            first_image = first_imageParent.find('span', attrs={'data-lazy': True})
            if first_image:
                src = first_image.get('src') or first_image.get('data-csrc')
                if src:
                    if not src.startswith('http'):
                        src = 'https://www.meritagehomes.com' + src
                        data["images"].append(src)
                        logger.info("Found first image")

        # Extract location coordinates
        location_elem = soup.find('div', id='community-driving-directions--location')
        if location_elem:
            data["location"]["latitude"] = location_elem.get('data-lat')
            data["location"]["longitude"] = location_elem.get('data-long')
            logger.info("Found location coordinates")

        # Extract ranges for details
        html_text = soup.text
        # Square footage range
        sqft_match = re.search(r'Approx\.\s+Sq\.\s+Ft\.\s+([\d,]+)\s*-\s*([\d,]+)', html_text)
        if sqft_match:
            data["details"]["sqft_range"] = f"{sqft_match.group(1)} - {sqft_match.group(2)}"
            logger.info(f"Found sqft range: {data['details']['sqft_range']}")

        # Find all columns with the specified class
        columns = soup.find_all('div', class_='small-6 medium-6 large-3 column')
        
        # Extract bed range
        for col in columns:
            h3 = col.find('h3')
            if h3 and h3.text.strip() == 'Bedrooms':
                span = h3.find_next_sibling('span')
                if span:
                    data["details"]["bed_range"] = span.text.strip()
                break
        
        # Extract bath range
        for col in columns:
            h3 = col.find('h3')
            if h3 and h3.text.strip() == 'Full Bathrooms':
                span = h3.find_next_sibling('span')
                if span:
                    data["details"]["bath_range"] = span.text.strip()
                break
        
        # Extract stories range
        for col in columns:
            h3 = col.find('h3')
            if h3 and h3.text.strip() == 'Stories':
                span = h3.find_next_sibling('span')
                if span:
                    data["details"]["stories_range"] = span.text.strip()
                break

        # Extract nearby places
        for group in soup.find_all('div', class_='multicol'):
            category = group.find('h5').text.strip() if group.find('h5') else None
            for link in group.find_all('span', class_='plain'):
                nearby = {
                    "name": link.text.strip(),
                    "category": category,
                    "distance": None,
                    "rating": None,
                    "reviews": None
                }
                data["nearbyplaces"].append(nearby)
            logger.info(f"Found {len(data['nearbyplaces'])} nearby places")

        # Extract homesites
        qmi_section = soup.find('section', attrs={'aria-label': 'Quick Move Ins'})
        if qmi_section:
            for index, qmi in enumerate(qmi_section.find_all('div', class_='qmi-vertical')):
                content = qmi.find('div', class_='content')
                if content:
                    mid = content.find('div', class_='mid')
                    if mid:
                        raw_address = mid.find('p').text.strip() if mid.find('p') else None
                        # Clean up address formatting - remove newlines and extra spaces
                        address = ' '.join(raw_address.split()) if raw_address else None
                        homesite = {
                            "address": address,
                            "name": re.sub(r'\s+\d{5}$', '', address) if address else None,
                            "plan": mid.find('h3').text.strip() if mid.find('h3') else None,
                            "id": str(index + 1),
                            "price": mid.find('div', class_='top-details').text.strip() if mid.find('div', class_='top-details') else None,
                            "beds": f"{re.search(r'Bed\s+(\d+)', mid.find('div', class_='bottom-details').text).group(1)}bd" if mid.find('div', class_='bottom-details') and re.search(r'Bed\s+(\d+)', mid.find('div', class_='bottom-details').text) else None,
                            "baths": f"{re.search(r'Bath\s+(\d+)', mid.find('div', class_='bottom-details').text).group(1)}ba" if mid.find('div', class_='bottom-details') and re.search(r'Bath\s+(\d+)', mid.find('div', class_='bottom-details').text) else None,
                            "sqft": f"{re.search(r'Approx\.\s+([\d,]+)\s+sq\.\s+ft\.', mid.find('div', class_='bottom-details').text).group(1)} ft²" if mid.find('div', class_='bottom-details') and re.search(r'Approx\.\s+([\d,]+)\s+sq\.\s+ft\.', mid.find('div', class_='bottom-details').text) else None,
                            "status": "Available",
                            "image_url": None,
                            "url": f"https://www.meritagehomes.com{mid.find('h3').find('a')['href']}" if mid.find('h3') and mid.find('h3').find('a') else None,
                            "latitude": None,
                            "longitude": None,
                            "overview": None,
                            "images": []
                        }
                        
                        # Get image URL
                        img_container = qmi.find('div', class_='image')
                        if img_container and img_container.find('img'):
                            img = img_container.find('img')
                            src = img.get('src') or img.get('data-csrc')
                            if src and not src.startswith('http'):
                                src = 'https://www.meritagehomes.com' + src
                            homesite["image_url"] = src

                        # Fetch homesite detail page
                        if homesite["url"]:
                            try:
                                site_name = homesite["url"].split('/')[-1]
                                site_html_file = f"{output_dir}/html/meritage_homesite_{site_name}.html"
                                
                                # Save homesite page HTML
                                driver.get(homesite["url"])
                                time.sleep(3)  # Wait for page load
                                with open(site_html_file, 'w', encoding='utf-8') as f:
                                    f.write(driver.page_source)
                                
                                # Parse homesite page
                                site_soup = BeautifulSoup(driver.page_source, 'html.parser')
                                
                                # Extract coordinates and overview from article
                                content_section = site_soup.find('article', attrs={'class': 'small-12 medium-10 large-8 column text-center pad-bottom-2'})
                                if content_section:
                                    # Find map link and extract coordinates
                                    map_link = content_section.find('a', {'class': 'plain', 'href': lambda x: x and 'maps.google.com' in x})
                                    if map_link and 'href' in map_link.attrs:
                                        coords_match = re.search(r'daddr=([-\d.]+),([-\d.]+)', map_link['href'])
                                        if coords_match:
                                            homesite["latitude"] = coords_match.group(1)
                                            homesite["longitude"] = coords_match.group(2)
                                            logger.info(f"Found coordinates: {homesite['latitude']}, {homesite['longitude']}")
                                    
                                    # Extract overview - it's the p tag that contains text about the home description
                                    paragraphs = content_section.find_all('p')
                                    for p in paragraphs:
                                        # Skip paragraphs that are just plan numbers or contain specific headers
                                        if not p.text.strip().startswith('Plan #') and 'Estimated Completion' not in p.text and 'Home Address' not in p.text:
                                            homesite["overview"] = p.text.strip()
                                            logger.info(f"Found overview: {homesite['overview'][:50]}...")
                                            break
                                
                                # Extract images - handle both regular and lazy loaded images
                                for slide in site_soup.find_all('li', class_='slick-slide orbit-slide'):
                                    # First try to get lazy loaded image
                                    hidden_img = slide.find('span', class_='hidden-image')
                                    if hidden_img and hidden_img.get('data-lazy'):
                                        src = hidden_img.get('data-lazy')
                                        if src and not src.startswith('http'):
                                            src = 'https://www.meritagehomes.com' + src
                                        homesite["images"].append(src)
                                    else:
                                        # Try regular image as fallback
                                        img = slide.find('img', class_='orbit-image')
                                        if img:
                                            src = img.get('src') or img.get('data-csrc')
                                            if src and not src.startswith('http') and not src.endswith('meritageLoadingCommunityHero.gif'):
                                                src = 'https://www.meritagehomes.com' + src
                                                homesite["images"].append(src)
                                
                                logger.info(f"Found {len(homesite['images'])} images")
                                
                                # Delete the HTML file after extracting data
                                if os.path.exists(site_html_file):
                                    os.remove(site_html_file)
                                    logger.info(f"Deleted HTML file: {site_html_file}")
                                    
                            except Exception as e:
                                logger.error(f"Error processing homesite page {homesite['url']}: {str(e)}")
                                # Try to delete HTML file even if there was an error
                                if os.path.exists(site_html_file):
                                    os.remove(site_html_file)
                                    logger.info(f"Deleted HTML file after error: {site_html_file}")
                            
                        data["homesites"].append(homesite)
                        logger.info(f"Added homesite: {homesite['name']}")

        # Extract home plans
        for plan in soup.find_all('div', class_='row columns collapse floorplan-vertical'):
            content = plan.find('div', class_='content')
            homeplan = {
                "name": content.find('h3').text.strip() if content and content.find('h3') else None,
                "url": f"https://www.meritagehomes.com{content.find('h3').find('a')['href']}" if content and content.find('h3') and content.find('h3').find('a') else None,
                "details": {
                    "price": plan.find('div', class_='top-details').text.strip() if plan.find('div', class_='top-details') else None,
                    "beds": f"{re.search(r'Bed\s+(\d+)', plan.find('div', class_='bottom-details').text).group(1)}bd" if plan.find('div', class_='bottom-details') and re.search(r'Bed\s+(\d+)', plan.find('div', class_='bottom-details').text) else None,
                    "baths": f"{re.search(r'Bath\s+(\d+)', plan.find('div', class_='bottom-details').text).group(1)}ba" if plan.find('div', class_='bottom-details') and re.search(r'Bath\s+(\d+)', plan.find('div', class_='bottom-details').text) else None,
                    "half_baths": None,
                    "sqft": f"{re.search(r'Approx\.\s+([\d,]+)\s+sq\.\s+ft\.', plan.find('div', class_='bottom-details').text).group(1)} ft²" if plan.find('div', class_='bottom-details') and re.search(r'Approx\.\s+([\d,]+)\s+sq\.\s+ft\.', plan.find('div', class_='bottom-details').text) else None,
                    "status": "Actively selling",
                    "image_url": None
                },
                "floorplan_images": [],
                "includedFeatures": []
            }
            
            # Get image URL
            img_container = plan.find('div', class_='image')
            if img_container:
                # Try to find image in lazy load script
                lazy_script = img_container.find('script', {'type': 'text/lazyload'})
                if lazy_script:
                    # Extract src from the img tag inside script content
                    img_match = re.search(r'<img[^>]*src="([^"]*)"', lazy_script.string)
                    if img_match:
                        src = img_match.group(1)
                        if src and not src.startswith('http'):
                            src = 'https://www.meritagehomes.com' + src
                        homeplan["details"]["image_url"] = src
                else:
                    # Try normal img tag as fallback
                    img = img_container.find('img')
                    if img:
                        src = img.get('src') or img.get('data-csrc')
                        if src and not src.startswith('http'):
                            src = 'https://www.meritagehomes.com' + src
                        homeplan["details"]["image_url"] = src

            # Fetch homeplan detail page
            if homeplan["url"]:
                try:
                    plan_name = homeplan["url"].split('/')[-1]
                    plan_html_file = f"{output_dir}/html/meritage_{plan_name}.html"
                    
                    # Save plan page HTML
                    driver.get(homeplan["url"])
                    time.sleep(3)  # Wait for page load
                    with open(plan_html_file, 'w', encoding='utf-8') as f:
                        f.write(driver.page_source)
                    
                    # Parse plan page
                    plan_soup = BeautifulSoup(driver.page_source, 'html.parser')
                    
                    # Initialize includedFeatures array
                    homeplan["includedFeatures"] = []
                    
                    # Extract included features from multicol decorated
                    feature_sections = plan_soup.find_all('div', class_='small-12 large-6 column text align-middle text-left')
                    logger.info(f"feature_sections------------: {feature_sections}")
                    total_features = 0
                    
                    # First count total features to determine section distribution
                    for section in feature_sections:
                        if section.find('ul'):
                            total_features += len(section.find('ul').find_all('li'))
                            logger.info(f"total_features------------: {total_features}")
                    
                    # Calculate features per section (roughly divide by 4)
                    features_per_section = total_features // 4 if total_features > 0 else 0
                    logger.info(f"features_per_section------------: {features_per_section}")
                    current_section = 0
                    feature_count = 0
                    
                    # Extract features and assign section indexes
                    for section in feature_sections:
                        ul = section.find('ul')
                        if ul:
                            for li in ul.find_all('li'):
                                feature_text = li.text.strip()
                                if feature_text:
                                    homeplan["includedFeatures"].append({
                                        "description": feature_text,
                                        "section_index": current_section
                                    })
                                    feature_count += 1
                                    # Update section index when count exceeds per-section limit
                                    if feature_count >= (current_section + 1) * features_per_section:
                                        current_section = min(current_section + 1, 3)
                    
                    logger.info(f"Added {len(homeplan['includedFeatures'])} included features for plan: {homeplan['name']}")
                    
                    # Extract half baths
                    for col in plan_soup.find_all('div', class_='small-6 medium-6 large-4 column'):
                        h3 = col.find('h3')
                        if h3 and h3.text.strip() == 'Half Bathrooms':
                            span = h3.find_next_sibling('span')
                            if span:
                                homeplan["details"]["half_baths"] = span.text.strip()
                                break
                    
                    # Get number of stories and generate floorplan images
                    stories = None
                    for col in plan_soup.find_all('div', class_='small-6 medium-6 large-4 column'):
                        h3 = col.find('h3')
                        if h3 and h3.text.strip() == 'Stories':
                            span = h3.find_next_sibling('span')
                            if span:
                                try:
                                    stories = int(span.text.strip())
                                    # Generate floorplan entries based on number of stories
                                    for i in range(1, stories + 1):
                                        if i == 1:
                                            floor_name = "1st Floor Floorplan"
                                        elif i == 2:
                                            floor_name = "2nd Floor Floorplan"
                                        elif i == 3:
                                            floor_name = "3rd Floor Floorplan"
                                        else:
                                            floor_name = f"{i}th Floor Floorplan"
                                            
                                        # Find corresponding image in tabs-content
                                        tabs_content = plan_soup.find('div', class_='tabs-content')
                                        if tabs_content:
                                            panels = tabs_content.find('div', class_='tabs-panel')
                                            img = panels.find('img')
                                            if img:
                                                src = img.get('src') or img.get('data-csrc')
                                                if src:
                                                    homeplan["floorplan_images"].append({
                                                        "name": floor_name,
                                                        "image_url": src
                                                    })
                                except ValueError:
                                    continue
                                break
                    
                    # Delete the HTML file after extracting data
                    if os.path.exists(plan_html_file):
                        os.remove(plan_html_file)
                        logger.info(f"Deleted HTML file: {plan_html_file}")
                                        
                except Exception as e:
                    logger.error(f"Error processing plan page {homeplan['url']}: {str(e)}")
                    # Try to delete HTML file even if there was an error
                    if os.path.exists(plan_html_file):
                        os.remove(plan_html_file)
                        logger.info(f"Deleted HTML file after error: {plan_html_file}")
                
            data["homeplans"].append(homeplan)
            logger.info(f"Added plan: {homeplan['name']}")

        # If main images array is empty, try to get an image from homeplans or homesites
        if not data["images"]:
            available_images = []
            
            # Collect images from homeplans
            for plan in data["homeplans"]:
                if plan["details"]["image_url"]:
                    available_images.append(plan["details"]["image_url"])
            
            # Collect images from homesites
            for site in data["homesites"]:
                if site["image_url"]:
                    available_images.append(site["image_url"])
                if site["images"]:
                    available_images.extend(site["images"])
            
            # If we found any images, randomly select one
            if available_images:
                data["images"] = [random.choice(available_images)]
                logger.info(f"Added random image to main images array from available images")

        # Save JSON
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Data saved to: {json_file}")

        return data

    except Exception as e:
        logger.error(f"Error processing page: {str(e)}")
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logger.error(f"Error closing driver: {str(e)}")

def main():
    """Main function"""
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description='Scrape Meritage community pages')
        parser.add_argument('--url', help='Process a single URL')
        parser.add_argument('--batch', action='store_true', help='Process all URLs from meritage_links.json')
        args = parser.parse_args()

        # Ensure output directories exist
        output_dir = 'data/meritagehomes'
        os.makedirs(f'{output_dir}/html', exist_ok=True)
        os.makedirs(f'{output_dir}/json', exist_ok=True)
        
        if args.batch:
            try:
                # Look for meritage_links.json in several possible locations
                possible_paths = [
                    'meritage_links.json',
                    'data/meritage_links.json',
                    '../meritage_links.json',
                    os.path.join(os.path.dirname(__file__), 'meritage_links.json')
                ]
                
                json_file = None
                for path in possible_paths:
                    if os.path.exists(path):
                        json_file = path
                        logger.info(f"Found meritage_links.json at: {path}")
                        break
                
                if not json_file:
                    logger.error("Could not find meritage_links.json in any expected location")
                    return
                
                # Read URLs from meritage_links.json
                with open(json_file, 'r', encoding='utf-8') as f:
                    urls = json.load(f)
                
                if not urls:
                    logger.error("No URLs found in meritage_links.json")
                    return
                
                logger.info(f"Found {len(urls)} URLs to process")
                
                # Process each URL
                for i, url in enumerate(urls, 1):
                    try:
                        logger.info(f"Processing URL {i}/{len(urls)}")
                        fetch_page(url, output_dir)
                        time.sleep(2)  # Add delay to avoid too frequent requests
                    except Exception as e:
                        logger.error(f"Failed to process URL {url}: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.error(f"Error during batch processing: {str(e)}")
                logger.exception("Detailed error information:")
                return
                
        elif args.url:
            # Process specified URL
            fetch_page(args.url, output_dir)
        else:
            # Process default URL
            default_urls = [
                "https://www.meritagehomes.com/state/al/huntsville/madison-preserve-the-estate-series",
                "https://www.meritagehomes.com/state/az/phoenix/heritage-at-maricopa",
                "https://www.meritagehomes.com/state/ca/sacramento/madison-at-ten-trails"
            ]
            default_url = default_urls[0]  # Use first URL as default
            fetch_page(default_url, output_dir)
        
    except Exception as e:
        logger.error(f"Main program execution error: {str(e)}")
        logger.exception("Detailed error information:")

if __name__ == "__main__":
    main() 
import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from dotenv import load_dotenv
import database as db
import message_personalizer as mp

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
DISCOVERY_URL = "https://attend.websummit.com/lis25/discovery?active_tab=attendances"
DELAY_BETWEEN_REQUESTS = 3000
DELAY_AFTER_SCROLL = 2000
MAX_RETRIES = 3
RETRY_DELAY = 2000

# Parallel processing
MAX_WORKERS = 5  # Number of concurrent workers
BATCH_SIZE = 10  # Show stats every N attendees
HEADLESS = True  # Run browsers in headless mode (no UI, faster)

def load_cookies() -> List[Dict]:
    """Load cookies from cookies.json."""
    with open('cookies.json', 'r') as f:
        return json.load(f)

async def setup_browser() -> tuple[Browser, BrowserContext, Page]:
    """Setup browser with cookies."""
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=HEADLESS)
    context = await browser.new_context()
    
    cookies = load_cookies()
    await context.add_cookies(cookies)
    
    page = await context.new_page()
    return browser, context, page

async def create_worker_browser() -> tuple[Browser, BrowserContext, Page]:
    """Create a new browser instance for a worker."""
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=HEADLESS)
    context = await browser.new_context()
    cookies = load_cookies()
    await context.add_cookies(cookies)
    page = await context.new_page()
    return browser, context, page

async def scroll_and_collect_profiles(page: Page) -> List[str]:
    """Scroll page and collect all profile URLs."""
    logger.info("Collecting profile URLs...")
    profile_urls = set()
    last_count = 0
    no_change_count = 0
    
    while True:
        links = await page.query_selector_all('a[href*="/lis25/profiles/"]')
        
        for link in links:
            href = await link.get_attribute('href')
            if href and '/profiles/' in href:
                full_url = f"https://attend.websummit.com{href}" if href.startswith('/') else href
                base_url = full_url.split('?')[0]
                profile_urls.add(base_url)
        
        current_count = len(profile_urls)
        logger.info(f"Found {current_count} profiles so far...")
        
        if current_count == last_count:
            no_change_count += 1
            if no_change_count >= 3:
                logger.info("No new profiles found after 3 scrolls. Stopping.")
                break
        else:
            no_change_count = 0
        
        last_count = current_count
        
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        await asyncio.sleep(DELAY_AFTER_SCROLL / 1000)
        
        loading = await page.query_selector('text="Loading..."')
        if not loading:
            logger.info("No loading indicator found. Reached end.")
            break
    
    logger.info(f"Total profiles collected: {len(profile_urls)}")
    return list(profile_urls)

async def extract_profile_data(page: Page, profile_url: str) -> Optional[Dict]:
    """Extract data from attendee profile page."""
    try:
        await page.goto(profile_url, wait_until='domcontentloaded')
        await asyncio.sleep(1)
        
        profile_id = profile_url.split('/profiles/')[-1]
        
        main_text = await page.locator('main').text_content()
        lines = [line.strip() for line in main_text.split('\n') if line.strip()]
        
        badge = lines[0] if lines else ""
        name = lines[1] if len(lines) > 1 else ""
        title = lines[2] if len(lines) > 2 else ""
        company = lines[3] if len(lines) > 3 else ""
        bio = lines[4] if len(lines) > 4 else ""
        location = lines[5] if len(lines) > 5 else ""
        industry = lines[6] if len(lines) > 6 else ""
        
        communities = []
        try:
            comm_tab = await page.query_selector('tab[aria-label="Communities"]')
            if comm_tab:
                comm_text = await comm_tab.text_content()
                communities = [c.strip() for c in comm_text.split('\n') if c.strip() and not c.startswith('�')]
        except:
            pass
        
        data = {
            'profile_id': profile_id,
            'name': name,
            'badge': badge,
            'title': title,
            'company': company,
            'bio': bio,
            'location': location,
            'industry': industry,
            'communities': communities,
            'profile_url': profile_url
        }
        
        logger.info(f"Extracted data for: {name}")
        return data
        
    except Exception as e:
        logger.error(f"Error extracting profile data from {profile_url}: {e}")
        return None

async def send_meeting_request(page: Page, attendee_data: Dict) -> bool:
    """Send meeting request to attendee with personalized message."""
    try:
        # Generate personalized message
        logger.info(f"Generating personalized message for {attendee_data.get('name', 'attendee')}...")
        message = mp.personalize_message(attendee_data)
        
        await page.click('button:has-text("Request Meeting")')
        logger.info("Clicked Request Meeting button")
        await asyncio.sleep(2)
        
        modal = await page.wait_for_selector('[role="dialog"]', timeout=5000)
        if not modal:
            logger.error("Modal did not appear")
            return False
        
        logger.info("Modal appeared, selecting location...")
        location_label = await page.query_selector('label[for="location_3407"]')
        if location_label:
            await location_label.click()
            logger.info("Selected first location")
        else:
            location_links = await page.query_selector_all('a[href*="load_location_slots"]')
            if location_links:
                await location_links[0].click()
                logger.info("Selected first available location")
        
        await asyncio.sleep(2)
        
        logger.info("Selecting time slot...")
        slot_card = await page.query_selector('.slot-card')
        if slot_card:
            await slot_card.click()
            logger.info("Selected first time slot")
        else:
            slot_labels = await page.query_selector_all('label[for^="location_time_slot_"]')
            if slot_labels:
                await slot_labels[0].click()
                logger.info("Selected first available time slot")
        
        await asyncio.sleep(1)
        
        logger.info("Filling personalized message...")
        message_field = await page.query_selector('textarea[name="description"]')
        if message_field:
            await message_field.fill(message)
            logger.info("Personalized message filled")
        
        await asyncio.sleep(1)
        
        logger.info("Clicking send request...")
        send_btn = await page.query_selector('button:has-text("Send request")')
        if send_btn:
            await send_btn.click()
            logger.info("Send request clicked")
            await asyncio.sleep(2)
            return True
        else:
            logger.error("Send button not found")
            return False
        
    except Exception as e:
        logger.error(f"Error sending meeting request: {e}")
        return False

async def process_attendee(page: Page, profile_url: str) -> bool:
    """Process a single attendee: scrape data and send meeting request."""
    profile_id = profile_url.split('/profiles/')[-1]
    
    if db.attendee_exists(profile_id):
        attendee = db.get_attendee(profile_id)
        if attendee['meeting_requested']:
            logger.info(f"Skipping {profile_id} - already processed")
            return True
        logger.info(f"Attendee {profile_id} exists, sending meeting request...")
        # Convert DB row to dict format for personalizer
        attendee_data = {
            'name': attendee.get('name', ''),
            'company': attendee.get('company', ''),
            'title': attendee.get('title', ''),
            'industry': attendee.get('industry', ''),
            'bio': attendee.get('bio', ''),
            'badge': attendee.get('badge', ''),
            'location': attendee.get('location', ''),
            'communities': json.loads(attendee.get('communities', '[]')) if attendee.get('communities') else []
        }
    else:
        data = await extract_profile_data(page, profile_url)
        if not data:
            logger.error(f"Failed to extract data for {profile_id}")
            return False
        
        db.insert_attendee(data)
        logger.info(f"Saved attendee: {data['name']}")
        attendee_data = data
    
    attendee_name = attendee_data['name']
    
    await page.goto(profile_url, wait_until='domcontentloaded')
    await asyncio.sleep(1)
    
    success = await send_meeting_request(page, attendee_data)
    
    if success:
        db.mark_as_sent(profile_id)
        logger.info(f"✓ Meeting request sent to {attendee_name}")
    else:
        db.mark_as_failed(profile_id, "Failed to send meeting request")
        logger.error(f"✗ Failed to send meeting request to {attendee_name}")
    
    return success

# Global counters for progress tracking
processed_count = 0
processed_lock = asyncio.Lock()

async def worker(worker_id: int, profile_urls: List[str], semaphore: asyncio.Semaphore, total_urls: int):
    """Worker that processes attendees concurrently."""
    global processed_count
    
    browser, context, page = await create_worker_browser()
    
    try:
        for profile_url in profile_urls:
            async with semaphore:
                async with processed_lock:
                    processed_count += 1
                    current = processed_count
                
                logger.info(f"[Worker {worker_id}] [{current}/{total_urls}] Processing {profile_url}")
                
                success = await process_attendee(page, profile_url)
                
                await asyncio.sleep(DELAY_BETWEEN_REQUESTS / 1000)
                
                if current % BATCH_SIZE == 0:
                    stats = db.get_stats()
                    logger.info(f"\n[Progress] {stats}")
    finally:
        await context.close()
        await browser.close()

async def main():
    """Main automation flow with parallel processing."""
    global processed_count
    processed_count = 0
    
    logger.info("Starting Web Summit automation...")
    logger.info(f"Running with {MAX_WORKERS} parallel workers")
    
    db.create_database()
    
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY not set! Please set it as an environment variable.")
        logger.error("Example: set OPENAI_API_KEY=your_key_here")
        return
    
    logger.info("Using AI-powered personalized messages")
    
    browser, context, page = await setup_browser()
    
    try:
        logger.info("Navigating to discovery page...")
        await page.goto(DISCOVERY_URL, wait_until='domcontentloaded')
        await asyncio.sleep(3)
        
        logger.info("Collecting all profile URLs...")
        profile_urls = await scroll_and_collect_profiles(page)
        
        # Close the initial context (workers will create their own)
        await context.close()
        
        logger.info(f"Processing {len(profile_urls)} profiles with {MAX_WORKERS} workers...")
        
        # Split URLs among workers
        chunk_size = len(profile_urls) // MAX_WORKERS
        url_chunks = [
            profile_urls[i:i + chunk_size] 
            for i in range(0, len(profile_urls), chunk_size)
        ]
        
        # Ensure all URLs are distributed
        if len(url_chunks) > MAX_WORKERS:
            url_chunks[MAX_WORKERS - 1].extend(url_chunks[MAX_WORKERS:][0])
            url_chunks = url_chunks[:MAX_WORKERS]
        
        # Create semaphore to control concurrency
        semaphore = asyncio.Semaphore(MAX_WORKERS)
        
        # Start all workers (each with own browser instance)
        workers = [
            worker(i + 1, url_chunks[i], semaphore, len(profile_urls))
            for i in range(len(url_chunks))
        ]
        
        # Wait for all workers to complete
        await asyncio.gather(*workers)
        
        final_stats = db.get_stats()
        logger.info(f"\n{'='*50}")
        logger.info("Automation completed!")
        logger.info(f"Total profiles: {final_stats['total']}")
        logger.info(f"Meeting requests sent: {final_stats['meeting_sent']}")
        logger.info(f"Pending: {final_stats['pending']}")
        logger.info(f"Failed: {final_stats['failed']}")
        logger.info(f"{'='*50}")
        
    except Exception as e:
        logger.error(f"Error in main flow: {e}")
    finally:
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())


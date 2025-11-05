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
HEADLESS = False  # Run browsers in headless mode (no UI, faster)

# Scraping mode
SCRAPE_ONLY = True  # Set to True to only collect data without sending meeting requests

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

async def create_worker_page(context: BrowserContext) -> Page:
    """Create a new page (tab) for a worker."""
    page = await context.new_page()
    return page

async def scroll_and_collect_profiles(page: Page, worker_id: int) -> List[str]:
    """Scroll page and collect all profile URLs."""
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
        logger.info(f"[Worker {worker_id}] Found {current_count} profiles so far...")
        
        if current_count == last_count:
            no_change_count += 1
            if no_change_count >= 3:
                logger.info(f"[Worker {worker_id}] No new profiles found after 3 scrolls. Stopping.")
                break
        else:
            no_change_count = 0
        
        last_count = current_count
        
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        await asyncio.sleep(DELAY_AFTER_SCROLL / 1000)
        
        loading = await page.query_selector('text="Loading..."')
        if not loading:
            logger.info(f"[Worker {worker_id}] No loading indicator found. Reached end.")
            break
    
    logger.info(f"[Worker {worker_id}] Total profiles collected: {len(profile_urls)}")
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

async def send_meeting_request(page: Page, attendee_data: Dict, worker_id: int) -> bool:
    """Send meeting request to attendee with personalized message."""
    try:
        # Check if Request Meeting button exists and is enabled
        request_btn = await page.query_selector('button:has-text("Request Meeting")')
        if not request_btn:
            logger.error(f"[Worker {worker_id}] Request Meeting button not found")
            return False
        
        # Check if button is disabled (meeting limit reached)
        is_disabled = await request_btn.get_attribute('disabled')
        if is_disabled:
            error_msg = await request_btn.get_attribute('data-bs-original-title')
            logger.error(f"[Worker {worker_id}] ⚠️  MEETING LIMIT REACHED! Button disabled: {error_msg}")
            return False
        
        # Generate personalized message
        logger.info(f"[Worker {worker_id}] Generating personalized message for {attendee_data.get('name', 'attendee')}...")
        message = mp.personalize_message(attendee_data)
        
        await request_btn.click()
        logger.info(f"[Worker {worker_id}] Clicked Request Meeting button")
        await asyncio.sleep(2)
        
        modal = await page.wait_for_selector('[role="dialog"]', timeout=5000)
        if not modal:
            logger.error(f"[Worker {worker_id}] Modal did not appear")
            return False
        
        logger.info(f"[Worker {worker_id}] Modal appeared, selecting location...")
        location_label = await page.query_selector('label[for="location_3407"]')
        if location_label:
            await location_label.click()
            logger.info(f"[Worker {worker_id}] Selected first location")
        else:
            location_links = await page.query_selector_all('a[href*="load_location_slots"]')
            if location_links:
                await location_links[0].click()
                logger.info(f"[Worker {worker_id}] Selected first available location")
        
        await asyncio.sleep(2)
        
        logger.info(f"[Worker {worker_id}] Selecting time slot...")
        slot_card = await page.query_selector('.slot-card')
        if slot_card:
            await slot_card.click()
            logger.info(f"[Worker {worker_id}] Selected first time slot")
        else:
            slot_labels = await page.query_selector_all('label[for^="location_time_slot_"]')
            if slot_labels:
                await slot_labels[0].click()
                logger.info(f"[Worker {worker_id}] Selected first available time slot")
        
        await asyncio.sleep(1)
        
        logger.info(f"[Worker {worker_id}] Filling personalized message...")
        message_field = await page.query_selector('textarea[name="description"]')
        if message_field:
            await message_field.fill(message)
            logger.info(f"[Worker {worker_id}] Personalized message filled")
        
        await asyncio.sleep(1)
        
        logger.info(f"[Worker {worker_id}] Clicking send request...")
        send_btn = await page.query_selector('button:has-text("Send request")')
        if send_btn:
            await send_btn.click()
            logger.info(f"[Worker {worker_id}] Send request clicked")
            await asyncio.sleep(2)
            return True
        else:
            logger.error(f"[Worker {worker_id}] Send button not found")
            return False
        
    except Exception as e:
        logger.error(f"[Worker {worker_id}] Error sending meeting request: {e}")
        return False

async def process_attendee(page: Page, profile_url: str, worker_id: int) -> bool:
    """Process a single attendee: scrape data and send meeting request."""
    profile_id = profile_url.split('/profiles/')[-1]
    
    if db.attendee_exists(profile_id):
        attendee = db.get_attendee(profile_id)
        if attendee['meeting_requested']:
            logger.info(f"[Worker {worker_id}] Skipping {profile_id} - already processed")
            return True
        
        if SCRAPE_ONLY:
            logger.info(f"[Worker {worker_id}] Attendee {profile_id} exists - skipping (SCRAPE_ONLY mode)")
            return True
            
        logger.info(f"[Worker {worker_id}] Attendee {profile_id} exists, sending meeting request...")
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
            logger.error(f"[Worker {worker_id}] Failed to extract data for {profile_id}")
            return False
        
        try:
            db.insert_attendee(data)
            logger.info(f"[Worker {worker_id}] Saved attendee: {data['name']}")
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                logger.warning(f"[Worker {worker_id}] Attendee {profile_id} already exists (race condition)")
            else:
                logger.error(f"[Worker {worker_id}] Error saving attendee: {e}")
                return False
        
        if SCRAPE_ONLY:
            logger.info(f"[Worker {worker_id}] SCRAPE_ONLY mode - skipping meeting request")
            return True
            
        attendee_data = data
    
    attendee_name = attendee_data['name']
    
    await page.goto(profile_url, wait_until='domcontentloaded')
    await asyncio.sleep(1)
    
    success = await send_meeting_request(page, attendee_data, worker_id)
    
    if success:
        db.mark_as_sent(profile_id)
        logger.info(f"[Worker {worker_id}] ✓ Meeting request sent to {attendee_name}")
    else:
        db.mark_as_failed(profile_id, "Failed to send meeting request")
        logger.error(f"[Worker {worker_id}] ✗ Failed to send meeting request to {attendee_name}")
    
    return success

# Global counters for progress tracking
processed_count = 0
processed_lock = asyncio.Lock()

async def worker(worker_id: int, context: BrowserContext, semaphore: asyncio.Semaphore):
    """Worker that processes attendees concurrently in its own tab."""
    global processed_count
    
    page = await create_worker_page(context)
    
    try:
        # Each worker loads the discovery page independently
        logger.info(f"[Worker {worker_id}] Navigating to discovery page...")
        await page.goto(DISCOVERY_URL, wait_until='domcontentloaded')
        await asyncio.sleep(3)
        
        # Each worker collects its own profile URLs
        logger.info(f"[Worker {worker_id}] Collecting profile URLs...")
        profile_urls = await scroll_and_collect_profiles(page, worker_id)
        logger.info(f"[Worker {worker_id}] Found {len(profile_urls)} profiles to process")
        
        # Process each profile
        for idx, profile_url in enumerate(profile_urls, 1):
            async with semaphore:
                async with processed_lock:
                    processed_count += 1
                    current = processed_count
                
                logger.info(f"[Worker {worker_id}] [{idx}/{len(profile_urls)}] (Global: {current}) Processing {profile_url}")
                
                success = await process_attendee(page, profile_url, worker_id)
                
                await asyncio.sleep(DELAY_BETWEEN_REQUESTS / 1000)
                
                if current % BATCH_SIZE == 0:
                    stats = db.get_stats()
                    logger.info(f"\n[Progress] {stats}")
    finally:
        await page.close()

async def main():
    """Main automation flow with parallel processing."""
    global processed_count
    processed_count = 0
    
    logger.info("Starting Web Summit automation...")
    logger.info(f"Running with {MAX_WORKERS} parallel workers")
    
    db.create_database()
    
    if SCRAPE_ONLY:
        logger.info("🔍 SCRAPE_ONLY MODE - Will only collect attendee data, no meeting requests")
    else:
        # Check for API key only if sending meeting requests
        if not os.getenv("OPENAI_API_KEY"):
            logger.error("OPENAI_API_KEY not set! Please set it as an environment variable.")
            logger.error("Example: set OPENAI_API_KEY=your_key_here")
            return
        
        logger.info("Using AI-powered personalized messages")
    
    browser, context, page = await setup_browser()
    
    try:
        # Close the initial page, workers will create their own
        await page.close()
        
        logger.info(f"Starting {MAX_WORKERS} workers, each will independently collect profiles...")
        
        # Create semaphore to control concurrency
        semaphore = asyncio.Semaphore(MAX_WORKERS)
        
        # Start all workers (each independently collects and processes profiles)
        workers = [
            worker(i + 1, context, semaphore)
            for i in range(MAX_WORKERS)
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


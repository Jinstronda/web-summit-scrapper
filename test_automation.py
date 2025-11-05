import asyncio
import json
import logging
from playwright.async_api import async_playwright
import database as db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TEST_PROFILE_URL = "https://attend.websummit.com/lis25/profiles/531171"
DISCOVERY_URL = "https://attend.websummit.com/lis25/discovery?active_tab=attendances"

def load_cookies():
    with open('cookies.json', 'r') as f:
        return json.load(f)

async def test_login():
    """Test 1: Verify login with cookies works."""
    logger.info("Test 1: Testing login with cookies...")
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    
    cookies = load_cookies()
    await context.add_cookies(cookies)
    
    page = await context.new_page()
    await page.goto(DISCOVERY_URL, wait_until='domcontentloaded')
    await asyncio.sleep(3)
    
    title = await page.title()
    logger.info(f"Page title: {title}")
    
    is_logged_in = "Sign in" not in await page.content()
    
    if is_logged_in:
        logger.info("✓ Login successful!")
    else:
        logger.error("✗ Login failed - please update cookies.json")
    
    await browser.close()
    await playwright.stop()
    return is_logged_in

async def test_profile_extraction():
    """Test 2: Extract data from a single profile."""
    logger.info("\nTest 2: Testing profile data extraction...")
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    
    cookies = load_cookies()
    await context.add_cookies(cookies)
    
    page = await context.new_page()
    await page.goto(TEST_PROFILE_URL, wait_until='domcontentloaded')
    await asyncio.sleep(2)
    
    main_text = await page.locator('main').text_content()
    lines = [line.strip() for line in main_text.split('\n') if line.strip()]
    
    logger.info("Extracted data:")
    logger.info(f"  Badge: {lines[0] if lines else 'N/A'}")
    logger.info(f"  Name: {lines[1] if len(lines) > 1 else 'N/A'}")
    logger.info(f"  Title: {lines[2] if len(lines) > 2 else 'N/A'}")
    logger.info(f"  Company: {lines[3] if len(lines) > 3 else 'N/A'}")
    
    success = len(lines) >= 2
    if success:
        logger.info("✓ Profile extraction successful!")
    else:
        logger.error("✗ Profile extraction failed")
    
    await browser.close()
    await playwright.stop()
    return success

async def test_meeting_modal():
    """Test 3: Open meeting request modal and inspect elements."""
    logger.info("\nTest 3: Testing meeting request modal...")
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    
    cookies = load_cookies()
    await context.add_cookies(cookies)
    
    page = await context.new_page()
    await page.goto(TEST_PROFILE_URL, wait_until='domcontentloaded')
    await asyncio.sleep(2)
    
    try:
        await page.click('button:has-text("Request Meeting")')
        logger.info("Clicked Request Meeting button")
        await asyncio.sleep(2)
        
        modal = await page.wait_for_selector('[role="dialog"]', timeout=5000)
        if modal:
            logger.info("✓ Modal appeared!")
            
            locations = await page.query_selector_all('input[type="radio"][name="location"]')
            logger.info(f"  Found {len(locations)} meeting locations")
            
            location_links = await page.query_selector_all('a[href*="load_location_slots"]')
            if location_links:
                await location_links[0].click()
                logger.info("  Selected first location")
                await asyncio.sleep(2)
                
                time_slots = await page.query_selector_all('input[type="radio"][name="location_time_slot_id"]')
                logger.info(f"  Found {len(time_slots)} time slots")
                
                message_field = await page.query_selector('textarea[name="description"]')
                if message_field:
                    logger.info("  ✓ Message field found")
                    placeholder = await message_field.get_attribute('placeholder')
                    logger.info(f"  Placeholder: {placeholder}")
                
                send_btn = await page.query_selector('button:has-text("Send request")')
                if send_btn:
                    logger.info("  ✓ Send button found")
                    logger.info("✓ All modal elements found!")
                    success = True
                else:
                    logger.error("  ✗ Send button not found")
                    success = False
            else:
                logger.error("  ✗ No locations found")
                success = False
        else:
            logger.error("✗ Modal did not appear")
            success = False
            
    except Exception as e:
        logger.error(f"✗ Error testing modal: {e}")
        success = False
    
    logger.info("\nModal will stay open for 5 seconds for inspection...")
    await asyncio.sleep(5)
    
    await browser.close()
    await playwright.stop()
    return success

def test_database():
    """Test 4: Test database operations."""
    logger.info("\nTest 4: Testing database operations...")
    
    test_data = {
        'profile_id': 'TEST123',
        'name': 'Test User',
        'badge': 'ATTENDEE',
        'title': 'Test Title',
        'company': 'Test Company',
        'bio': 'Test bio',
        'location': 'Test Location',
        'industry': 'Test Industry',
        'communities': ['Community 1', 'Community 2'],
        'profile_url': 'https://test.com/profile/TEST123'
    }
    
    if db.attendee_exists('TEST123'):
        logger.info("Test attendee already exists, cleaning up...")
        conn = db.get_connection()
        conn.execute('DELETE FROM attendees WHERE profile_id = ?', ('TEST123',))
        conn.commit()
        conn.close()
    
    logger.info("Inserting test attendee...")
    attendee_id = db.insert_attendee(test_data)
    logger.info(f"  Inserted with ID: {attendee_id}")
    
    logger.info("Checking if attendee exists...")
    exists = db.attendee_exists('TEST123')
    logger.info(f"  Exists: {exists}")
    
    logger.info("Getting attendee...")
    attendee = db.get_attendee('TEST123')
    logger.info(f"  Retrieved: {attendee['name']}")
    
    logger.info("Marking as sent...")
    db.mark_as_sent('TEST123')
    
    logger.info("Checking status...")
    attendee = db.get_attendee('TEST123')
    logger.info(f"  Meeting requested: {attendee['meeting_requested']}")
    logger.info(f"  Status: {attendee['request_status']}")
    
    logger.info("Cleaning up test data...")
    conn = db.get_connection()
    conn.execute('DELETE FROM attendees WHERE profile_id = ?', ('TEST123',))
    conn.commit()
    conn.close()
    
    success = exists and attendee['meeting_requested'] == 1
    if success:
        logger.info("✓ Database operations successful!")
    else:
        logger.error("✗ Database operations failed")
    
    return success

async def run_all_tests():
    """Run all tests."""
    logger.info("="*60)
    logger.info("Web Summit Automation - Test Suite")
    logger.info("="*60)
    
    results = {}
    
    results['login'] = await test_login()
    
    results['extraction'] = await test_profile_extraction()
    
    results['modal'] = await test_meeting_modal()
    
    results['database'] = test_database()
    
    logger.info("\n" + "="*60)
    logger.info("Test Results Summary")
    logger.info("="*60)
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{test_name.capitalize()}: {status}")
    
    all_passed = all(results.values())
    logger.info("="*60)
    if all_passed:
        logger.info("All tests passed! Ready to run automation.")
    else:
        logger.info("Some tests failed. Please review errors above.")
    logger.info("="*60)
    
    return all_passed

if __name__ == '__main__':
    asyncio.run(run_all_tests())


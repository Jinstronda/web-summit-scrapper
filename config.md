# Web Summit Automation Configuration

## Base URLs
- Discovery Page: `https://attend.websummit.com/lis25/discovery?active_tab=attendances`
- Profile Base: `https://attend.websummit.com/lis25/profiles/{profile_id}`

## Selectors

### Discovery Page - Attendee List
```python
# Attendee profile links (contains profile URL and basic info)
ATTENDEE_LINKS = 'a[href*="/lis25/profiles/"]'

# Each attendee link contains:
# - Name (first child text)
# - Badge/Role (e.g., ATTENDEE, SPEAKER, ALPHA, etc.)
# - Title and Company
# - Location/Country
```

### Profile Page - Data Extraction
```python
# Profile data is in the main section
PROFILE_NAME = 'main'  # Look for name in StaticText elements
PROFILE_BADGE = 'main'  # Badge type (ATTENDEE, SPEAKER, etc.)
PROFILE_TITLE = 'main'  # Job title
PROFILE_COMPANY = 'main'  # Company name
PROFILE_BIO = 'main'  # Bio/description text
PROFILE_LOCATION = 'main'  # Location text
PROFILE_INDUSTRY = 'main'  # Industry text
PROFILE_COMMUNITIES = 'tab[aria-label="Communities"]'  # Communities tab

# Request Meeting Button
REQUEST_MEETING_BTN = 'button:has-text("Request Meeting")'
```

### Meeting Request Modal
```python
# Modal appears after clicking Request Meeting
MODAL_DIALOG = '[role="dialog"]'

# Meeting Locations (radio buttons)
LOCATION_RADIO = 'input[type="radio"][name="location"]'
LOCATION_LABELS = '[for^="location_"]'
FIRST_LOCATION = '#location_3407'  # Attendee Meeting Area

# After selecting location, time slots load
TIME_SLOT_RADIO = 'input[type="radio"][name="location_time_slot_id"]'
TIME_SLOT_CARDS = '.slot-card'
FIRST_TIME_SLOT = '#location_time_slot_1456'  # First available slot

# Message textarea
MESSAGE_TEXTAREA = 'textarea[name="description"]#description'
MESSAGE_PLACEHOLDER = 'Tell {name} why you\'d like to meet/What\'s the meeting goal'

# Submit button
SEND_REQUEST_BTN = 'button:has-text("Send request")'

# Close modal
CLOSE_MODAL_BTN = 'button.btn-close'
```

### Pagination / Infinite Scroll
```python
# The page uses infinite scroll - "Loading..." text appears at bottom
LOADING_INDICATOR = 'text="Loading..."'

# Scroll detection
PAGE_END_MARKER = 'text="Loading..."'
```

## Form Fields (Hidden)

These are auto-populated by the site:
```python
FORM_FIELDS = {
    'authenticity_token': 'auto',
    'requester_id': 'auto',  # Your user ID
    'requester_name': 'auto',  # Your name
    'requestee_id': 'auto',  # Target user ID
    'requestee_name': 'auto',  # Target user name
    'location': 'select',  # Radio button value
    'location_time_slot_id': 'select',  # Radio button value
    'description': 'user_input'  # Message text
}
```

## Message Template

```
Hey!
```

**Note:** Replace `{{MESSAGE_PLACEHOLDER}}` with your actual meeting request message before running the automation.

## Settings

### Timeouts (milliseconds)
- PAGE_LOAD_TIMEOUT: 30000
- ELEMENT_WAIT_TIMEOUT: 10000
- MODAL_WAIT_TIMEOUT: 5000
- NAVIGATION_TIMEOUT: 30000

### Retry Logic
- MAX_RETRIES: 3
- RETRY_DELAY: 2000

### Rate Limiting
- DELAY_BETWEEN_REQUESTS: 3000 (3 seconds between each meeting request)
- DELAY_AFTER_SCROLL: 2000 (2 seconds after scrolling)

### Batch Processing
- BATCH_SIZE: 10 (process 10 attendees then checkpoint)
- ENABLE_CHECKPOINTS: true

## Data Fields to Extract

From each attendee profile:
- profile_id (from URL)
- name
- badge/role
- title
- company
- bio
- location
- industry
- communities (JSON array)
- profile_url
- scraped_at (timestamp)
- meeting_requested (boolean)
- request_status (pending/sent/failed)

## Workflow Steps

1. **Initialize**
   - Load cookies from cookies.json
   - Connect to database
   - Navigate to discovery page

2. **Scroll and Collect Profile URLs**
   - Scroll page to trigger infinite loading
   - Collect all profile URLs
   - Stop when no more profiles load

3. **Process Each Profile**
   - Navigate to profile URL
   - Extract all profile data
   - Check database for duplicate
   - If new: Save to database with status='scraped'
   
4. **Send Meeting Request** (if not already sent)
   - Click "Request Meeting" button
   - Wait for modal to appear
   - Select first location (radio button)
   - Wait for time slots to load
   - Select first time slot (radio button)
   - Fill message textarea
   - Click "Send request" button
   - Wait for confirmation/modal close
   - Update database status='meeting_requested'
   
5. **Return to Discovery**
   - Navigate back to discovery page
   - Continue with next profile

6. **Resume Capability**
   - Database tracks processed profiles
   - Skip profiles with status='meeting_requested'
   - Resume from last unprocessed profile

## Error Handling

- **Profile already processed**: Skip to next
- **Element not found**: Retry up to MAX_RETRIES, then skip
- **Network error**: Retry with exponential backoff
- **Modal doesn't appear**: Log error, skip attendee
- **No time slots available**: Mark as unavailable, skip request
- **Rate limit detected**: Wait longer, retry

## Cookies File Format

Save cookies as `cookies.json`:
```json
[
  {
    "name": "_attendee_portal_session",
    "value": "your_session_value",
    "domain": "attend.websummit.com",
    "path": "/"
  }
]
```

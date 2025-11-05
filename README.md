# Web Summit Meeting Request Automation

I built this to save time at Web Summit. Instead of manually clicking through hundreds of attendee profiles to send meeting requests, this script does it automatically.

## What It Does

The script logs into the Web Summit attendee portal, scrolls through the discovery page to find all attendees, extracts their profile data, stores it in a local database, and automatically sends **AI-personalized meeting requests** for each attendee.

Each message is uniquely generated using GPT-5-Mini, selecting from 4 different templates and matching relevant clients based on their profile. No two messages are the same - every one is personalized.

It's built to be resume-able - if something goes wrong or you stop it, it picks up where it left off. No duplicates, no wasted time.

## Setup

### Option 1: Using uv (Recommended - Faster)

```bash
# Deactivate conda if active
conda deactivate

# Install dependencies with uv
uv pip install -r requirements.txt

# Install Playwright browsers
uv run playwright install chromium
```

### Option 2: Using pip

```bash
pip install -r requirements.txt
playwright install chromium
```

Then set up your authentication cookies. You need to be logged into Web Summit in your browser first:

1. Log into https://attend.websummit.com in your browser
2. The cookies are already saved in `cookies.json` (update if needed)

## Configuration

### AI Personalization Setup

The system uses GPT-5-Mini to generate personalized messages. **You need to set your OpenAI API key:**

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY="your-api-key-here"
```

**Windows (CMD):**
```cmd
set OPENAI_API_KEY=your-api-key-here
```

Get your API key from: https://platform.openai.com/api-keys

See `SETUP_AI_MESSAGES.md` for detailed setup instructions.

The AI automatically:
- Selects from 4 different message templates based on each person's profile
- Matches relevant clients from Augusta Labs' portfolio
- Personalizes the "second line" icebreaker for each attendee
- Creates unique messages - no two are the same

## Running

### With uv (if you used uv to install)

```bash
# Deactivate conda first
conda deactivate

# Run the automation
uv run python automation.py
```

### With standard Python

```bash
python automation.py
```

or double-click `run.bat`

The script will:
1. Open a browser (you'll see it working - not headless)
2. Load your cookies to stay authenticated
3. Scroll through the discovery page collecting all attendee URLs
4. For each attendee:
   - Navigate to their profile
   - Extract their info (name, company, role, bio, etc.)
   - Save to SQLite database
   - Click "Request Meeting"
   - Select first available meeting location
   - Select first available time slot
   - Fill in your message
   - Click send
5. Wait 3 seconds between requests to avoid rate limiting
6. Show progress every 10 attendees

## Database

Everything gets saved to `websummit_attendees.db`. You can query it with any SQLite tool:

```bash
sqlite3 websummit_attendees.db
SELECT name, company, title, meeting_requested FROM attendees;
```

The schema tracks:
- Profile data (name, company, title, bio, location, industry, communities)
- Whether a meeting request was sent
- When it was sent
- Any errors that occurred

## Resume Capability

If the script crashes or you stop it:
- Just run it again
- It will skip anyone already in the database with `meeting_requested = 1`
- Continues from where it left off
- No duplicates sent

## Safety Features

- 3-second delay between requests (configurable in `automation.py`)
- Retries on errors
- Logs everything so you can see what happened
- Stores failures in database for review
- Won't send duplicate requests

## Files

- `automation.py` - Main script
- `message_personalizer.py` - AI-powered message personalization
- `database.py` - SQLite database functions
- `config.md` - Configuration and selectors
- `cookies.json` - Your auth cookies
- `requirements.txt` - Python dependencies
- `SETUP_AI_MESSAGES.md` - AI personalization setup guide
- `websummit_attendees.db` - SQLite database (created on first run)

## Customizing Messages

Messages are automatically personalized by AI. To customize the base message template or the 4 second-line templates, edit `message_personalizer.py`:

- `BASE_MESSAGE` - The main message structure
- `SECOND_LINE_TEMPLATES` - The 4 template options the AI chooses from
- `CLIENT_LIST` - Client matching logic by industry

## Customization

Want to change behavior? Edit `automation.py`:

- `MAX_WORKERS` - Number of parallel workers (default: 5)
- `BATCH_SIZE` - Show stats every N attendees (default: 10)
- `DELAY_BETWEEN_REQUESTS` - Time between requests (default: 3000ms)
- `DELAY_AFTER_SCROLL` - Time to wait after scrolling (default: 2000ms)
- `MAX_RETRIES` - How many times to retry on error (default: 3)

### Parallel Processing

The system runs **5 workers in parallel** by default, processing multiple attendees simultaneously. This makes it ~5x faster than sequential processing.

Each worker:
- Has its own browser context (isolated cookies and state)
- Processes its assigned chunk of attendees
- Respects rate limiting with delays

To change the number of workers, edit `MAX_WORKERS` in `automation.py`.

## Troubleshooting

**"Modal did not appear"** - The meeting request modal didn't load. Could be rate limiting or page changes. The script will skip and continue.

**"Failed to send meeting request"** - Something went wrong during the request flow. Check logs for details. These get marked as failed in the database.

**"No new profiles found"** - The infinite scroll stopped loading new attendees. This is expected when you reach the end.

**Cookies expired** - If you get logged out, update `cookies.json` with fresh cookies from your browser.

## Stats

Check progress anytime:

```bash
python -c "import database as db; print(db.get_stats())"
```

Shows:
- Total profiles scraped
- Meeting requests sent
- Pending requests
- Failed requests

## Notes

This was built specifically for Web Summit 2025 (Lisbon). If the site structure changes, you'll need to update selectors in `config.md`.

The script runs with headless=False so you can see what's happening. Set it to True in `automation.py` if you want it to run in the background.

Be respectful with automation. Don't hammer their servers. The 3-second delay is intentional.

## License

Do whatever you want with this. No warranties. Use at your own risk.


# AI-Powered Message Personalization Setup

The automation now uses GPT-5-Mini to generate personalized meeting request messages for each attendee.

## Setup

### 1. Install Dependencies

```bash
pip install openai
```

Or install all requirements:
```bash
pip install -r requirements.txt
```

### 2. Set Your OpenAI API Key

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY="your-api-key-here"
```

**Windows (CMD):**
```cmd
set OPENAI_API_KEY=your-api-key-here
```

**Linux/Mac:**
```bash
export OPENAI_API_KEY="your-api-key-here"
```

**Permanent Setup (Windows):**
1. Search for "Environment Variables" in Windows
2. Add new system/user variable: `OPENAI_API_KEY`
3. Set value to your API key

**Or use .env file:**
Create a `.env` file in the project root:
```
OPENAI_API_KEY=your-api-key-here
```

### 3. Get Your API Key

1. Go to https://platform.openai.com/api-keys
2. Sign up or log in
3. Create a new API key
4. Copy and set it as shown above

## How It Works

For each attendee, the system:

1. **Extracts Profile Data**: Name, company, title, industry, bio, etc.
2. **Matches Relevant Clients**: Automatically selects 1-3 clients from Augusta Labs' portfolio that match the attendee's industry/role
3. **Chooses Template**: AI selects one of 4 second-line templates based on the profile:
   - **Template A**: AI/Technology roles
   - **Template B**: Specific focus/expertise
   - **Template C**: Industry match
   - **Template D**: Generic/browsing fallback
4. **Personalizes**: Fills in the template with specific details from their profile
5. **Generates Message**: Creates the complete personalized message

## Message Structure

Each message follows this format:

```
Dear [Name]

[AI-Generated Second Line - Personalized Icebreaker]

I am a past solo founder that is currently working at Augusta Labs, we are an applied AI lab from Europe working with Fortune 500 companies and governments (incl. Veolia, Sage, Millennium and Avantor), helping them embed AI into core operations to drive tangible performance and efficiency gains.

Would be great to connect while we're both at WebSummit.

Happy to chat via linkedin (https://www.linkedin.com/in/joaopanizzutti) or WhatsApp (+351 911 898 593) if that's easier.

Best,

João Panizzutti

Engineer, Augusta Labs

https://augustalabs.ai
```

## Client Matching

The system automatically matches clients based on:
- **Automotive**: Volkswagen Group, Tata Motors, Volvo Group
- **Energy**: Siemens, Baker Hughes, Halliburton, Weatherford
- **Chemicals/Pharma**: BASF, Croda, Avantor, AstraZeneca
- **Logistics**: DB Schenker, DSV, Kuehne + Nagel, DP World
- **Water/Environmental**: Veolia, ACCIONA
- **Infrastructure**: Ferrovial, ACCIONA
- **Consulting**: McKinsey, Bain, BCG
- **And more...**

## Example Personalized Messages

**For an AI/ML Director:**
```
Dear Sarah Johnson

Saw you're Director of AI at TechCorp, the operational AI challenges you're likely facing are exactly what we've been solving for companies like Siemens and Veolia.
```

**For a logistics specialist:**
```
Dear Michael Chen

Your work in supply chain optimization at Logistics Inc. caught my eye - we've been doing similar AI integration work with DB Schenker.
```

**For someone with specific focus:**
```
Dear Emma Rodriguez

I see you're focused on predictive maintenance systems - that's fascinating because we just wrapped a project doing exactly that for Volkswagen Group.
```

## Testing

Before running the full automation, you can test the personalization:

```python
import message_personalizer as mp

test_data = {
    'name': 'John Doe',
    'company': 'TechCorp',
    'title': 'AI Director',
    'industry': 'Technology',
    'bio': 'Leading AI initiatives for enterprise clients',
    'badge': 'ATTENDEE'
}

message = mp.personalize_message(test_data)
print(message)
```

## Cost

GPT-5-Mini is very cost-effective:
- Each message generation uses ~500-800 tokens
- **Estimated cost: ~$0.001-0.002 per message**

For 1000 attendees: ~$1-2 total

## Troubleshooting

**"OPENAI_API_KEY not set"**
- Make sure you've set the environment variable
- Restart your terminal/IDE after setting it
- Check spelling: `OPENAI_API_KEY` (not `OPENAI_KEY`)

**"API key invalid"**
- Verify your key at https://platform.openai.com/api-keys
- Make sure you copied the full key
- Check for extra spaces or quotes

**Rate Limits**
- The system includes delays between requests
- If you hit rate limits, increase `DELAY_BETWEEN_REQUESTS` in `automation.py`

**Fallback Behavior**
- If API call fails, system uses a generic fallback message
- Check logs for API errors
- All failures are logged in the database

## Notes

- Messages are generated per attendee, so each one is unique
- The AI uses only information from their profile (no fabrication)
- Client matching is automatic based on industry/role
- Template selection is intelligent based on profile depth
- All messages maintain professional tone


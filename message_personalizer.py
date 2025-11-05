import os
import logging
from typing import Dict, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

# Client list organized by industry/domain for matching
CLIENT_LIST = {
    "automotive": ["Volkswagen Group", "Tata Motors", "Volvo Group"],
    "energy": ["Siemens", "Baker Hughes", "Halliburton", "Weatherford International", "John Wood Group"],
    "chemicals": ["BASF SE", "Croda International", "Avantor"],
    "logistics": ["DB Schenker", "DSV", "Kuehne + Nagel", "DP World", "Hutchison Ports", "The Port of Los Angeles"],
    "water_environmental": ["Veolia", "ACCIONA"],
    "infrastructure": ["Ferrovial", "ACCIONA"],
    "pharmaceutical": ["AstraZeneca"],
    "consulting": ["McKinsey & Company", "Bain & Company", "The Boston Consulting Group"],
    "tech_industrial": ["Siemens", "ABB"],
    "media": ["CNN"],
    "testing_certification": ["Bureau Veritas", "DEKRA SE", "SGS SA"],
    "software": ["Sage"],
    "government": ["Portuguese Government"],
    "general": ["Volkswagen Group", "Siemens", "Veolia", "Sage", "Avantor", "AstraZeneca", "ABB", "ACCIONA", "Ferrovial"]
}

# Base message template
BASE_MESSAGE = """Dear {{Name}}

{{Second Line}}

I am a Machine Learning Engineer and past Solo Founder that is currently working at Augusta Labs, we are an applied AI lab from Europe working with Fortune 500 companies and governments (incl. Veolia, Sage, Millennium and Avantor), helping them embed AI into core operations to drive tangible performance and efficiency gains.

Would be great to connect while we're both at WebSummit.

Happy to chat via linkedin (https://www.linkedin.com/in/joaopanizzutti) or WhatsApp (+351 911 898 593) if that's easier.

Best,

João Panizzutti

Engineer, Augusta Labs

https://augustalabs.ai"""

# Second line templates
SECOND_LINE_TEMPLATES = {
    "ai_role": """Saw you're {{their_role}} at {{company}}, the operational AI challenges you're likely facing are exactly what we've been solving for companies like {{relevant_client}}.""",
    
    "specific_focus": """I see you're focused on {{specific_thing_from_their_profile}} - that's fascinating because we just wrapped a project doing exactly that for {{relevant_client}}.""",
    
    "industry_match": """Your work in {{their_industry/domain}} at {{company}} caught my eye - we've been doing similar AI integration work with {{relevant_client_from_similar_space}}.""",
    
    "browsing": """I was browsing the Web Summit attendees site and noticed your work at {{company}} - we've been helping similar companies like {{relevant_client}} with their AI transformation."""
}

def get_openai_client() -> OpenAI:
    """Get OpenAI API client."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    return OpenAI(api_key=api_key)

def match_relevant_clients(attendee_data: Dict) -> list[str]:
    """Match relevant clients based on attendee's company/industry."""
    company = (attendee_data.get('company', '') or '').lower()
    industry = (attendee_data.get('industry', '') or '').lower()
    title = (attendee_data.get('title', '') or '').lower()
    bio = (attendee_data.get('bio', '') or '').lower()
    
    matched_clients = set()
    
    # Industry-based matching
    if any(term in industry or term in bio for term in ['automotive', 'car', 'vehicle', 'auto']):
        matched_clients.update(CLIENT_LIST["automotive"])
    if any(term in industry or term in bio for term in ['energy', 'oil', 'gas', 'petroleum', 'renewable']):
        matched_clients.update(CLIENT_LIST["energy"])
    if any(term in industry or term in bio for term in ['chemical', 'pharma', 'pharmaceutical']):
        matched_clients.update(CLIENT_LIST["chemicals"])
        matched_clients.update(CLIENT_LIST["pharmaceutical"])
    if any(term in industry or term in bio for term in ['logistics', 'supply chain', 'shipping', 'port']):
        matched_clients.update(CLIENT_LIST["logistics"])
    if any(term in industry or term in bio for term in ['water', 'waste', 'environmental', 'sustainability']):
        matched_clients.update(CLIENT_LIST["water_environmental"])
    if any(term in industry or term in bio for term in ['infrastructure', 'construction', 'engineering']):
        matched_clients.update(CLIENT_LIST["infrastructure"])
    if any(term in title or term in bio for term in ['consultant', 'consulting', 'advisory']):
        matched_clients.update(CLIENT_LIST["consulting"])
    if any(term in industry or term in bio for term in ['industrial', 'manufacturing', 'tech']):
        matched_clients.update(CLIENT_LIST["tech_industrial"])
    if any(term in industry or term in bio for term in ['software', 'saas', 'tech']):
        matched_clients.update(CLIENT_LIST["software"])
    
    # If no specific match, use general clients
    if not matched_clients:
        matched_clients.update(CLIENT_LIST["general"][:3])
    
    # Return top 3 most relevant
    return list(matched_clients)[:3]

def personalize_message(attendee_data: Dict) -> str:
    """Generate personalized message using GPT-5-Mini."""
    try:
        client = get_openai_client()
        
        name = attendee_data.get('name', '')
        company = attendee_data.get('company', 'N/A')
        title = attendee_data.get('title', 'N/A')
        industry = attendee_data.get('industry', 'N/A')
        bio = attendee_data.get('bio', '')
        badge = attendee_data.get('badge', '')
        
        relevant_clients = match_relevant_clients(attendee_data)
        clients_str = ", ".join(relevant_clients)
        
        # Build context for AI
        profile_context = f"""
Attendee Profile:
- Name: {name}
- Role/Title: {title}
- Company: {company}
- Industry: {industry}
- Badge Type: {badge}
- Bio: {bio[:500] if bio else 'N/A'}
"""
        
        prompt = f"""<task>
Generate a personalized second line for a Web Summit meeting request message. This line should act as an icebreaker that creates a connection based on similarity.

<attendee_profile>
{profile_context}
</attendee_profile>

<relevant_clients>
Available clients to reference (choose 1-2 most relevant): {clients_str}
</relevant_clients>

<template_options>
You must choose ONE of these 4 templates based on the profile:

Template A (AI/Technology Role) - Use when they work in AI, tech, or have technology-focused roles:
"Saw you're {title} at {company}, the operational AI challenges you're likely facing are exactly what we've been solving for companies like [RELEVANT_CLIENT]."

Template B (Specific Focus) - Use when their profile mentions a specific area, project, or expertise:
"I see you're focused on [SPECIFIC_THING_FROM_PROFILE] - that's fascinating because we just wrapped a project doing exactly that for [RELEVANT_CLIENT]."

Template C (Industry Match) - Use when their industry/domain aligns well with our clients:
"Your work in [INDUSTRY/DOMAIN] at {company} caught my eye - we've been doing similar AI integration work with [RELEVANT_CLIENT]."

Template D (Browsing Fallback) - Use when profile information is sparse or generic:
"I was browsing the Web Summit attendees site and noticed your work at {company} - we've been helping similar companies like [RELEVANT_CLIENT] with their AI transformation."
</template_options>

<instructions>
1. Analyze the profile to determine which template is most effective
2. Fill in the placeholders:
   - [RELEVANT_CLIENT]: Choose 1-2 clients from the list that best match their industry/role
   - [SPECIFIC_THING_FROM_PROFILE]: Extract a specific area, project, or expertise from their bio/title
   - [INDUSTRY/DOMAIN]: Use their industry or a specific domain they work in
3. Make it feel natural, specific, and personal - not generic
4. Keep it concise (1-2 sentences maximum)
5. Only use information present in the profile - don't invent details
</instructions>

<output_format>
Return ONLY the completed second line text. No explanations, no quotes, no markdown formatting. Just the plain text that will replace {{Second Line}} in the message.
</output_format>"""

        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        second_line = response.choices[0].message.content.strip()
        
        # Build final message
        message = BASE_MESSAGE.replace("{{Name}}", name)
        message = message.replace("{{Second Line}}", second_line)
        
        logger.info(f"Generated personalized message for {name}")
        return message
        
    except Exception as e:
        logger.error(f"Error personalizing message: {e}")
        # Fallback to generic message
        name = attendee_data.get('name', 'there')
        fallback_second_line = f"I noticed your work at {attendee_data.get('company', 'your company')} - we've been helping similar companies like {match_relevant_clients(attendee_data)[0]} with their AI transformation."
        
        message = BASE_MESSAGE.replace("{{Name}}", name)
        message = message.replace("{{Second Line}}", fallback_second_line)
        return message


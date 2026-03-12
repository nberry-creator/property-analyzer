import streamlit as st
from openai import OpenAI
import json
import re

st.set_page_config(page_title="Property Quick Analyzer", layout="wide")
st.title("🏠 Property Quick Analyzer")
st.caption("Live photos • Valuation • Red flags • Off-market check | Powered by Grok")

# === AUTOMATIC API KEY (from secrets) ===
if "XAI_API_KEY" in st.secrets:
    api_key = st.secrets["XAI_API_KEY"]
    st.sidebar.success("✅ Secure key loaded automatically")
else:
    api_key = st.sidebar.text_input("🔑 Paste your xAI API Key here (temporary)", type="password")

if not api_key:
    st.info("👈 Add your key in Streamlit Secrets")
    st.stop()

address = st.text_input("Enter full property address (US only)", 
                        placeholder="8800 Southwest 31st Terrace Oklahoma City OK 73179")

if st.button("🔍 Analyze with Grok", type="primary"):
    if not address:
        st.error("Please enter an address")
        st.stop()
    
    with st.spinner("Grok is searching Zillow, Redfin, Realtor.com, county records... (25–55 seconds)"):
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1"
        )
        
        system_prompt = """You are an expert real estate analyst. Use your web_search tool to research the given address in real time.

STRICT LISTING RULES:
- ONLY set "off_market": false if there is a true active "For Sale" listing with current asking price.
- For Pending listings, still set "off_market": false and extract photos + full details.

You MUST return ONLY clean raw JSON. No markdown, no **bold**, no extra text.

Especially for photos: If the property is listed or has a details page, ALWAYS extract 5–8 DIRECT high-resolution image URLs from the listing gallery (full .jpg or .webp links from Zillow/Redfin/Realtor — not thumbnails).

Exact format:
{
  "off_market": true/false,
  "listing_status": "Active / Pending / Sold / Off Market / etc.",
  "listing_url": "full URL or null",
  "photos": ["https://direct-image-url1.jpg", ...] (max 8),
  "valuation_estimate": "e.g. $250,000–$270,000",
  "current_list_price": "$250,990 or N/A",
  "last_sale": "Sold MM/DD/YYYY for $XXX,XXX or N/A",
  "zestimate": "$258,400 or N/A",
  "redfin_estimate": "$252,100 or N/A",
  "county_assessed_value": "$240,000 or N/A",
  "red_flags": ["Red flag 1...", ...],
  "summary": "2–4 sentence purchase advice"
}"""
        
        try:
            response = client.responses.create(
                model="grok-4.20-beta-latest-non-reasoning",
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Address: {address}"}
                ],
                tools=[{"type": "web_search"}]
            )
            
            # Robust text extraction + cleaning
            raw_text = ""
            if hasattr(response, "output_text") and response.output_text:
                raw_text = response.output_text.strip()
            elif hasattr(response, "output") and response.output:
                for item in reversed(response.output):
                    if hasattr(item, "content") and item.content:
                        for content_item in item.content:
                            if hasattr(content_item, "text") and content_item.text:
                                raw_text = content_item.text.strip()
                                break
                        if raw_text:
                            break
            
            raw_text = raw_text.strip()
            raw_text = re.sub(r'^\s*\*\*', '', raw_text)
            raw_text = re.sub(r'\*\*\s*$', '', raw_text)
            raw_text = raw_text.strip('*').strip()
            json_match = re.search(r'(\{.*\})', raw_text, re.DOTALL)
            if json_match:
                raw_text = json_match.group(1)
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```", 2)[1].strip() if len(raw_text.split("```", 2)) > 1 else raw_text
            
            data = json.loads(raw_text)
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.stop()

    # === RESULTS DISPLAY ===
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📸 Current Listing Photos")
        photos = data.get("photos", [])
        if photos:
            for url in photos[:8]:
                st.image(url, use_column_width=True)
        else:
            st.info("No current listing photos found (may be very new or Pending)")
    
    with col2:
        st.subheader("Status")
        status = data.get("listing_status", "Unknown")
        if data.get("off_market"):
            st.error(f"🔴 {status}")
        else:
            st.success(f"🟢 {status}")
        
        # Clean full valuation display (no truncation)
        st.subheader("Valuation Estimate")
        st.markdown(f"**{data.get('valuation_estimate', 'N/A')}**")
        
        # NEW BULLET SECTION
        st.subheader("📊 Valuation Details")
        st.markdown(f"""
- **Last Sale**: {data.get('last_sale', 'N/A')}
- **Zestimate (Zillow)**: {data.get('zestimate', 'N/A')}
- **Redfin Estimate**: {data.get('redfin_estimate', 'N/A')}
- **County Assessed Value**: {data.get('county_assessed_value', 'N/A')}
        """)
        
        st.subheader("🚩 Red Flags")
        flags = data.get("red_flags", [])
        if flags:
            for flag in flags:
                st.warning(flag)
        else:
            st.success("No major red flags detected")
    
    st.subheader("📋 Grok Summary")
    st.markdown(data.get("summary", "No summary returned"))
    
    if data.get("listing_url"):
        st.markdown(f"[🔗 View Full Listing]({data['listing_url']})")

    with st.expander("🔧 Debug: Raw JSON from Grok"):
        st.json(data)

import streamlit as st
from openai import OpenAI
import json
import re

st.set_page_config(page_title="Property Quick Analyzer", layout="wide")
st.title("🏠 Property Quick Analyzer")
st.caption("Live photos • Valuation • Red flags • Off-market check | Powered by Grok")

# === AUTOMATIC API KEY ===
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
        
        system_prompt = """You are an expert real estate analyst AND my trusted personal real estate advisor in Oklahoma City.

**CRITICAL PHOTO INSTRUCTIONS** (do this every time):
Find the Zillow/Redfin/Realtor.com listing page for the exact address. Open the photo gallery. Extract 5–8 **direct full-resolution image URLs** that will load directly in a browser. They must be real CDN links (usually start with https://photos.zillowstatic.com/fp/ or https://ap.rdcpix.com/ or similar high-res gallery src). Never return thumbnails or placeholders. If photos exist, return them — this property has 33+ on Zillow.

**SUMMARY INSTRUCTIONS**:
Write the "summary" field EXACTLY as if you are my personal real estate advisor in Oklahoma City. Use natural, professional, conversational language. Be thorough (4–6 sentences). Always cover:
- Key features and condition of THIS specific property
- Pros and cons of the home and lot
- Buffalo Farms subdivision and southwest Oklahoma City area (growth, amenities, future potential, market trends)
- Western Heights School District (ratings and implications for families)
- Risks of new construction + Pending status (builder warranty, HOA fees/rules, resale value in new community, backup offer risks)
- What I should do next (inspections, builder walk-through, HOA docs review, financing tips, etc.)
- Your honest recommendation at the current price

Return ONLY clean raw JSON. No markdown, no bold, no extra text. Use normal spacing and punctuation in every field.

Exact format:
{
  "off_market": true/false,
  "listing_status": "Active / Pending / Sold / Off Market / etc.",
  "listing_url": "full URL or null",
  "photos": ["https://photos.zillowstatic.com/fp/...jpg", ...] (max 8),
  "valuation_estimate": "e.g. $240,000–$265,000",
  "current_list_price": "$250,990 or N/A",
  "last_sale": "Sold MM/DD/YYYY for $XXX,XXX or N/A",
  "zestimate": "$258,400 or N/A",
  "redfin_estimate": "$252,100 or N/A",
  "county_assessed_value": "$240,000 or N/A",
  "red_flags": ["Red flag 1...", ...],
  "summary": "Your thorough personal advisor paragraph here"
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

    # === RESULTS ===
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📸 Current Listing Photos")
        photos = data.get("photos", [])
        if photos:
            for url in photos[:8]:
                st.image(url, use_column_width=True)
        else:
            st.info("No current listing photos found (this sometimes happens on brand-new builds — try again in a few hours)")
    
    with col2:
        st.subheader("Status")
        status = data.get("listing_status", "Unknown")
        if data.get("off_market"):
            st.error(f"🔴 {status}")
        else:
            st.success(f"🟢 {status}")
        
        st.subheader("Valuation Estimate")
        st.markdown(f"**{data.get('valuation_estimate', 'N/A')}**")
        
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
    
    st.subheader("📋 Grok Summary (My Personal Advice)")
    st.markdown(data.get("summary", "No summary returned"))
    
    if data.get("listing_url"):
        st.markdown(f"[🔗 View Full Listing]({data['listing_url']})")

    with st.expander("🔧 Debug: Raw JSON from Grok"):
        st.json(data)

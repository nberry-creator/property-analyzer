import streamlit as st
from openai import OpenAI
import json
import re

st.set_page_config(page_title="Property Quick Analyzer", layout="wide")
st.title("🏠 Property Quick Analyzer")
st.caption("Valuation • Red flags • Off-market check | Powered by Grok")

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
                        placeholder="13120 4th St Grandview, MO 64030")

if st.button("🔍 Analyze with Grok", type="primary"):
    if not address:
        st.error("Please enter an address")
        st.stop()
    
    with st.spinner("Grok is searching Zillow, Redfin, Realtor.com, county records... (25–55 seconds)"):
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1"
        )
        
        system_prompt = """You are my expert personal real estate advisor. Use web_search to research the exact address.

Return ONLY clean raw JSON. No markdown, no extra text.

Exact format:
{
  "off_market": true/false,
  "listing_status": "Active / Pending / Sold / Off Market / etc.",
  "listing_url": "full URL or null",
  "valuation_estimate": "e.g. $240,000–$280,000",
  "current_list_price": "$259,900 or N/A",
  "days_on_market": "45 days or N/A",
  "last_sale": "exact text here or New Construction - No prior sale recorded",
  "zestimate": "exact text here or Zestimate not yet available on Zillow - new construction",
  "redfin_estimate": "exact text here or Redfin Estimate not available yet",
  "county_assessed_value": "exact text here or County assessment not yet updated",
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

    # === CLEAN RESULTS (no photos, standardized formatting) ===
    st.subheader("Status")
    status = data.get("listing_status", "Unknown")
    if data.get("off_market"):
        st.error(f"🔴 {status}")
    else:
        st.success(f"🟢 {status}")

    # Valuation Estimate - clean metric
    st.subheader("Valuation Estimate")
    st.metric(label="", value=data.get("valuation_estimate", "N/A"))

    # New Listing Info section
    st.subheader("📋 Listing Info")
    col_a, col_b = st.columns(2)
    with col_a:
        st.metric("List Price", data.get("current_list_price", "N/A"))
    with col_b:
        st.metric("Days on Market", data.get("days_on_market", "N/A"))
    
    if data.get("listing_url"):
        st.markdown(f"[🔗 View Full Listing]({data['listing_url']})")

    # Valuation Details
    st.subheader("📊 Valuation Details")
    st.markdown(f"""
- **Last Sale**: {data.get('last_sale', 'N/A')}
- **Zestimate (Zillow)**: {data.get('zestimate', 'N/A')}
- **Redfin Estimate**: {data.get('redfin_estimate', 'N/A')}
- **County Assessed Value**: {data.get('county_assessed_value', 'N/A')}
    """)

    # Red Flags
    st.subheader("🚩 Red Flags")
    flags = data.get("red_flags", [])
    if flags:
        for flag in flags:
            st.warning(flag)
    else:
        st.success("No major red flags detected")

    # Summary
    st.subheader("📋 Grok Summary (My Personal Advice)")
    st.markdown(data.get("summary", "No summary returned"))

    with st.expander("🔧 Debug: Raw JSON from Grok"):
        st.json(data)

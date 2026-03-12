import streamlit as st
from openai import OpenAI
import json
import re

st.set_page_config(page_title="Property Quick Analyzer", layout="wide")
st.title("🏠 Property Quick Analyzer")
st.caption("Live photos • Valuation • Red flags • Off-market check | Powered by Grok")

# === AUTOMATIC API KEY LOADING (no more typing!) ===
if "XAI_API_KEY" in st.secrets:
    api_key = st.secrets["XAI_API_KEY"]
    st.sidebar.success("✅ Secure key loaded automatically")
else:
    api_key = st.sidebar.text_input("🔑 Paste your xAI API Key here (temporary fallback)", type="password", help="Get it from console.x.ai")

if not api_key:
    st.info("👈 Add your key in Streamlit Secrets (see instructions) or use the sidebar for now")
    st.stop()

address = st.text_input("Enter full property address (US only)", 
                        placeholder="12345 N May Ave, Oklahoma City, OK 73120")

if st.button("🔍 Analyze with Grok", type="primary"):
    if not address:
        st.error("Please enter an address")
        st.stop()
    
    with st.spinner("Grok is searching Zillow, Redfin, Realtor.com, county records... (20–50 seconds)"):
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1"
        )
        
        system_prompt = """You are an expert real estate analyst. Use your web_search tool to research the given address in real time.

**STRICT RULES FOR LISTING STATUS** (follow exactly):
- Cross-check Zillow, Redfin, and Realtor.com.
- ONLY set "off_market": false if you see an ACTIVE "For Sale" or "Active" listing WITH a current asking price.
- If the page says "currently not for sale", "Off Market", "Sold", "Pending", or there is only a Zestimate with no asking price → "off_market": true and "listing_status": "Off Market".
- The Zillow details page exists for almost every property — do NOT assume it is listed just because the page exists.

You MUST return ONLY clean raw JSON (no markdown, no **bold**, no explanations, no backticks). Always include a useful "summary" field with 2-4 sentences of purchase advice.

Exact format:
{
  "off_market": true/false,
  "listing_status": "Active / Pending / Sold / Off Market / etc.",
  "listing_url": "full URL if found or null",
  "photos": ["direct-image-url1.jpg", ...] (max 8),
  "valuation_estimate": "e.g. $450,000–$480,000 (Zestimate $462k)",
  "current_list_price": "$455,000 or N/A",
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
            
        except json.JSONDecodeError:
            st.error("❌ JSON parsing failed. Here's what Grok returned:")
            st.code(raw_text or "EMPTY")
            st.stop()
        except Exception as e:
            st.error(f"API Error: {str(e)}")
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
            st.info("No current listing photos (property is likely off-market)")
    
    with col2:
        st.subheader("Status")
        status = data.get("listing_status", "Unknown")
        if data.get("off_market"):
            st.error(f"🔴 {status}")
        else:
            st.success(f"🟢 {status}")
        st.metric("Valuation Estimate", data.get("valuation_estimate", "N/A"))
        if data.get("current_list_price") and data.get("current_list_price") != "N/A":
            st.metric("List Price", data.get("current_list_price"))
        
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

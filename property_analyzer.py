import streamlit as st
from openai import OpenAI
import json
import re

st.set_page_config(page_title="Property Quick Analyzer", layout="wide")

# === CUSTOM ARIAL FONT STYLING (14px text, 25px headings) ===
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Arial:wght@400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Arial', sans-serif !important;
        font-size: 14px !important;
    }
    
    h1, h2, h3, h4, h5, h6, .stSubheader {
        font-family: 'Arial', sans-serif !important;
        font-size: 25px !important;
        font-weight: 700 !important;
    }
    
    .stMetric label, .stMarkdown p, .stAlert, .stWarning {
        font-family: 'Arial', sans-serif !important;
        font-size: 14px !important;
    }
    
    .stMetric div[data-testid="stMetricValue"] {
        font-size: 18px !important;
    }
</style>
""", unsafe_allow_html=True)

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
                        placeholder="8800 Southwest 31st Terrace Oklahoma City OK 73179")

def clean_text(text):
    if not text:
        return text
    text = re.sub(r'(\d),(\d)', r'\1, \2', text)
    text = re.sub(r'(\d)kand', r'\1k and', text)
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    text = re.sub(r'(\d)([A-Za-z])', r'\1 \2', text)
    text = re.sub(r'([A-Za-z])(\d)', r'\1 \2', text)
    text = text.replace("whileRedfin", "while Redfin")
    text = text.replace("Propertytaxes", "Property taxes")
    text = re.sub(r'\s+', ' ', text).strip()
    return text

if st.button("🔍 Analyze with Grok", type="primary"):
    if not address:
        st.error("Please enter an address")
        st.stop()
    
    with st.spinner("Grok is searching Zillow, Redfin, Realtor.com, county records... (25–55 seconds)"):
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1"
        )
        
        system_prompt = """You are my expert personal real estate advisor in Oklahoma City. Use web_search for the exact address.

Return ONLY clean raw JSON. No markdown, no extra text.

In the summary field, write in perfect natural English with proper spacing, commas, periods, and punctuation. Never glue words or numbers together.

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
  "summary": "Your thorough personal advisor paragraph here with perfect spacing"
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
            
            if "summary" in data:
                data["summary"] = clean_text(data["summary"])
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.stop()

    # === CLEAN RESULTS ===
    st.subheader("Status")
    status = data.get("listing_status", "Unknown")
   

import streamlit as st
import requests

# Page Configuration
st.set_page_config(
    page_title="ERS - Log Analysis Console",
    page_icon="🛡️",
    layout="wide"
)

# Custom Styling
st.markdown("""
    <style>
        .stApp { background-color: #0f172a; color: #f8fafc; }
        .sidebar .sidebar-content { background-color: #1e293b; }
        div.stButton > button { background-color: #0284c7; color: white; font-weight: bold; border-radius: 6px; width: 100%; }
        div.stButton > button:hover { background-color: #0369a1; }
        .response-box { background-color: #1e293b; padding: 20px; border-radius: 8px; border: 1px solid #334155; margin-top: 15px; }
    </style>
""", unsafe_allow_html=True)

API_URL = "http://127.0.0.1:8000"

st.title("🛡️ ERS: Event & Error RAG Console")
st.caption("Interrogate system logs using natural language powered by local LLMs & ChromaDB")

# Sidebar for Database Health & Stats
with st.sidebar:
    st.header("⚙️ Database Status")
    if st.button("Check Connection & Stats"):
        try:
            res = requests.get(f"{API_URL}/db/stats", timeout=3)
            if res.status_code == 200:
                stats = res.json()
                st.success("Connected to FastAPI Backend")
                st.metric("Total Indexed Logs", stats.get("total_logs_stored", 0))
            else:
                st.error("Backend error fetching stats")
        except Exception:
            st.error("Unable to connect to FastAPI server (127.0.0.1:8000)")
    
    st.divider()
    st.markdown("### 💡 Example Queries")
    st.markdown("* *Show me critical errors in the payment service*")
    st.markdown("* *Are there any SQL injection or security threats?*")
    st.markdown("* *List recent database connection failures*")

# Query Form Interface
st.subheader("🔍 Search & Analyze Logs")

with st.form(key="query_form"):
    user_query = st.text_input(
        "Natural Language Query",
        placeholder="e.g., What caused the payment service failure?"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        service_filter = st.selectbox(
            "Filter by Service Name (Optional)",
            ["", "auth-service", "payment-service", "order-service", "inventory-service"]
        )
    with col2:
        severity_filter = st.selectbox(
            "Filter by Severity (Optional)",
            ["", "CRITICAL", "ERROR", "WARNING", "INFO"]
        )

    submit_button = st.form_submit_button(label="Ask RAG Assistant")

# Handle Response
if submit_button:
    if not user_query.strip():
        st.warning("Please enter a query before submitting.")
    else:
        payload = {"query": user_query}
        if service_filter:
            payload["service_name"] = service_filter
        if severity_filter:
            payload["severity"] = severity_filter

        with st.spinner("Retrieving logs from ChromaDB & querying Ollama..."):
            try:
                response = requests.post(f"{API_URL}/query", json=payload, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    st.markdown("### 📝 Assistant Response:")
                    st.info(data.get("response", "No response received."))
                else:
                    st.error(f"Error {response.status_code}: {response.text}")
            except requests.exceptions.RequestException as e:
                st.error(f"Failed to reach server: {e}")
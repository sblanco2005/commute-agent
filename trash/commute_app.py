import streamlit as st
import asyncio
from agent.commute_agent import trigger_commute_agent

st.set_page_config(page_title="🚇 Smart Commute Agent", layout="centered")

st.title("🚶‍♂️ Smart Commute Assistant")

# Trigger logic
if st.button("🚀 Trigger Commute Agent"):
    with st.spinner("Checking your route..."):
        result = asyncio.run(trigger_commute_agent(location="59th & Lex"))

        st.success("Commute monitoring started.")
        st.markdown("### 📍 Status at " + result["timestamp"])

        st.subheader("🚇 Subway – 59th & Lex (Downtown)")
        for train in result["subway"]:
            st.markdown(f"- {train}")

        st.subheader("🚉 NJ Transit – NY Penn → Newark Penn")
        if result["nj_transit"].get("delayed"):
            st.error("⚠️ Delays detected on NJ Transit!")
        else:
            st.success("✅ NJ Transit running on time.")

        st.markdown("**Next Trains:**")
        for train in result["nj_transit"].get("next_trains", []):
            st.markdown(f"- {train['time']} ({train['status']})")
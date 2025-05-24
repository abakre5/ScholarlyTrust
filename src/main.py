"""
main.py

Author: Abhishek Bakare (https://www.linkedin.com/in/abhishekbakare/)
Contact: abakre5@gmail.com

This is the main entry point for the ScholarlyTrust Streamlit application.
It handles user interaction, input validation, and orchestrates the workflow for:
- Checking the credibility of journals and research papers using their ISSN, name, DOI, or title.
- Displaying confidence scores and detailed rationales based on trusted scholarly metadata and rule-based assessment.
- Presenting results in a user-friendly, interactive web interface.
"""
import json
import os
import traceback
import streamlit as st
import requests
import re

from api_utils import ERROR_STATE, HIJACKED_ISSN, NOT_FOUND, get_journal_assessment, get_journal_credibility, get_paper_credibility, get_paper_metadata_v2, get_journal_metadata, get_research_paper_assessment


def validate_issn(issn):
    """Validate ISSN format (e.g., 1234-5678)."""
    pattern = r'^\d{4}-\d{4}$'
    return bool(re.match(pattern, issn))

def validate_title(title):
    """Validate title (non-empty and reasonable length)."""
    return len(title.strip()) > 0 and len(title) <= 500

def main():
    st.set_page_config(
        page_title="ScholarlyTrust: Journal & Paper Credibility Checker",
        page_icon="🔎",
        layout="centered"
    )
    
    st.title("🔎 ScholarlyTrust: Journal & Paper Credibility Assessment")
    st.write("Assess the credibility and integrity of journals (by ISSN or Name) or research papers (by DOI or Title) using trusted scholarly data sources.")
    
    # Add disclaimer
    st.warning("**Disclaimer:** Results are based on available data and algorithms and may not be 100% accurate.")    
    
    try:
        check_type = st.radio("Select check type:", ("Journal", "Research Paper"))
        
        if check_type == "Journal":
            input_type = st.radio("Select journal input type (ISSN is preferred input type):", ("ISSN", "Name"))
            if input_type == "Name":
                st.info("The journal name should be an exact match (case-insensitive, but otherwise identical to the official journal name).")
            journal_input = st.text_input(f"Enter journal {input_type} (e.g., ISSN: 1092-2172, Name: Journal of Molecular Biology)", "")
            if st.button("Check Journal"):
                if not journal_input:
                    st.error(f"Please enter a valid journal {input_type}.")
                    return
                
                if input_type == "ISSN" and not validate_issn(journal_input):
                    st.error("Invalid ISSN format. Please use a format like 1234-5678.")
                    return
                
                with st.spinner("Analyzing your request..."):
                    try:
                        journal_input = journal_input.strip()
                        assessment = None
                        if input_type == "ISSN":
                            assessment = get_journal_assessment(journal_input, True)
                        else:  # Input type is "Name"
                            assessment = get_journal_assessment(journal_input, False)  # You need to implement this function

                        if assessment == ERROR_STATE:
                            st.error("An error occurred while processing your request. Please try again later.")
                            return
                        elif assessment == NOT_FOUND:
                            st.error(
                                "No matching journal was found in our trusted scholarly databases. "
                                "Please double-check the ISSN or journal name for accuracy. "
                                "If you believe this is a reputable journal, it may not be indexed in OpenAlex or Crossref yet, "
                                "or there may be a typo in your input. Try searching with the official ISSN (preferred) or the exact journal name as listed by the publisher. "
                                "If the problem persists, the journal may not be recognized by major scholarly indices."
                            )
                            return
                        
                        st.header("Journal Assessment")
                        st.markdown(assessment, unsafe_allow_html=True)
                        
                    except Exception as e:
                        st.error(f"An error occurred: {e}")
                        traceback.print_exc()
                        message_something_went_wrong()
                        return
                
        else:
            input_type = st.radio("Select paper input type(DOI is preferred input type):", ("DOI", "Title"))
            if input_type == "Title":
                st.info("The research paper title should be an exact match (case-insensitive, but otherwise identical to the official research paper name).")
            paper_input = st.text_input(f"Enter paper {input_type} (e.g., DOI: 10.1128/mmbr.00144-23, Title: Microbiology of human spaceflight: microbial responses to mechanical forces that impact health and habitat sustainability)", "")
            if st.button("Check Paper"):
                if not paper_input:
                    st.error(f"Please enter a valid {input_type}.")
                    return
                if input_type == "Title" and not validate_title(paper_input):
                    st.error("Invalid title. Please enter a non-empty title (up to 500 characters).")
                    return
                
                with st.spinner("Analyzing your request..."):
                    try:
                        paper_input = paper_input.strip()
                        assessment = get_research_paper_assessment(paper_input, input_type.lower())
                        if assessment == ERROR_STATE:
                            st.error("An error occurred while processing your request. Please try again later.")
                            return
                        elif assessment == NOT_FOUND:
                            st.error(
                                "No matching research paper was found in our trusted scholarly databases. "
                                "Please double-check the DOI or paper title for accuracy. "
                                "If you believe this is a reputable research paper, it may not be indexed in OpenAlex or Crossref yet, "
                                "or there may be a typo in your input. Try searching with the official DOI (preferred) or the exact paper title as listed by the publisher. "
                                "If the problem persists, the paper may not be recognized by major scholarly indices."
                            )
                            return

                        st.header("Research Paper Assessment")
                        st.markdown(assessment, unsafe_allow_html=True)
                    except Exception:
                        message_something_went_wrong()
                        return
                
                

    except Exception:
        st.error("An unexpected error occurred OUTER")
        message_something_went_wrong()
    
    st.markdown(
        """
        <div style="text-align: center; margin-top: 12px; font-size: 12px; color: #555;">
            Powered by <a href="https://www.anthropic.com/" target="_blank">Anthropic</a>, <a href="https://openalex.org/" target="_blank">OpenAlex</a> & <a href="https://www.crossref.org/" target="_blank">Crossref</a><br> 
            Developed by <a href="https://www.linkedin.com/in/abhishekbakare/" target="_blank">Abhishek Bakare</a>
        </div>
        """,
        unsafe_allow_html=True
    )

def display_confidence(confidence, is_journal=True):
    """Display the confidence level and corresponding message."""
    if confidence >= 70:
        st.success(f"This {'journal' if is_journal else 'research paper'} demonstrates strong indicators of legitimacy ({confidence}% confidence).")
    elif confidence > 40:
        st.warning(f"This {'journal' if is_journal else 'research paper'} shows several questionable indicators and should be treated with caution ({confidence}% confidence).")
    else:    
        st.error(f"This {'journal' if is_journal else 'research paper'} is likely predatory with {confidence}% confidence.")

def display_investigation_summary(reason):
    st.subheader("Investigation Summary")
    st.markdown(reason, unsafe_allow_html=True)

def message_something_went_wrong():
    """Display a message indicating something went wrong."""
    st.error("Something went wrong. Please contact the administrator at abakre5@gmail.com")

if __name__ == "__main__":
    main()
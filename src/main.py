"""
main.py

Author: Abhishek Bakare (https://www.linkedin.com/in/abhishekbakare/)
Contact: abakre5@gmail.com

This is the main entry point for the ScholarlyTrust Streamlit app.
It handles user interaction, input validation, and orchestrates the workflow for:
- Checking the credibility of journals and research papers using their ISSN, name, DOI, or title.
- Displaying confidence scores and detailed rationales based on trusted scholarly metadata and rule-based assessment.
- Presenting results in a user-friendly, interactive web interface.
"""
import json
import os
import streamlit as st
import requests
import re

from api_utils import ERROR_STATE, HIJACKED_ISSN, get_journal_credibility, get_paper_credibility, get_paper_metadata_v2, get_journal_metadata


def validate_issn(issn):
    """Validate ISSN format (e.g., 1234-5678)."""
    pattern = r'^\d{4}-\d{4}$'
    return bool(re.match(pattern, issn))

def validate_title(title):
    """Validate title (non-empty and reasonable length)."""
    return len(title.strip()) > 0 and len(title) <= 500

def main():
    st.title("ScholarlyTrust: Research Integrity Checker")
    st.write("Check the legitimacy of a journal (by ISSN or Name) or a research paper (by DOI or Title).")
    
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
                        if input_type == "ISSN":
                            metadata = get_journal_metadata(journal_input, True)
                        else:  # Input type is "Name"
                            metadata = get_journal_metadata(journal_input, False)  # You need to implement this function
                        
                        if metadata is ERROR_STATE:
                            message_something_went_wrong()
                            return
                        if metadata is HIJACKED_ISSN:
                            st.error(f"This journal is definitely predatory as it is marked as a hijacked journal.")
                            return
                        if not metadata or not isinstance(metadata, dict):
                            st.error(
                                "We could not locate this paper in any of our trusted scholarly databases, and no reliable metadata is available. "
    "If you are confident that your input is correct, this strongly suggests the work is not recognized by reputable academic sources. "
    "Otherwise, please carefully review your input for possible errors or typos."
                            )                       
                            return
                        
                        confidence, reason = get_journal_credibility(metadata)
                        if confidence is ERROR_STATE:
                            st.error("Something went wrong.")
                            return
                        display_confidence(confidence, is_journal=True)
                        display_investigation_summary(reason)
                    except Exception:
                        st.error("An unexpected error occurred while retrieving journal data. Please try again or contact support.")
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
                        metadata = get_paper_metadata_v2(paper_input, input_type.lower())
                        if metadata is ERROR_STATE:
                            message_something_went_wrong()
                            return
                        if not metadata or not isinstance(metadata, dict):
                            st.error(
                                "We could not locate this paper in any of our trusted scholarly databases, and no reliable metadata is available. "
    "If you are confident that your input is correct, this strongly suggests the work is not recognized by reputable academic sources. "
    "Otherwise, please carefully review your input for possible errors or typos."
                            )
                            return
                        
                        confidence, reason = get_paper_credibility(metadata)
                        if confidence is ERROR_STATE or reason is ERROR_STATE:
                            message_something_went_wrong()
                            return
                        display_confidence(confidence, is_journal=False)
                        display_investigation_summary(reason)
        
                    except Exception:
                        message_something_went_wrong()
                        return
                
                

    except Exception:
        message_something_went_wrong()
    
    st.markdown(
        """
        <div style="text-align: center; margin-top: 12px; font-size: 12px; color: #555;">
            Powered by <a href="https://www.anthropic.com/" target="_blank">Anthropic</a> & <a href="https://openalex.org/" target="_blank">OpenAlex</a><br>
            Developed by <a href="https://www.linkedin.com/in/abhishekbakare/" target="_blank">Abhishek Bakare</a>
        </div>
        """,
        unsafe_allow_html=True
    )

def display_confidence(confidence, is_journal=True):
    """Display the confidence level and corresponding message."""
    if confidence >= 70:
        st.success(f"This {'journal' if is_journal else 'research paper'} demonstrates strong indicators of legitimacy ({confidence}% confidence).")
    elif confidence > 30:
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
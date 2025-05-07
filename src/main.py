import os
import streamlit as st
import requests
import re

from api_utils import HIJACKED_ISSN, is_in_doaj, get_journal_metadata, get_paper_metadata, get_journal_confidence, get_paper_confidence

def validate_issn(issn):
    """Validate ISSN format (e.g., 1234-5678)."""
    pattern = r'^\d{4}-\d{4}$'
    return bool(re.match(pattern, issn))

def validate_title(title):
    """Validate title (non-empty and reasonable length)."""
    return len(title.strip()) > 0 and len(title) <= 500

def main():
    st.title("ScholarlyTrust: Research Integrity Checker")
    st.write("Check the legitimacy of a journal (by ISSN) or a research paper (by DOI or title).")
    
    try:
        check_type = st.radio("Select check type:", ("Journal", "Research Paper"))
        
        if check_type == "Journal":
            input_type = st.radio("Select journal input type:", ("Name", "ISSN"))
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
                        if input_type == "ISSN":
                            metadata = get_journal_metadata(journal_input, True)
                        else:  # Input type is "Name"
                            metadata = get_journal_metadata(journal_input, False)  # You need to implement this function
                        
                        if metadata is HIJACKED_ISSN:
                            st.error(f"This journal is definitely predatory as it is marked as a hijacked journal.")
                            return
                        if not metadata or not isinstance(metadata, dict):
                            st.error("The journal could not be found. Please verify the input or consider that the journal might not be legitimate.")
                            return
                        
                        try:
                            confidence = get_journal_confidence(metadata)
                            if confidence >= 60:
                                st.success(f"This journal is likely legitimate with {confidence}% confidence.")
                            elif confidence > 30:
                                st.warning(f"This journal is questionable with {confidence}% confidence.")
                            else:
                                st.error(f"This journal is likely predatory with {confidence}% confidence.")
                            reason = generate_journal_reason(confidence, metadata)
                        except ValueError:
                            st.error("Invalid data received from the analysis service. Please try again later.")
                            return
                        except Exception:
                            st.error("An unexpected error occurred during analysis. Please try again or contact support.")
                            return
                    
                    except requests.RequestException:
                        st.error("Unable to connect to the data source. Please check your internet connection and try again.")
                        return
                    except Exception:
                        st.error("An unexpected error occurred while retrieving journal data. Please try again or contact support.")
                        return
                
                st.subheader("Journal Metadata")
                with st.expander("View Journal Metadata"):
                    st.write(f"**Title**: {str(metadata.get('title', 'Unknown'))}")
                    st.write(f"**Publisher**: {str(metadata.get('publisher', 'Unknown'))}")
                    st.write(f"**Homepage URL**: {str(metadata.get('homepage_url', 'N/A'))}")
                    st.write(f"**In DOAJ**: {'Yes' if metadata.get('is_in_doaj', False) else 'No'}")
                    st.write(f"**Is Open Access**: {'Yes' if metadata.get('is_open_access', False) else 'No'}")
                    st.write(f"**Country Code**: {str(metadata.get('country_code', 'Unknown'))}")
                    st.write(f"**Total Works**: {str(metadata.get('works_count', 'N/A'))}")
                    st.write(f"**Cited By Count**: {str(metadata.get('cited_by_count', 'N/A'))}")
                    st.write(f"**Fields of Research**: {', '.join(metadata.get('fields_of_research', ['Unknown']))}")
                
                st.subheader("Investigation Summary")
                st.write(reason)
      
        
        else:
            input_type = st.radio("Select paper input type(DOI is preferred input type):", ("DOI", "Title"))
            paper_input = st.text_input(f"Enter paper {input_type} (e.g., DOI: 10.1128/mmbr.00144-23, Title: Microbiology of human spaceflight)", "")
            if st.button("Check Paper"):
                if not paper_input:
                    st.error(f"Please enter a valid {input_type}.")
                    return
                if input_type == "Title" and not validate_title(paper_input):
                    st.error("Invalid title. Please enter a non-empty title (up to 500 characters).")
                    return
                
                with st.spinner("Analyzing your request..."):
                    try:
                        metadata = get_paper_metadata(paper_input, input_type.lower())
                        if not metadata or not isinstance(metadata, dict):
                            st.error(f"Paper not found in the data source or metadata unavailable. Please verify the {input_type}.")
                            return
                        
                        try:
                            confidence = get_paper_confidence(metadata)
                            if confidence >= 60:
                                st.success(f"This paper is likely legitimate with {confidence}% confidence.")
                            elif confidence > 30:
                                st.warning(f"This paper is questionable with {confidence}% confidence.")
                            else:
                                st.error(f"This paper is likely predatory with {confidence}% confidence.")
                            reason = generate_paper_reason(confidence, metadata)
                        
                        except ValueError:
                            st.error("Invalid data received from the analysis service. Please try again later.")
                            return
                        except Exception:
                            st.error("An unexpected error occurred during analysis. Please try again or contact support.")
                            return
                    
                    except requests.RequestException:
                        st.error("Unable to connect to the data source. Please check your internet connection and try again.")
                        return
                    except Exception:
                        st.error("An unexpected error occurred while retrieving paper data. Please try again or contact support.")
                        return
                
                st.subheader("Investigation Summary")
                st.write(reason)
                
                with st.expander("View Paper Metadata"):
                    st.write(f"**Title**: {str(metadata.get('title', 'Unknown'))}")
                    st.write(f"**Journal ISSN**: {str(metadata.get('journal_issn', 'Unknown'))}")
                    st.write(f"**Publication Year**: {str(metadata.get('publication_year', 'N/A'))}")
                    st.write(f"**Cited By Count (per year)**: {str(round(float(metadata.get('cited_by_count', 0)), 2)) if isinstance(metadata.get('cited_by_count', 0), (int, float)) else 'N/A'}")
                    st.write(f"**Author Count**: {str(metadata.get('author_count', 0))}")
                    st.write(f"**In DOAJ**: {'Yes' if metadata.get('is_in_doaj', False) else 'No'}")
                    st.write(f"**Publisher**: {str(metadata.get('publisher', 'Unknown'))}")
                
    except Exception:
        st.error("An unexpected error occurred in the application. Please refresh the page and try again.")
        return
    
    # Powered by Anthropic Footer
    st.markdown(
        """
        <div style="text-align: center; margin-top: 12px; font-size: 12px; color: #555;">
            Powered by <a href="https://www.anthropic.com/" target="_blank">Anthropic</a><br>
            Developed by <a href="https://www.linkedin.com/in/abhishekbakare/" target="_blank">Abhishek Bakare</a>
        </div>
        """,
        unsafe_allow_html=True
    )

def generate_journal_reason(confidence, metadata):
    """Generate a reason for the journal's legitimacy based on confidence and metadata."""
    citations_count = metadata.get('cited_by_count', 0)
    is_in_doaj = metadata.get('is_in_doaj', False)
    publisher = metadata.get('publisher', 'an unknown publisher')
    works_count = metadata.get('works_count', 0)
    title = metadata.get('title', 'an unknown title')
    fields_of_research = metadata.get('fields_of_research', ['Unknown'])[:3]

    # Handle unknown or missing data gracefully
    avg_citations_message = (
        f"with total {citations_count} citations"
        if citations_count > 0
        else "but citation data is unavailable or not reported"
    )
    fields_message = (
        f"The journal focuses on fields such as {', '.join(fields_of_research)}."
        if fields_of_research and fields_of_research[0] != "Unknown"
        else "The journal's fields of research are not well-defined."
    )
    doaj_message = (
        f"It’s {'listed' if is_in_doaj else 'not listed'} on a trusted journal directory (DOAJ), "
        f"{'which adds to its credibility' if is_in_doaj else 'which raises some questions about its standards'}."
    )
    publisher_message = (
        f"It’s run by {publisher}, which is {'widely known and trusted' if confidence >= 70 else 'not widely known or trusted'}."
    )
    works_message = (
        f"The journal has published {works_count} works in total."
        if works_count > 0
        else "The journal's publication volume is not reported."
    )

    # Generate confidence-based reasoning
    if confidence >= 60:
        confidence_message = f"We’re {confidence}% sure that the journal '{title}' is trustworthy because it has strong signs of quality."
    elif confidence > 30:
        confidence_message = f"We’re only {confidence}% sure about the journal '{title}' because it shows some mixed signs."
    else:
        confidence_message = f"We’re only {confidence}% confident in the journal '{title}' because it has serious red flags."

    # Combine all messages into a single reason
    return (
        f"{confidence_message} {publisher_message} {fields_message} "
        f"The journal’s articles are often read and cited {avg_citations_message}. "
        f"{doaj_message} {works_message}"
    )

def generate_paper_reason(confidence, metadata):
    """Generate a reason for the paper's legitimacy based on confidence and metadata."""
    title = metadata.get('title', 'an unknown title')
    journal_issn = metadata.get('journal_issn', 'Unknown')
    publication_year = metadata.get('publication_year', 'Unknown')
    cited_by_count = metadata.get('cited_by_count', 0)
    author_count = metadata.get('author_count', 0)
    is_in_doaj = metadata.get('is_in_doaj', False)
    publisher = metadata.get('publisher') or 'an unknown publisher'  # Fix for None or missing publisher
    avg_author_publications = metadata.get('avg_author_publications', 0)
    avg_author_cited_by_count = metadata.get('avg_author_cited_by_count', 0)
    avg_author_2yr_citedness = metadata.get('avg_author_2yr_citedness', 0)
    orcid_presence = metadata.get('orcid_presence', 'No')
    top_concepts = metadata.get('top_concepts', 'Unknown')
    publication_trend = metadata.get('publication_trend', 'Unknown')

    # Handle missing or unknown data gracefully
    citation_message = (
        f"The paper has been cited {cited_by_count} times"
        if cited_by_count > 0
        else "but citation data is unavailable or not reported"
    )
    author_message = (
        f"The paper has {author_count} authors, {'most of whom have verified ORCID IDs' if orcid_presence == 'Yes' else 'but author verification is lacking'}."
    )
    publisher_message = (
        f"It’s published by {publisher}, which is {'widely known and trusted' if confidence >= 70 else 'not widely known or trusted'}."
    )
    doaj_message = (
        f"The journal is {'listed' if is_in_doaj else 'not listed'} on a trusted directory (DOAJ), "
        f"{'which adds to its credibility' if is_in_doaj else 'which raises some questions about its standards'}."
    )
    author_stats_message = (
        f"The authors have an average of {avg_author_publications} publications and {avg_author_cited_by_count} citations, "
        f"with a 2-year mean citedness of {avg_author_2yr_citedness}."
        if avg_author_publications > 0 or avg_author_cited_by_count > 0
        else "Author-level metrics are unavailable or not reported."
    )
    concepts_message = (
        f"The paper focuses on concepts such as {top_concepts}."
        if top_concepts != "Unknown"
        else "The paper's key concepts are not well-defined."
    )
    publication_trend_message = (
        f"The authors are affiliated with institutions such as {publication_trend.split(';')[0]}."
        if publication_trend != "Unknown"
        else "The authors' institutional affiliations are not well-documented."
    )
    journal_message = (
        f"The paper was published in a journal with ISSN {journal_issn} in the year {publication_year}."
        if journal_issn != "Unknown" and publication_year != "Unknown"
        else "The journal's ISSN or publication year is not well-documented."
    )

    # Generate confidence-based reasoning
    if confidence >= 60:
        confidence_message = f"We’re {confidence}% sure that the paper '{title}' is trustworthy because it has strong signs of quality."
    elif confidence > 30:
        confidence_message = f"We’re only {confidence}% sure about the paper '{title}' because it shows some mixed signs."
    else:
        confidence_message = f"We’re only {confidence}% confident in the paper '{title}' because it has serious red flags."

    # Combine all messages into a single reason
    return (
        f"{confidence_message} {publisher_message} {journal_message} {citation_message}. "
        f"{author_message} {doaj_message} {author_stats_message} "
        f"{concepts_message} {publication_trend_message}"
    )

if __name__ == "__main__":
    main()
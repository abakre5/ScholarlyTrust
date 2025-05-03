import streamlit as st
from api_utils import is_in_doaj, get_journal_metadata, get_paper_metadata, get_journal_confidence, get_paper_confidence

def main():
    st.title("Journal and Research Paper Legitimacy Checker")
    st.write("Check the legitimacy of a journal (by ISSN) or a research paper (by DOI or title, including author legitimacy) using Claude 3.5 Sonnet.")
    
    check_type = st.radio("Select check type:", ("Journal", "Research Paper"))
    
    if check_type == "Journal":
        issn_input = st.text_input("Enter journal ISSN (e.g., 2313-1799)", "")
        if st.button("Check Journal"):
            if issn_input:
                # Fetch journal metadata
                metadata = get_journal_metadata(issn_input)
                
                if metadata and isinstance(metadata, dict):
                    # Get confidence score from Claude
                    try:
                        confidence = get_journal_confidence(metadata)
                        if confidence >= 50:
                            st.success(f"This journal is likely legitimate with {confidence}% confidence.")
                        else:
                            st.warning(f"This journal is likely predatory with {100 - confidence}% confidence.")
                        st.write("Reason: Claude 3.5 Sonnet AI analysis based on metadata.")
                    except Exception as e:
                        st.error(f"Failed to get confidence score: {e}")
                        st.warning("Unable to assess journal legitimacy due to API error.")
                    
                    # Display metadata explicitly as strings with type checking
                    st.subheader("Journal Metadata")
                    total_works = metadata.get('total_works', 'N/A')
                    avg_citations = metadata.get('avg_citations', 0)
                    is_in_doaj = metadata.get('is_in_doaj', False)
                    st.write(f"**Total Works**: {str(total_works)}")
                    st.write(f"**Average Citations**: {str(round(float(avg_citations), 2)) if isinstance(avg_citations, (int, float)) else 'N/A'}")
                    st.write(f"**In DOAJ**: {'Yes' if is_in_doaj else 'No'}")
                
                else:
                    st.error("Journal not found in OpenAlex or metadata unavailable.")
                
                # Generate report for media
                st.subheader("Investigation Summary")
                st.write("This app uses Claude 3.5 Sonnet AI to analyze journal metadata, helping researchers avoid predatory publishing scams.")
            else:
                st.error("Please enter a valid ISSN.")
    
    else:  # Research Paper
        input_type = st.radio("Select paper input type:", ("DOI", "Title"))
        paper_input = st.text_input(f"Enter paper {input_type} (e.g., DOI: 10.17487/IJST.2023.123456, Title: Blockchain Applications in IoT)", "")
        if st.button("Check Paper"):
            if paper_input:
                # Fetch paper metadata, including author metadata
                metadata = get_paper_metadata(paper_input, input_type.lower())
                
                if metadata and isinstance(metadata, dict):
                    # Get confidence score from Claude, including author metadata
                    try:
                        confidence = get_paper_confidence(metadata)
                        if confidence >= 50:
                            st.success(f"This paper is likely legitimate with {confidence}% confidence.")
                        else:
                            st.warning(f"This paper is likely from a predatory source with {100 - confidence}% confidence.")
                        st.write("Reason: Claude 3.5 Sonnet AI analysis based on paper and author metadata.")
                    except Exception as e:
                        st.error(f"Failed to get confidence score: {e}")
                        st.warning("Unable to assess paper legitimacy due to API error.")
                    
                    # Display paper metadata explicitly as strings with type checking
                    st.subheader("Paper Metadata")
                    title = metadata.get('title', 'Unknown')
                    journal_issn = metadata.get('journal_issn', 'Unknown')
                    publication_year = metadata.get('publication_year', 'N/A')
                    cited_by_count = metadata.get('cited_by_count', 0)
                    author_count = metadata.get('author_count', 0)
                    is_in_doaj = metadata.get('is_in_doaj', False)
                    st.write(f"**Title**: {str(title)}")
                    st.write(f"**Journal ISSN**: {str(journal_issn)}")
                    st.write(f"**Publication Year**: {str(publication_year)}")
                    st.write(f"**Cited By Count**: {str(cited_by_count)}")
                    st.write(f"**Author Count**: {str(author_count)}")
                    st.write(f"**In DOAJ**: {'Yes' if is_in_doaj else 'No'}")
                    
                    # Display author metadata explicitly as strings with type checking
                    st.subheader("Author Metadata (Aggregated)")
                    avg_author_publications = metadata.get('avg_author_publications', 'N/A')
                    avg_author_h_index = metadata.get('avg_author_h_index', 'N/A')
                    avg_author_cited_by_count = metadata.get('avg_author_cited_by_count', 'N/A')
                    avg_author_2yr_citedness = metadata.get('avg_author_2yr_citedness', 0)
                    orcid_presence = metadata.get('orcid_presence', 'No')
                    top_concepts = metadata.get('top_concepts', 'Unknown')
                    publication_trend = metadata.get('publication_trend', 'N/A')
                    st.write(f"**Average Publication Count**: {str(avg_author_publications)}")
                    st.write(f"**Average H-Index**: {str(avg_author_h_index)}")
                    st.write(f"**Average Cited By Count**: {str(avg_author_cited_by_count)}")
                    st.write(f"**Average 2-Year Mean Citedness**: {str(round(float(avg_author_2yr_citedness), 2)) if isinstance(avg_author_2yr_citedness, (int, float)) else 'N/A'}")
                    st.write(f"**ORCID Presence**: {str(orcid_presence)}")
                    st.write(f"**Top Concepts**: {str(top_concepts)}")
                    st.write(f"**Publication Trend (Last 5 Years)**: {str(publication_trend)}")
                    
                    # Generate report for media
                    st.subheader("Investigation Summary")
                    st.write("This app uses Claude 3.5 Sonnet AI to analyze paper and author metadata, helping researchers avoid fraudulent publications.")
                else:
                    st.error("Paper not found in OpenAlex or metadata unavailable.")
            else:
                st.error(f"Please enter a valid {input_type}.")

if __name__ == "__main__":
    main()
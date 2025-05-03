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
                
                if metadata:
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
                    
                    # Display metadata explicitly as strings
                    st.subheader("Journal Metadata")
                    st.write(f"**Total Works**: {str(metadata.get('total_works', 'N/A'))}")
                    st.write(f"**Average Citations**: {str(round(metadata.get('avg_citations', 0), 2))}")
                    st.write(f"**In DOAJ**: {'Yes' if metadata.get('is_in_doaj', False) else 'No'}")
                
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
                # Fetch paper metadata
                metadata = get_paper_metadata(paper_input, input_type.lower())
                
                if metadata:
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
                    
                    # Display paper metadata explicitly as strings
                    st.subheader("Paper Metadata")
                    st.write(f"**Title**: {str(metadata.get('title', 'Unknown'))}")
                    st.write(f"**Journal ISSN**: {str(metadata.get('journal_issn', 'Unknown'))}")
                    st.write(f"**Publication Year**: {str(metadata.get('publication_year', 'N/A'))}")
                    st.write(f"**Cited By Count**: {str(metadata.get('cited_by_count', 0))}")
                    st.write(f"**Author Count**: {str(metadata.get('author_count', 0))}")
                    st.write(f"**In DOAJ**: {'Yes' if metadata.get('is_in_doaj', False) else 'No'}")
                    
                    # Display author metadata explicitly as strings
                    st.subheader("Author Metadata (Aggregated)")
                    st.write(f"**Average Publication Count**: {str(metadata.get('avg_author_publications', 'N/A'))}")
                    st.write(f"**Average H-Index**: {str(metadata.get('avg_author_h_index', 'N/A'))}")
                    st.write(f"**Affiliations**: {str(metadata.get('author_affiliations', 'Unknown'))}")
                    st.write(f"**Average Citations**: {str(round(metadata.get('avg_author_citations', 0), 2))}")
                    
                    # Generate report for media
                    st.subheader("Investigation Summary")
                    st.write("This app uses Claude 3.5 Sonnet AI to analyze paper and author metadata, helping researchers avoid fraudulent publications.")
                else:
                    st.error("Paper not found in OpenAlex or metadata unavailable.")
            else:
                st.error(f"Please enter a valid {input_type}.")

if __name__ == "__main__":
    main()
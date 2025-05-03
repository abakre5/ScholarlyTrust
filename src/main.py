import streamlit as st
import requests
import re

from api_utils import is_in_doaj, get_journal_metadata, get_paper_metadata, get_journal_confidence, get_paper_confidence

def validate_issn(issn):
    """Validate ISSN format (e.g., 1234-5678)."""
    pattern = r'^\d{4}-\d{4}$'
    return bool(re.match(pattern, issn))

def validate_doi(doi):
    """Validate DOI format (e.g., 10.1000/xyz123)."""
    pattern = r'^10\.\d{4,9}/[-._;()/:A-Z0-9]+$'
    return bool(re.match(pattern, doi.strip()))

def validate_title(title):
    """Validate title (non-empty and reasonable length)."""
    return len(title.strip()) > 0 and len(title) <= 500

def main():
    st.title("Journal and Research Paper Legitimacy Checker")
    st.write("Check the legitimacy of a journal (by ISSN) or a research paper (by DOI or title, including author legitimacy).")
    
    try:
        check_type = st.radio("Select check type:", ("Research Paper", "Journal"))
        
        if check_type == "Journal":
            issn_input = st.text_input("Enter journal ISSN (e.g., 1092-2172 for MMBR, 2313-1799 for predatory)", "")
            if st.button("Check Journal"):
                if not issn_input:
                    st.error("Please enter a valid ISSN.")
                    return
                if not validate_issn(issn_input):
                    st.error("Invalid ISSN format. Please use a format like 1234-5678.")
                    return
                
                with st.spinner("Analyzing your request..."):
                    try:
                        metadata = get_journal_metadata(issn_input)
                        if not metadata or not isinstance(metadata, dict):
                            st.error("Journal not found in the data source or metadata unavailable. Please verify the ISSN.")
                            return
                        
                        try:
                            confidence = get_journal_confidence(metadata)
                            if confidence >= 60:
                                st.success(f"This journal is likely legitimate with {confidence}% confidence.")
                                reason = (
                                    f"We’re {confidence}% sure this journal is trustworthy because it has strong signs of quality. "
                                    f"It’s run by {metadata.get('publisher', 'an unknown publisher')}, "
                                    f"which is {'a well-known and trusted name' if metadata.get('publisher') in ['American Society for Microbiology', 'Nature', 'Elsevier', 'Springer', 'Wiley'] else 'not widely known'}. "
                                    f"The journal’s articles are {'often read and cited' if metadata.get('avg_citations', 0) > 5 else 'not widely read'}, "
                                    f"with an average of {round(float(metadata.get('avg_citations', 0)), 2)} citations per article. "
                                    f"It’s {'listed' if metadata.get('is_in_doaj', False) else 'not listed'} on a trusted journal directory (DOAJ), "
                                    f"which {'adds to its credibility' if metadata.get('is_in_doaj', False) else 'raises some questions about its standards'}."
                                )
                            elif confidence > 30 and confidence < 60:
                                st.warning(f"This journal is questionable with {confidence}% confidence.")
                                reason = (
                                    f"We’re only {confidence}% sure about this journal because it shows some mixed signs. "
                                    f"The publisher, {metadata.get('publisher', 'unknown')}, "
                                    f"{'is somewhat trusted' if metadata.get('publisher') in ['American Society for Microbiology', 'Nature', 'Elsevier', 'Springer', 'Wiley'] else 'isn’t well-known'}, "
                                    f"which makes us cautious. The journal’s articles get {round(float(metadata.get('avg_citations', 0)), 2)} citations on average, "
                                    f"showing {'some' if metadata.get('avg_citations', 0) > 2 else 'very little'} attention from researchers. "
                                    f"It’s {'listed' if metadata.get('is_in_doaj', False) else 'not listed'} on a trusted journal directory (DOAJ), "
                                    f"{'which is good' if metadata.get('is_in_doaj', False) else 'which raises concerns'}. "
                                    "You should check the journal’s reputation further before trusting it."
                                )
                            else:
                                st.error(f"This journal is likely predatory with {confidence}% confidence.")
                                reason = (
                                    f"We’re only {confidence}% confident in this journal because it has serious red flags. "
                                    f"The publisher, {metadata.get('publisher', 'unknown')}, "
                                    f"{'is not trusted' if metadata.get('publisher') not in ['American Society for Microbiology', 'Nature', 'Elsevier', 'Springer', 'Wiley'] else 'raises concerns'}, "
                                    f"which suggests it might not be reliable. The journal’s articles get {round(float(metadata.get('avg_citations', 0)), 2)} citations on average, "
                                    f"meaning they’re {'rarely read' if metadata.get('avg_citations', 0) < 2 else 'not widely read'} by researchers. "
                                    f"It’s {'not listed' if not metadata.get('is_in_doaj', False) else 'listed'} on a trusted journal directory (DOAJ), "
                                    f"{'which makes it very questionable' if not metadata.get('is_in_doaj', False) else 'but this alone doesn’t make it trustworthy'}."
                                )
                        
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
                    st.write(f"**Total Works**: {str(metadata.get('total_works', 'N/A'))}")
                    st.write(f"**Average Citations**: {str(round(float(metadata.get('avg_citations', 0)), 2)) if isinstance(metadata.get('avg_citations', 0), (int, float)) else 'N/A'}")
                    st.write(f"**In DOAJ**: {'Yes' if metadata.get('is_in_doaj', False) else 'No'}")
                    st.write(f"**Publisher**: {str(metadata.get('publisher', 'Unknown'))}")
                
                st.subheader("Investigation Summary")
                st.write(reason)
        
        else:
            input_type = st.radio("Select paper input type:", ("Title", "DOI"))
            paper_input = st.text_input(f"Enter paper {input_type} (e.g., DOI: 10.1128/mmbr.00144-23, Title: Microbiology of human spaceflight)", "")
            if st.button("Check Paper"):
                if not paper_input:
                    st.error(f"Please enter a valid {input_type}.")
                    return
                if input_type == "DOI" and not validate_doi(paper_input):
                    st.error("Invalid DOI format. Please use a format like 10.1000/xyz123.")
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
                                reason = (
                                    f"We’re {confidence}% sure this paper is trustworthy because it has strong signs of quality. "
                                    f"It’s published by {metadata.get('publisher', 'an unknown publisher')}, "
                                    f"which is {'a well-known and trusted name' if metadata.get('publisher') in ['American Society for Microbiology', 'Nature', 'Elsevier', 'Springer', 'Wiley'] else 'not widely known'}. "
                                    f"The authors {'are verified with IDs' if metadata.get('orcid_presence', 'No') == 'Yes' else 'lack verification IDs'}, "
                                    f"{'making them more credible' if metadata.get('orcid_presence', 'No') == 'Yes' else 'which raises some questions'}. "
                                    f"The journal is {'on a trusted list (DOAJ)' if metadata.get('is_in_doaj', False) else 'not on a trusted list (DOAJ)'}, "
                                    f"{'adding to its reliability' if metadata.get('is_in_doaj', False) else 'making it less certain'}. "
                                    f"The paper is {'often read' if metadata.get('cited_by_count', 0) > 5 else 'not widely read'} by researchers, "
                                    f"with {round(float(metadata.get('cited_by_count', 0)), 2)} citations per year, and the authors have {'a steady record' if 'works' in metadata.get('publication_trend', '') else 'an unclear record'} of publishing."
                                )
                            elif confidence > 30 and confidence < 60:
                                st.warning(f"This paper is questionable with {confidence}% confidence.")
                                reason = (
                                    f"We’re only {confidence}% sure about this paper because it shows some mixed signs. "
                                    f"The publisher, {metadata.get('publisher', 'unknown')}, "
                                    f"{'is somewhat trusted' if metadata.get('publisher') in ['American Society for Microbiology', 'Nature', 'Elsevier', 'Springer', 'Wiley'] else 'isn’t well-known'}, "
                                    f"which makes us cautious. The authors {'are verified with IDs' if metadata.get('orcid_presence', 'No') == 'Yes' else 'lack verification IDs'}, "
                                    f"{'which is good' if metadata.get('orcid_presence', 'No') == 'Yes' else 'which raises concerns'}. "
                                    f"The journal is {'on a trusted list (DOAJ)' if metadata.get('is_in_doaj', False) else 'not on a trusted list (DOAJ)'}, "
                                    f"{'which is positive' if metadata.get('is_in_doaj', False) else 'which makes it less reliable'}. "
                                    f"The paper gets {round(float(metadata.get('cited_by_count', 0)), 2)} citations per year, "
                                    f"showing {'some' if metadata.get('cited_by_count', 0) > 2 else 'very little'} attention from researchers, "
                                    f"and the authors have {'a steady' if 'works' in metadata.get('publication_trend', '') else 'an unclear'} publishing record. "
                                    "You should check the paper’s source further before trusting it."
                                )
                            else:
                                st.error(f"This paper is likely predatory with {confidence}% confidence.")
                                reason = (
                                    f"We’re only {confidence}% confident in this paper because it has serious red flags. "
                                    f"The publisher, {metadata.get('publisher', 'unknown')}, "
                                    f"{'is not trusted' if metadata.get('publisher') not in ['American Society for Microbiology', 'Nature', 'Elsevier', 'Springer', 'Wiley'] else 'raises concerns'}, "
                                    f"which suggests it might not be reliable. The authors {'lack verification IDs' if metadata.get('orcid_presence', 'No') == 'No' else 'are verified with IDs'}, "
                                    f"{'making it very questionable' if metadata.get('orcid_presence', 'No') == 'No' else 'but this alone isn’t enough'}. "
                                    f"The journal is {'not on a trusted list (DOAJ)' if not metadata.get('is_in_doaj', False) else 'on a trusted list (DOAJ)'}, "
                                    f"{'which raises major concerns' if not metadata.get('is_in_doaj', False) else 'but this doesn’t make it trustworthy'}. "
                                    f"The paper gets {round(float(metadata.get('cited_by_count', 0)), 2)} citations per year, "
                                    f"meaning it’s {'rarely read' if metadata.get('cited_by_count', 0) < 2 else 'not widely read'} by researchers, "
                                    f"and the authors have {'an unclear' if 'N/A' in metadata.get('publication_trend', '') else 'a limited'} publishing record."
                                )
                        
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
                
                with st.expander("View Author Metadata (Aggregated)"):
                    st.write(f"**Average Publication Count (normalized)**: {str(metadata.get('avg_author_publications', 'N/A'))}")
                    st.write(f"**Average Cited By Count (normalized)**: {str(metadata.get('avg_author_cited_by_count', 'N/A'))}")
                    st.write(f"**Average 2-Year Mean Citedness**: {str(round(float(metadata.get('avg_author_2yr_citedness', 0)), 2)) if isinstance(metadata.get('avg_author_2yr_citedness', 0), (int, float)) else 'N/A'}")
                    st.write(f"**ORCID Presence**: {str(metadata.get('orcid_presence', 'No'))}")
                    st.write(f"**Top Concepts**: {str(metadata.get('top_concepts', 'Unknown'))}")
                    st.write(f"**Publication Trend (Last 5 Years)**: {str(metadata.get('publication_trend', 'N/A'))}")
                    st.write(f"**External Recognition (Citations/Co-authorship)**: {str(metadata.get('external_recognition', 'None'))}")
    
    except Exception:
        st.error("An unexpected error occurred in the application. Please refresh the page and try again.")
        return
    
    # Powered by Anthropic Footer
    st.markdown(
        """
        <div style="text-align: center; margin-top: 20px; font-size: 12px; color: #555;">
            Powered by <a href="https://www.anthropic.com/" target="_blank">Anthropic</a>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
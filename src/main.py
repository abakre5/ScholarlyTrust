import streamlit as st
from data_loader import load_predatory_journals
from api_utils import is_in_doaj, get_journal_metadata, get_claude_confidence

# Streamlit app
def main():
    st.title("Predatory Journal Checker")
    st.write("Enter a journal's ISSN to check if it's predatory using Claude AI.")
    
    issn_input = st.text_input("Enter journal ISSN (e.g., 1234-5678)", "")
    
    if st.button("Check"):
        if issn_input:
            # Load predatory journals
            predatory_journals = load_predatory_journals()
            if predatory_journals.empty:
                st.error("Cannot proceed without predatory journals list.")
                return
            
            # Check if ISSN is in predatory list
            is_predatory = issn_input in predatory_journals['ISSN'].values
            
            # Fetch metadata
            metadata = get_journal_metadata(issn_input)
            
            if metadata:
                # Get confidence score from Claude
                confidence = get_claude_confidence(metadata, is_predatory)
                
                # Display results
                if is_predatory or not metadata['is_in_doaj'] or confidence > 50:
                    st.warning(f"This journal is likely predatory with {confidence}% confidence.")
                    if is_predatory:
                        st.write("Reason: Found in predatory journals list.")
                    if not metadata['is_in_doaj']:
                        st.write("Reason: Not indexed in DOAJ.")
                    if confidence > 50:
                        st.write(f"Reason: Claude AI analysis suggests predatory behavior based on metadata.")
                else:
                    st.success(f"This journal is likely legitimate with {100 - confidence}% confidence.")
                    st.write("Reason: Not found in predatory journals list and indexed in DOAJ.")
                
                # Display metadata
                st.subheader("Journal Metadata")
                st.write(f"Total Works: {metadata['total_works']}")
                st.write(f"Average Citations: {metadata['avg_citations']:.2f}")
                st.write(f"In DOAJ: {'Yes' if metadata['is_in_doaj'] else 'No'}")
                
                # Generate report for media
                st.subheader("Investigation Summary")
                total_journals = len(predatory_journals)
                st.write(f"Database contains {total_journals} known predatory journals.")
                st.write("This app uses Claude AI to analyze journal metadata, helping researchers avoid scams.")
            else:
                st.error("Journal not found in OpenAlex or metadata unavailable.")
        else:
            st.error("Please enter a valid ISSN.")

if __name__ == "__main__":
    main()
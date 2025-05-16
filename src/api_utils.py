import traceback
import requests
import streamlit as st
from anthropic import Anthropic
import numpy as np
import os
import re
from config import ANTHROPIC_MODEL

# Define constants
HIJACKED_ISSN = "HIJACKED_ISSN"
ERROR_STATE = "ERROR_STATE"
NOT_FOUND = "Not Found"

# Initialize Anthropic client
try:
    anthropic = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
except KeyError:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        anthropic = Anthropic(api_key=api_key)
    else:
        print("Anthropic API key not found. Please set it in secrets.toml or as an environment variable.")
        st.stop()

def is_in_doaj(journal_issn):
    if not journal_issn:
        return False
    url = f"https://api.openalex.org/sources?filter=ids.value:{journal_issn},ids.schema:ISSN"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data['meta']['count'] > 0:
                return data['results'][0].get('is_in_doaj', False)
        return False
    except Exception as e:
        print(f"Failed to query OpenAlex API for journal: {e}")
        return ERROR_STATE

def get_journal_authors(source_id, max_works=100):
    """
    Fetches authors from the most recent works in a journal using OpenAlex.
    Returns a list of author dicts with name, orcid, and affiliation.
    """
    import requests

    # Accept both full OpenAlex URLs and just the source ID
    if source_id.startswith("https://openalex.org/"):
        source_id = source_id.split("/")[-1]

    url = f"https://api.openalex.org/works?filter=primary_location.source.id:{source_id}&per-page={max_works}"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to fetch works for journal {source_id}: {response.status_code}")
            return []
        works = response.json().get('results', [])
        authors = []
        for work in works:
            for author in work.get('authorships', []):
                author_data = author.get('author', {})
                name = author_data.get('display_name', NOT_FOUND)
                orcid = author_data.get('orcid', NOT_FOUND)
                institutions = author.get('institutions', [])
                affiliation = institutions[0]['display_name'] if institutions and len(institutions[0]) else NOT_FOUND
                authors.append({
                    "name": name,
                    "orcid": orcid,
                    "affiliation": affiliation
                })
        return authors
    except Exception as e:
        print(f"Error fetching journal authors: {e}")
        return []

def get_journal_metadata(id, is_issn=True):
    # Check if the ISSN is in the hijacked list
    hijacked_issns_file = "/workspaces/ScholarlyTrust/docs/hijacked_issn.txt"
    hijacked_journal_names_file = "/workspaces/ScholarlyTrust/docs/hijacked_journal_title.txt"
    try:
        if is_issn:
            with open(hijacked_issns_file, 'r') as file:
                hijacked_issns = {line.strip() for line in file if line.strip()}
            if id in hijacked_issns:
                return HIJACKED_ISSN
        else:
            with open(hijacked_journal_names_file, 'r') as file:
                hijacked_journals = {line.strip().lower() for line in file if line.strip()}
            if id.lower() in hijacked_journals:
                return HIJACKED_ISSN
    except Exception as e:
        print(f"Error reading hijacked ISSNs file: {e}")
        # return ERROR_STATE
    
    if is_issn:
        url = f"https://api.openalex.org/sources?filter=issn:{id}"
    else:
        url = f'https://api.openalex.org/sources?search="{id}"'
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data['meta']['count'] > 0:
                source = data['results'][0]
                # Extract fields
                title = source.get('display_name', NOT_FOUND)
                if not is_issn and not title.upper() == id.upper():
                    return None
                publisher = source.get('display_name', NOT_FOUND)
                homepage_url = source.get('homepage_url', 'N/A')
                is_in_doaj = source.get('is_in_doaj', False)
                is_open_access = source.get('is_oa', False)
                country_code = source.get('country_code', NOT_FOUND)
                works_count = source.get('works_count', 0)
                cited_by_count = source.get('cited_by_count', 0)
                fields_of_research = [
                    topic.get('display_name', 'Unknown')
                    for topic in source.get('topics', [])
                ]
                # v2
                source_id = source.get('id', NOT_FOUND)
                authors_who_pulished_in_this_journal_info = NOT_FOUND
                if source_id != NOT_FOUND:
                    authors_who_pulished_in_this_journal_info = get_journal_authors(source_id)
                is_indexed_in_scopus = source.get('is_indexed_in_scopus', False)
                summary_stats = source.get('summary_stats', {})
                h_index = summary_stats.get('h_index', NOT_FOUND)
                i10_index = summary_stats.get('i10_index', NOT_FOUND)
                two_yr_mean_citedness = summary_stats.get('2yr_mean_citedness', NOT_FOUND)
                host_organization_name = source.get('host_organization_name', NOT_FOUND)
                apc_prices = source.get('apc_prices', NOT_FOUND)


                return {
                    "title": title,
                    "publisher": publisher,
                    "homepage_url": homepage_url,
                    "is_in_doaj": is_in_doaj,
                    "is_open_access": is_open_access,
                    "authors_who_pulished_in_this_journal_info": authors_who_pulished_in_this_journal_info,
                    "country_code": country_code,
                    "works_count": works_count,
                    "cited_by_count": cited_by_count,
                    "fields_of_research": fields_of_research,
                    "is_indexed_in_scopus": is_indexed_in_scopus,
                    "h_index": h_index,
                    "i10_index": i10_index,
                    "two_yr_mean_citedness": two_yr_mean_citedness,
                    "host_organization_name": host_organization_name,
                    "apc_prices": apc_prices
                }
        return None
    except Exception as e:
        print(f"Failed to fetch journal metadata: {e}")
        traceback.print_exc()
        return ERROR_STATE

def get_author_metadata_for_paper(paper_data):
    """
    Returns a list of dicts, one per author, with:
      - name (display_name)
      - has_orcid (True/False)
      - affiliation (display_name of the first institution)
    """
    try:
        authors = paper_data.get('authorships', [])
        if authors is None or len(authors) == 0:
            return NOT_FOUND

        author_info = []
        for author in authors:
            author_data = author.get('author', {})
            name = author_data.get('display_name', NOT_FOUND)
            has_orcid = author_data.get('orcid') != None and author_data.get('orcid') != "null"
            institutions = author.get('institutions', [])
            if institutions is None or len(institutions) == 0:
                affiliation = NOT_FOUND
            else:
                affiliation = institutions[0].get('display_name', NOT_FOUND)
            author_info.append({
                'name': name,
                'has_orcid': has_orcid,
                'affiliation': affiliation
            })
        return author_info
    except Exception as e:
        print(f"Failed to fetch author metadata: {e}")
        return ERROR_STATE

def get_paper_metadata_v2(paper_input, input_type):
    if input_type == 'doi':
        url = f"https://api.openalex.org/works?filter=doi:{paper_input}"
    else:
        url = f"https://api.openalex.org/works?filter=title.search:{paper_input.replace(' ', '%20')}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            response_data = response.json()
            response_data = response_data.get('results', [])
            if response_data is None or len(response_data) == 0:
                # No results found
                return NOT_FOUND
            
            # 0th element is the most relevant
            paper = response_data[0]

            # Only focus on locations if locations_count >= 1
            locations_count = paper.get('locations_count', 0)
            locations = paper.get('locations', [])
            if locations_count == 0:
                # No locations found
                return NOT_FOUND
            location_data = None
            for loc in locations:
                if loc.get('source'):
                    location_data = loc
                    break
            if location_data is None:
                # No valid location with 'source' found
                return NOT_FOUND

            # Extract relevant metadata from location_data
            publication_year = paper.get('publication_year', NOT_FOUND)
            cited_by_count = paper.get('cited_by_count', NOT_FOUND)
            from datetime import datetime
            current_year = datetime.now().year
            years_since_publication = (
                max(1, current_year - publication_year) if isinstance(publication_year, int) else NOT_FOUND
            )
            total_paper_citation_count = cited_by_count

            # Author metadata
            author_metadata = get_author_metadata_for_paper(paper)

            # Extract from location_data or mark as NOT_FOUND
            is_in_doaj = location_data.get('source', {}).get('is_in_doaj', NOT_FOUND)
            publisher = location_data.get('source', {}).get('display_name', NOT_FOUND)

            # Other relevant metadata
            title = paper.get('title', NOT_FOUND)
            author_count = len(author_metadata) if isinstance(author_metadata, list) else NOT_FOUND
            open_access = location_data.get('is_oa', NOT_FOUND)
            concepts = paper.get('concepts', NOT_FOUND)
            language = paper.get('language', NOT_FOUND)
            doi = paper.get('doi', NOT_FOUND)

            return {
                'title': title,
                'publication_year': publication_year,
                'cited_by_count': cited_by_count,
                'years_since_publication': years_since_publication,
                'total_paper_citation_count': total_paper_citation_count,
                'author_metadata': author_metadata,
                'author_count': author_count,
                'is_in_doaj': is_in_doaj,
                'publisher': publisher,
                'open_access': open_access,
                'concepts': concepts,
                'language': language,
                'doi': doi,
                'locations_count': locations_count,
                'locations': locations
            }
        return NOT_FOUND
    except Exception as e:
        print(f"Failed to fetch paper metadata: {e}")
        traceback.print_exc()
        return ERROR_STATE

def get_journal_confidence(metadata):
    authors_info = metadata.get('authors_who_pulished_in_this_journal_info', [])
    total_authors = len(authors_info)
    orcid_count = sum(1 for a in authors_info if a.get('orcid') not in [None, NOT_FOUND, ""])
    reputable_affiliations = [
        "Harvard", "MIT", "Stanford", "Oxford", "Cambridge", "Yale", "Caltech", "Princeton", "Columbia", "Berkeley"
    ]
    reputable_affil_count = sum(
        1 for a in authors_info if any(
            uni.lower() in (a.get('affiliation') or '').lower() for uni in reputable_affiliations
        )
    )
    orcid_ratio = f"{orcid_count}/{total_authors}" if total_authors else "0/0"
    reputable_affil_ratio = f"{reputable_affil_count}/{total_authors}" if total_authors else "0/0"

    prompt = f"""
You are an expert in academic publishing. Evaluate the legitimacy of the following journal and provide a confidence score (0-100), where a higher score indicates greater legitimacy.

Check if the publisher name '{metadata['publisher']}' is reputable. This carries biggest deciding factor.

**Use the following metadata to make your decision:**
- In DOAJ: {metadata['is_in_doaj']}
- Indexed in Scopus: {metadata['is_indexed_in_scopus']}
- Host Organization Name: {metadata['host_organization_name']}
- H-Index: {metadata['h_index']}
- 2-Year Mean Citedness: {metadata['two_yr_mean_citedness']}
- I10 Index: {metadata['i10_index']}
- Cited By Count: {metadata['cited_by_count']}
- Total Works: {metadata['works_count']}
- Is Open Access: {metadata['is_open_access']}
- Homepage URL: {metadata['homepage_url']}
- APC Prices: {metadata['apc_prices']}
- Title: {metadata['title']}
- Publisher: {metadata['publisher']}
- Country Code: {metadata['country_code']}
- Fields of Research: {', '.join(metadata['fields_of_research'])}
- Authors with ORCID: {orcid_ratio}
- Authors with reputable affiliations: {reputable_affil_ratio}

**Respond with only a single integer between 0 and 100, with no additional text or explanation.**
"""
    try:
        response = anthropic.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=10,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        text = response.content[0].text.strip()
        match = re.search(r'\d+', text)
        if match:
            raw_score = int(match.group())
            normalized_score = int(100 / (1 + np.exp(-0.1 * (raw_score - 50))))
            return normalized_score
    except Exception as e:
        print(f"Failed to get journal confidence: {e}")
        return ERROR_STATE

def get_paper_confidence(metadata):
    """
    Given paper metadata, generate a confidence score (0-100) for legitimacy.
    Uses: DOAJ status, publisher, author ORCID, author affiliations, open access, concepts, citation count, etc.
    """
    # Prepare author-level summaries
    author_orcid_count = sum(1 for a in metadata.get('author_metadata', []) if a.get('has_orcid'))
    author_affiliations = [a.get('affiliation') for a in metadata.get('author_metadata', [])]
    has_affiliation = any(aff and aff != NOT_FOUND for aff in author_affiliations)
    author_count = metadata.get('author_count', 0)
    orcid_presence = "Yes" if author_orcid_count > 0 else "No"

    # Prepare concept summary
    concepts = metadata.get('concepts', [])
    if isinstance(concepts, list) and concepts:
        top_concepts = ", ".join([c.get('display_name', '') for c in concepts if c.get('score', 0) > 0.3])
    else:
        top_concepts = "Unknown"

    # Compose prompt for LLM
    prompt = (
        f"You are an expert in academic publishing. Provide a confidence score (0-100) indicating the likelihood that the paper is legitimate (higher score = more legitimate). "
        f"Assign weights: DOAJ indexing (40%, journals listed in DOAJ are highly credible), ORCID presence among authors (20%), publisher reputation (15%, high for American Society for Microbiology, Nature, Elsevier, Springer, Wiley), "
        f"external recognition (10%, citations/co-authorship in reputable venues as proxy for media coverage), author affiliations (5%), concept alignment (5%), open access status (5%). "
        f"Recognize predatory papers (e.g., ISSN 2313-1799) by non-DOAJ journals, no ORCID, no reputable affiliations, or misaligned concepts. "
        f"A paper is legitimate if published by reputable publishers, authors have ORCID, or the journal is in DOAJ. "
        f"Ensure top concepts align with paper title: {metadata.get('title', 'Unknown')}. "
        f"Metadata: Title: {metadata.get('title', 'Unknown')}, "
        f"Publication Year: {metadata.get('publication_year', 'Unknown')}, "
        f"Cited By Count: {metadata.get('cited_by_count', 'Unknown')}, "
        f"Years Since Publication: {metadata.get('years_since_publication', 'Unknown')}, "
        f"Author Count: {author_count}, "
        f"In DOAJ: {metadata.get('is_in_doaj', 'Unknown')}, "
        f"Publisher: {metadata.get('publisher', 'Unknown')}, "
        f"Open Access: {metadata.get('open_access', 'Unknown')}, "
        f"ORCID Presence: {orcid_presence}, "
        f"Author Affiliations Present: {'Yes' if has_affiliation else 'No'}, "
        f"Top Concepts: {top_concepts}, "
        f"Language: {metadata.get('language', 'Unknown')}, "
        f"DOI: {metadata.get('doi', 'Unknown')}. "
        f"**Respond with only a single integer between 0 and 100, with no additional text or explanation.**"
    )
    try:
        response = anthropic.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=10,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        text = response.content[0].text.strip()
        match = re.search(r'\d+', text)
        if match:
            raw_score = int(match.group())
            normalized_score = int(100 / (1 + np.exp(-0.1 * (raw_score - 50))))
            return normalized_score
        raise ValueError("No integer found in Claude response")
    except Exception as e:
        return ERROR_STATE
    
def view_paper_metadata(metadata, st):
    """Display paper metadata in a Streamlit expander."""
    with st.expander("View Paper Metadata"):
        st.write(f"**Title**: {str(metadata.get('title', 'Unknown'))}")
        # Journal name from first location's source.display_name if available
        journal_name = "Unknown"
        locations = metadata.get('locations', [])
        if locations and isinstance(locations, list):
            source = locations[0].get('source', {}) if locations[0].get('source') else {}
            journal_name = source.get('display_name', 'Unknown')
        st.write(f"**Journal Name**: {journal_name}")
        st.write(f"**Publication Year**: {str(metadata.get('publication_year', 'N/A'))}")
        st.write(f"**Cited By Count**: {str(metadata.get('cited_by_count', 'N/A'))}")
        st.write(f"**Years Since Publication**: {str(metadata.get('years_since_publication', 'N/A'))}")
        st.write(f"**Total Paper Citation Count**: {str(metadata.get('total_paper_citation_count', 'N/A'))}")
        st.write(f"**Author Count**: {str(metadata.get('author_count', 'N/A'))}")
        st.write(f"**In DOAJ**: {'Yes' if metadata.get('is_in_doaj', False) else 'No'}")
        st.write(f"**Publisher**: {str(metadata.get('publisher', 'Unknown'))}")
        st.write(f"**Open Access**: {'Yes' if metadata.get('open_access', False) else 'No'}")
        st.write(f"**Language**: {str(metadata.get('language', 'Unknown'))}")
        st.write(f"**DOI**: {str(metadata.get('doi', 'Unknown'))}")
        st.write(f"**Total Locations**: {str(metadata.get('locations_count', 'N/A'))}")

        # Show concepts if available
        concepts = metadata.get('concepts', [])
        if isinstance(concepts, list) and concepts:
            st.write("**Key Concepts:**")
            for c in concepts:
                st.write(f"- {c.get('display_name', 'Unknown')} (score: {round(c.get('score', 0), 2)})")

        # Show author details
        author_metadata = metadata.get('author_metadata', [])
        if isinstance(author_metadata, list) and author_metadata:
            st.write("**Authors:**")
            for a in author_metadata:
                st.write(
                    f"- {a.get('name', 'Unknown')} | ORCID: {'Yes' if a.get('has_orcid', False) else 'No'} | Affiliation: {a.get('affiliation', 'Unknown')}"
                )


def generate_paper_reason(confidence, metadata):
    """Generate a reason for the paper's legitimacy based on confidence and metadata."""
    title = metadata.get('title', 'an unknown title')
    publication_year = metadata.get('publication_year', 'Unknown')
    cited_by_count = metadata.get('cited_by_count', 0)
    years_since_publication = metadata.get('years_since_publication', 'Unknown')
    total_paper_citation_count = metadata.get('total_paper_citation_count', 0)
    author_metadata = metadata.get('author_metadata', [])
    author_count = metadata.get('author_count', 0)
    is_in_doaj = metadata.get('is_in_doaj', False)
    publisher = metadata.get('publisher') or 'an unknown publisher'
    open_access = metadata.get('open_access', 'Unknown')
    concepts = metadata.get('concepts', [])
    language = metadata.get('language', 'Unknown')
    doi = metadata.get('doi', 'Unknown')
    locations_count = metadata.get('locations_count', 0)
    locations = metadata.get('locations', [])

    # Author details
    orcid_count = sum(1 for a in author_metadata if a.get('has_orcid'))
    has_affiliation = any(a.get('affiliation') and a.get('affiliation') != 'NOT_FOUND' for a in author_metadata)
    author_names = [a.get('name', 'Unknown') for a in author_metadata]
    author_affiliations = [
        a.get('affiliation', 'Unknown') if a.get('affiliation') else "Unknown"
        for a in author_metadata
    ]

    # Concepts summary
    if isinstance(concepts, list) and concepts:
        top_concepts = ", ".join([c.get('display_name', '') for c in concepts if c.get('score', 0) > 0.3])
    else:
        top_concepts = "Unknown"

    # Location summary
    location_summary = ""
    if locations_count > 0 and locations:
        source = locations[0].get('source', {}) if locations[0].get('source') else {}
        journal_name = source.get('display_name', 'Unknown')
        location_summary = f"Published in '{journal_name}'."
    else:
        location_summary = "Journal or publication venue is not well-documented."

    # Compose reason
    citation_message = (
        f"The paper has been cited {cited_by_count} times"
        if cited_by_count and cited_by_count > 0
        else "Citation data is unavailable or not reported"
    )
    author_message = (
        f"Authored by {author_count} researcher(s): {', '.join(author_names)}. "
        f"{orcid_count} {'has' if orcid_count == 1 else 'have'} ORCID(s)."
    )
    affiliation_message = (
        f"Affiliations include: {', '.join(author_affiliations)}."
        if has_affiliation else "Author affiliations are not well-documented."
    )
    doaj_message = (
        f"The journal is {'listed' if is_in_doaj else 'not listed'} in DOAJ, "
        f"{'which adds to its credibility.' if is_in_doaj else 'which raises some questions about its standards.'}"
    )
    oa_message = (
        f"The paper is {'open access' if open_access else 'not open access'}."
        if open_access != 'Unknown' else "Open access status is unknown."
    )
    concepts_message = (
        f"Key concepts: {top_concepts}."
        if top_concepts != "Unknown" else "The paper's key concepts are not well-defined."
    )
    language_message = f"Language: {language}."
    doi_message = f"DOI: {doi}."

    # Confidence-based summary
    if confidence >= 60:
        confidence_message = f"We’re {confidence}% sure that the paper '{title}' is trustworthy because it has strong signs of quality."
    elif confidence > 30:
        confidence_message = f"We’re only {confidence}% sure about the paper '{title}' because it shows some mixed signs."
    else:
        confidence_message = f"We’re only {confidence}% confident in the paper '{title}' because it has serious red flags."

    return (
        f"{confidence_message} {location_summary} {citation_message}. "
        f"{author_message} {affiliation_message} {doaj_message} {oa_message} "
        f"{concepts_message} {language_message} {doi_message}"
    )


def view_journal_metadata(metadata, st):
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

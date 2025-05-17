"""
api_utils.py

Author: Abhishek Bakare (https://www.linkedin.com/in/abhishekbakare/)
Contact: abakre5@gmail.com

This module provides utility functions for:
- Fetching and processing metadata for journals and research papers from OpenAlex and related sources.
- Detecting hijacked journals.
- Constructing prompts for credibility assessment.
- Interfacing with the Anthropic API for confidence scoring and rationale generation.
- Parsing and formatting results for display in the ScholarlyTrust Streamlit app.
"""
import re
import traceback
import requests
import streamlit as st
from anthropic import Anthropic
import numpy as np
import os
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
                if orcid == "null" or orcid == None:
                    orcid = NOT_FOUND
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
    """
    Fetches journal metadata from OpenAlex, including retraction statistics and author info.
    """
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
        return ERROR_STATE

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
                source_id = source.get('id', NOT_FOUND)
                authors_who_pulished_in_this_journal_info = NOT_FOUND
                retracted_papers_count = 0
                retraction_rate = 0.0
                if source_id != NOT_FOUND:
                    authors_who_pulished_in_this_journal_info = get_journal_authors(source_id)
                    # Get retraction stats for this journal
                    works_url = f"https://api.openalex.org/works?filter=primary_location.source.id:{source_id}&per-page=200"
                    works_resp = requests.get(works_url)
                    if works_resp.status_code == 200:
                        works = works_resp.json().get('results', [])
                        total_works = len(works)
                        retracted_papers_count = sum(1 for w in works if w.get('is_retracted', False))
                        retraction_rate = (retracted_papers_count / total_works) if total_works > 0 else 0.0
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
                    "apc_prices": apc_prices,
                    "retracted_papers_count": retracted_papers_count,
                    "retraction_rate": retraction_rate
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
            is_retracted = paper.get('is_retracted', False)

            # Get journal/source id for further metadata
            journal_source_id = location_data.get('source', {}).get('id', None)
            journal_issn = location_data.get('source', {}).get('issn_l', None)
            journal_metadata = None
            if journal_source_id:
                # Prefer ISSN if available for exact match
                if journal_issn:
                    journal_metadata = get_journal_metadata(journal_issn, is_issn=True)
                else:
                    journal_metadata = get_journal_metadata(journal_source_id, is_issn=False)

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
                'locations': locations,
                'is_retracted': is_retracted,
                'journal_metadata': journal_metadata
            }
        return NOT_FOUND
    except Exception as e:
        print(f"Failed to fetch paper metadata: {e}")
        traceback.print_exc()
        return ERROR_STATE

def paper_credibility_prompt(metadata):
    """
    Compose a prompt for an LLM to assess scientific paper credibility using all available metadata.
    """
    # Prepare author and affiliation summaries
    author_metadata = metadata.get('author_metadata', [])
    author_count = len(author_metadata)
    author_names = [a.get('name', 'Unknown') for a in author_metadata]
    orcid_count = sum(1 for a in author_metadata if a.get('has_orcid'))
    author_affiliations = [a.get('affiliation', 'Unknown') for a in author_metadata]
    retraction_rates = [a.get('retraction_rate', None) for a in author_metadata if a.get('retraction_rate') is not None]

    # Journal metadata
    journal = metadata.get('journal_metadata', {}) or {}
    publisher = journal.get('publisher', 'Unknown')
    is_in_doaj = journal.get('is_in_doaj', False)
    is_indexed_in_scopus = journal.get('is_indexed_in_scopus', False)
    h_index = journal.get('h_index', 'Unknown')
    retraction_rate = journal.get('retraction_rate', 0.0)
    retracted_papers_count = journal.get('retracted_papers_count', 0)
    journal_title = journal.get('title', 'Unknown')

    # Paper-level
    cited_by_count = metadata.get('cited_by_count', 0)
    publication_year = metadata.get('publication_year', 'Unknown')
    open_access = metadata.get('open_access', False)
    doi = metadata.get('doi', 'Unknown')
    is_retracted = metadata.get('is_retracted', False)
    concepts = metadata.get('concepts', [])
    top_concepts = ", ".join([c.get('display_name', '') for c in concepts if c.get('score', 0) > 0.3]) if concepts else "Unknown"
    from datetime import datetime
    current_year = datetime.now().year

    prompt = f"""
    The current year is {current_year}.
You are an expert in academic publishing and research integrity. Given the following metadata, assess the credibility of this scientific paper on a scale from 0 (not credible) to 100 (highly credible). 
Consider all signals: author ORCID and affiliations, publisher reputation, journal indexing (DOAJ, Scopus), journal h-index, retraction history, citation count, DOI, open access status, and concept specificity.

**Metadata:**
- Paper Title: {metadata.get('title', 'Unknown')}
- Publication Year: {publication_year}
- Cited By Count: {cited_by_count}
- Is Retracted: {is_retracted}
- DOI: {doi}
- Open Access: {open_access}
- Authors: {', '.join(author_names)}
- Author ORCID Count: {orcid_count}/{author_count}
- Author Affiliations: {', '.join(author_affiliations)}
- Author Retraction Rates: {', '.join(str(r) for r in retraction_rates) if retraction_rates else 'None'}
- Journal Title: {journal_title}
- Publisher: {publisher}
- In DOAJ: {is_in_doaj}
- Indexed in Scopus: {is_indexed_in_scopus}
- Journal h-index: {h_index}
- Journal Retraction Rate: {retraction_rate:.2%}
- Journal Retracted Papers Count: {retracted_papers_count}
- Top Concepts: {top_concepts}

**Instructions:**
- Consider all metadata and use your expertise to decide if the publisher is trusted, if author affiliations are reputable, and if the journal is credible.
- If the paper is retracted, assign a very low score.
- If the journal is open access but not in DOAJ, treat as a red flag.
- If the publisher is known to be reputable, this is a strong positive.
- If authors have ORCID and reputable affiliations, this is a positive sign.
- If the journal has a high h-index and is indexed in Scopus, this is a strong positive.
- If the journal or authors have a high retraction rate, this is a strong negative.
- If the paper is old and has no citations, this is a negative.
- If the DOI is missing or invalid, this is a strong negative.
- If the paper's concepts are broad or unrelated, this is a negative.
- Weigh all factors and provide a single confidence score (0-100).

**Output:**
1. Confidence Score (0-100): [your score]
2. Rationale: String explaining the reason in less than 250 words strictly. (consider that I'm a human reader and I need to understand your reasoning. As a web developer, This string will directly dumped on the UI.)

Respond in this format:
Confidence Score: [score]
Rationale (HTML): [A short, well-formed HTML block. Use <ul> and <li> for lists, <a> for links and <p> for paragraphs. Do not mix plain text and HTML tags outside of a block. All content should be inside <p>, <ul>, <li>, or <b> tags as appropriate. The reasoning should be a very convincing, max 300 words. 
If possible, include specific proofs or evidence (such as direct metadata values, explicit journal or publisher names, or citation counts) that support your score. 
If you can, add external links to authoritative sources (e.g., DOAJ, publisher homepage, or retraction notices) as HTML <a> tags to increase credibility. 
This string will be shown directly in a web UI.]
"""
    return prompt

def get_paper_credibility(metadata):
    """
    Given paper metadata, generate a confidence score (0-100) for legitimacy.
    Uses: DOAJ status, publisher, author ORCID, author affiliations, open access, concepts, citation count, etc.
    """
    prompt = paper_credibility_prompt(metadata)
    try:
        response = anthropic.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=500,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        text = response.content[0].text.strip()
        score, rationale = parse_llm_paper_confidence_output(text)
        return score, rationale

    except Exception as e:
        print(f"Failed to get paper credibility: {e}")
        return ERROR_STATE, ERROR_STATE

def parse_llm_paper_confidence_output(llm_output):
    """
    Parses the LLM output for confidence score and rationale.
    Returns (score: int, rationale: list of str)
    """
    import re

    # Extract score
    score_match = re.search(r'Confidence Score:\s*(\d+)', llm_output)
    score = int(score_match.group(1)) if score_match else None

    # Extract rationale as HTML string
    rationale_match = re.search(r'Rationale\s*\(HTML\):\s*(.*)', llm_output, re.DOTALL)
    rationale_html = rationale_match.group(1).strip() if rationale_match else ""

    return score, rationale_html

def journal_credibility_prompt(metadata):
    """
    Compose a prompt for an LLM to assess journal credibility using all available OpenAlex metadata.
    """
    # Prepare author and affiliation summaries
    authors_info = metadata.get('authors_who_pulished_in_this_journal_info', [])
    
    # Journal metadata fields
    is_in_doaj = metadata.get('is_in_doaj', False)
    is_core = metadata.get('is_core', False)
    is_open_access = metadata.get('is_open_access', False)
    publisher = metadata.get('publisher', 'Unknown')
    host_organization_name = metadata.get('host_organization_name', 'Unknown')
    country_code = metadata.get('country_code', 'Unknown')
    apc_prices = metadata.get('apc_prices', 'Unknown')
    apc_usd = metadata.get('apc_usd', 'Unknown')
    works_count = metadata.get('works_count', 0)
    cited_by_count = metadata.get('cited_by_count', 0)
    h_index = metadata.get('h_index', 'Unknown')
    i10_index = metadata.get('i10_index', 'Unknown')
    two_yr_mean_citedness = metadata.get('two_yr_mean_citedness', 'Unknown')
    retracted_papers_count = metadata.get('retracted_papers_count', 0)
    retraction_rate = metadata.get('retraction_rate', 0.0)
    homepage_url = metadata.get('homepage_url', 'N/A')
    title = metadata.get('title', 'Unknown')
    fields_of_research = ', '.join(metadata.get('fields_of_research', []))

    from datetime import datetime
    current_year = datetime.now().year

    prompt = f"""
The current year is {current_year}.
You are an expert in academic publishing and research integrity. Given the following metadata, assess the credibility of this journal on a scale from 0 (not credible/predatory) to 100 (highly credible). 
Consider all signals: DOAJ and core index status, publisher and host organization reputation, country code, APC transparency, citation and impact metrics, retraction history, author ORCID and affiliations, and scope.

**Journal Metadata:**
- Title: {title}
- Publisher: {publisher}
- Host Organization: {host_organization_name}
- Homepage URL: {homepage_url}
- In DOAJ: {is_in_doaj}
- In Core Index: {is_core}
- Is Open Access: {is_open_access}
- Country Code: {country_code}
- APC Prices: {apc_prices}
- APC USD: {apc_usd}
- Total Works: {works_count}
- Cited By Count: {cited_by_count}
- H-Index: {h_index}
- I10 Index: {i10_index}
- 2-Year Mean Citedness: {two_yr_mean_citedness}
- Retraction Rate: {retraction_rate:.2%}
- Retracted Papers Count: {retracted_papers_count}
- Fields of Research: {fields_of_research}
- Author Information: {authors_info}

**Instructions:**
- If the journal is open access but not in DOAJ, this is a major red flag.
- If the journal is not in any core scholarly index, this is a moderate risk.
- If the publisher or host organization is on a known blacklist, this is a critical risk.
- If the publisher is unknown or not in a whitelist, this is a minor risk.
- If APC info is missing for an OA journal, this is a transparency issue.
- If the journal has high output but low citations or h-index, this is a strong risk.
- If the journal has a high retraction rate or count, this is a strong risk.
- If the journal's scope is unusually broad, this is a minor risk.
- If the journal is in DOAJ or a core index, or published by a reputable publisher, this is a strong positive.
- Weigh all factors and provide a single confidence score (0-100).

**Output:**
1. Confidence Score (0-100): [your score]
2. Rationale: String explaining the reason in less than 250 words strictly. (This string will be shown directly to a human user.)

Respond in this format:
Confidence Score: [score]
Rationale (HTML): [A short, well-formed HTML block. Use <ul> and <li> for lists, <a> for links and <p> for paragraphs. Do not mix plain text and HTML tags outside of a block. All content should be inside <p>, <ul>, <li>, or <b> tags as appropriate. The reasoning should be a very convincing, max 300 words. 
If possible, include specific proofs or evidence (such as direct metadata values, explicit journal or publisher names, or citation counts) that support your score. 
If you can, add external links to authoritative sources (e.g., DOAJ, publisher homepage, or retraction notices) as HTML <a> tags to increase credibility. 
This string will be shown directly in a web UI.]
"""
    return prompt

def get_journal_credibility(metadata):
    """
    Given journal metadata, generate a confidence score (0-100) for legitimacy using Anthropic LLM.
    """
    prompt = journal_credibility_prompt(metadata)
    try:
        response = anthropic.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=500,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        text = response.content[0].text.strip()
        score, rationale = parse_llm_paper_confidence_output(text)
        return score, rationale
    except Exception as e:
        print(f"Failed to get journal credibility: {e}")
        return ERROR_STATE, ERROR_STATE

"""
api_utils.py

Author: Abhishek Bakare (https://www.linkedin.com/in/abhishekbakare/)
Contact: abakre5@gmail.com

This module provides utility functions for interacting with the OpenAlex API and the Anthropic API.
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
    hijacked_issns_file = "docs/hijacked_issn.txt"
    hijacked_journal_names_file = "docs/hijacked_journal_title.txt"
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
                counts_by_year = source.get('counts_by_year', NOT_FOUND)

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
                    "retraction_rate": retraction_rate,
                    "counts_by_year": counts_by_year  
                }
        return None
    except Exception as e:
        print(f"Failed to fetch journal metadata: {e}")
        return ERROR_STATE

def get_author_metadata_for_paper(paper_data):
    """
    Returns a list of dicts, one per author, with:
      - name (display_name)
      - has_orcid (True/False)
      - affiliation (display_name of the first institution)
      - is_corresponding (True/False)
      - author_position (first, second, etc.)
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
            
            is_corresponding = author.get('is_corresponding', False)
            author_position = author.get('author_position', NOT_FOUND)

            author_info.append({
                'name': name,
                'has_orcid': has_orcid,
                'affiliation': affiliation,
                'is_corresponding': is_corresponding,
                'author_position': author_position
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
            location_data = None
            if locations_count != 0:
                for loc in locations:
                    if loc.get('source'):
                        location_data = loc
                        break

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
            is_in_doaj = NOT_FOUND
            publisher = NOT_FOUND
            open_access = NOT_FOUND
            if location_data != None:
                location_data.get('source', {}).get('is_in_doaj', NOT_FOUND)
                publisher = location_data.get('source', {}).get('display_name', NOT_FOUND)
                open_access = location_data.get('is_oa', NOT_FOUND)

            # Other relevant metadata
            title = paper.get('title', NOT_FOUND)
            author_count = len(author_metadata) if isinstance(author_metadata, list) else NOT_FOUND
            concepts = paper.get('concepts', NOT_FOUND)
            language = paper.get('language', NOT_FOUND)
            doi = paper.get('doi', NOT_FOUND)
            is_retracted = paper.get('is_retracted', False)

            # Get journal/source id for further metadata
            journal_source_id = NOT_FOUND
            journal_issn = NOT_FOUND
            if location_data != None:
                journal_source_id = location_data.get('source', {}).get('id', None)
                journal_issn = location_data.get('source', {}).get('issn_l', None)
            journal_metadata = None
            if journal_source_id:
                # Prefer ISSN if available for exact match
                if journal_issn:
                    journal_metadata = get_journal_metadata(journal_issn, is_issn=True)
                else:
                    journal_metadata = get_journal_metadata(journal_source_id, is_issn=False)


            grants = paper.get('grants', NOT_FOUND)  # List of grants associated with the paper
            referenced_works_count = paper.get('referenced_works_count', NOT_FOUND)  # Number of works this paper references
            related_works = paper.get('related_works', NOT_FOUND)  # List of related work IDs
            sustainable_development_goals = paper.get('sustainable_development_goals', NOT_FOUND)  # SDGs associated with the paper
            counts_by_year = paper.get('counts_by_year', NOT_FOUND)  # Citation and publication counts by year
            publication_date = paper.get('publication_date', NOT_FOUND)  # Full publication date (YYYY-MM-DD)
            created_date = paper.get('created_date', NOT_FOUND)  # Date the record was created in OpenAlex

            return {
                'title': title,                                     # (str) The title of the research paper.
                'publication_year': publication_year,               # (int) The year the paper was published.
                'cited_by_count': cited_by_count,                   # (int) Total number of times this paper has been cited.
                'years_since_publication': years_since_publication, # (int) Number of years since the paper was published.
                'total_paper_citation_count': total_paper_citation_count, # (int) Same as cited_by_count.
                'author_metadata': author_metadata,                 # (list of dicts) List of authors with their details.
                'author_count': author_count,                       # (int) Number of authors for this paper.
                'is_in_doaj': is_in_doaj,                           # (bool or str) Whether the journal is listed in DOAJ.
                'publisher': publisher,                             # (str) Name of the journal's publisher.
                'open_access': open_access,                         # (bool or str) Whether the paper is open access.
                'concepts': concepts,                               # (list) List of research topics/concepts.
                'language': language,                               # (str) Language of the paper.
                'doi': doi,                                         # (str) Digital Object Identifier for the paper.
                'locations_count': locations_count,                 # (int) Number of locations (sources) where the paper is indexed.
                'locations': locations,                             # (list) List of location/source dicts.
                'is_retracted': is_retracted,                       # (bool) Whether the paper has been retracted.
                'journal_metadata': journal_metadata,               # (dict or None) Metadata about the journal.
                'grants': grants,                                   # (list) Grants associated with the paper.
                'referenced_works_count': referenced_works_count,   # (int) Number of works this paper references.
                'related_works': related_works,                     # (list) List of related work IDs.
                'sustainable_development_goals': sustainable_development_goals, # (list) SDGs associated with the paper.
                'counts_by_year': counts_by_year,                   # (list) Citation/publication counts by year.
                'publication_date': publication_date,               # (str) Full publication date (YYYY-MM-DD).
                'created_date': created_date                        # (str) Date the record was created in OpenAlex.
            }
        return NOT_FOUND
    except Exception as e:
        print(f"Failed to fetch paper metadata: {e}")
        traceback.print_exc()
        return ERROR_STATE


def paper_credibility_prompt(metadata):
    """
    Compose a detailed prompt for an LLM to assess scientific paper credibility using all available metadata.
    This version covers all fields returned by get_paper_metadata_v2 and provides clear, explicit instructions.
    """
    from datetime import datetime
    current_year = datetime.now().year

    # Author summary
    author_metadata = metadata.get('author_metadata', [])
    author_count = metadata.get('author_count', 0)
    author_names = [a.get('name', 'Unknown') for a in author_metadata] if isinstance(author_metadata, list) else []
    orcid_count = sum(1 for a in author_metadata if a.get('has_orcid')) if isinstance(author_metadata, list) else 0
    author_affiliations = [a.get('affiliation', 'Unknown') for a in author_metadata] if isinstance(author_metadata, list) else []
    corresponding_authors = [a.get('name', 'Unknown') for a in author_metadata if a.get('is_corresponding')] if isinstance(author_metadata, list) else []
    author_positions = [a.get('author_position', 'Unknown') for a in author_metadata] if isinstance(author_metadata, list) else []

    # Journal metadata
    journal = metadata.get('journal_metadata', {}) or {}
    journal_title = journal.get('title', 'Unknown')
    publisher = journal.get('publisher', 'Unknown')
    is_in_doaj = journal.get('is_in_doaj', False)
    is_indexed_in_scopus = journal.get('is_indexed_in_scopus', False)
    h_index = journal.get('h_index', 'Unknown')
    retraction_rate = journal.get('retraction_rate', 0.0)
    retracted_papers_count = journal.get('retracted_papers_count', 0)

    # Paper-level
    title = metadata.get('title', 'Unknown')
    publication_year = metadata.get('publication_year', 'Unknown')
    publication_date = metadata.get('publication_date', 'Unknown')
    created_date = metadata.get('created_date', 'Unknown')
    cited_by_count = metadata.get('cited_by_count', 0)
    years_since_publication = metadata.get('years_since_publication', 'Unknown')
    total_paper_citation_count = metadata.get('total_paper_citation_count', 0)
    open_access = metadata.get('open_access', False)
    is_retracted = metadata.get('is_retracted', False)
    doi = metadata.get('doi', 'Unknown')
    language = metadata.get('language', 'Unknown')
    concepts = metadata.get('concepts', [])
    top_concepts = ", ".join([c.get('display_name', '') for c in concepts if c.get('score', 0) > 0.3]) if concepts else "Unknown"
    referenced_works_count = metadata.get('referenced_works_count', 'Unknown')
    related_works = metadata.get('related_works', [])
    related_works_count = len(related_works) if isinstance(related_works, list) else "Unknown"
    sustainable_development_goals = metadata.get('sustainable_development_goals', [])
    sdg_summary = ", ".join([sdg.get('display_name', 'Unknown') for sdg in sustainable_development_goals]) if sustainable_development_goals else "None"
    counts_by_year = metadata.get('counts_by_year', [])
    grants = metadata.get('grants', [])
    grants_summary = ", ".join([g.get('funder_display_name', 'Unknown') for g in grants]) if grants else "None"

    prompt = f"""
The current year is {current_year}.
You are an expert in academic publishing and research integrity. Given the following metadata, assess the credibility of this scientific paper on a scale from 0 (not credible/predatory) to 100 (highly credible).

**Metadata:**
- Paper Title: {title}
- Publication Year: {publication_year}
- Publication Date: {publication_date}
- Record Created Date: {created_date}
- Years Since Publication: {years_since_publication}
- Cited By Count: {cited_by_count}
- Total Paper Citation Count: {total_paper_citation_count}
- Referenced Works Count: {referenced_works_count}
- Related Works Count: {related_works_count}
- Is Retracted: {is_retracted}
- DOI: {doi}
- Open Access: {open_access}
- Language: {language}
- Author Count: {author_count}
- Authors: {', '.join(author_names)}
- Author ORCID Count: {orcid_count}/{author_count}
- Author Affiliations: {', '.join(author_affiliations)}
- Corresponding Authors: {', '.join(corresponding_authors) if corresponding_authors else 'None'}
- Author Positions: {', '.join(str(pos) for pos in author_positions) if author_positions else 'Unknown'}
- Grants/Funding: {grants_summary}
- Sustainable Development Goals: {sdg_summary}
- Journal Title: {journal_title}
- Publisher: {publisher}
- In DOAJ: {is_in_doaj}
- Indexed in Scopus: {is_indexed_in_scopus}
- Journal h-index: {h_index}
- Journal Retraction Rate: {retraction_rate:.2%}
- Journal Retracted Papers Count: {retracted_papers_count}
- Top Concepts: {top_concepts}
- Counts by Year: {counts_by_year}

**Instructions:**
- If the journal or publisher is associated with aggressive pay-to-publish advertising, or if the APC is highlighted as a main feature, treat this as a major red flag and deduct at least 40 points.
- If the journal is listed on known predatory lists, or there are credible external reports of predatory practices, assign a score below 30.
- If the journal is not in DOAJ or a core index, or lacks a reputable publisher, do not assign a score above 70.
- If the journal or publisher is not transparent about APCs, or if APCs are unusually high/low, treat this as a strong negative.
- If the editorial board is missing or unverifiable, or if the journal lacks clear peer review policies, treat this as a major red flag.
- If the paper is retracted, assign a very low score.
- If the paper is old and has no citations, this is a negative.
- If the DOI is missing or invalid, this is a strong negative.
- If the paper's concepts are broad or unrelated, this is a negative.
- If the paper is supported by reputable grants or aligns with recognized Sustainable Development Goals, this is a positive.
- If the referenced works count is unusually low or high, or if citation patterns are suspicious, mention this.
- If the author count is unusually high or low for the field, mention this.
- If the publication date or created date is inconsistent with citation counts, mention this.
- If the language is inconsistent with the journal's scope or target audience, mention this.
- If the corresponding author or author positions indicate unusual authorship patterns, mention this.
- Weigh all factors and provide a single confidence score (0-100).

**Output:**
1. Confidence Score (0-100): [your score]
2. Rationale: String explaining the reason in less than 400 words strictly. (This string will be shown directly to a human user.)

Respond in this format:
Confidence Score: [score]
Rationale (HTML): [A short, well-formed HTML block. Use <ul> and <li> for lists, <a> for links and <p> for paragraphs. Do not mix plain text and HTML tags outside of a block. All content should be inside <p>, <ul>, <li>, or <b> tags as appropriate. The reasoning should be a very convincing, max 400 words. 
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
    counts_by_year = metadata.get('counts_by_year', 'Unknown')

    from datetime import datetime
    current_year = datetime.now().year

    prompt = f"""
The current year is {current_year}.
You are an expert in academic publishing and research integrity. Given the following metadata from OpenAlex, assess the credibility of this journal on a scale from 0 (not credible/predatory) to 100 (highly credible). 
Consider all signals: DOAJ and core index status, publisher and host organization reputation, country code, APC transparency, citation and impact metrics, retraction history, author ORCID and affiliations, scope consistency, and annual trends in publication/citation counts.

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
- Counts by Year: {counts_by_year}

**Instructions:**
- Assign weights: Indexing status (25%), Publisher/Host Reputation (20%), Citation Metrics (15%), Retraction History (15%), Author Credibility (10%), Transparency (10%), Scope Consistency (5%).
- If open access but not in DOAJ, deduct 20 points.
- If not in any core index (e.g., Scopus, Web of Science) or delisted, deduct 25 points. Specify delisting status if known (via `is_core`).
- If publisher/host is on a known blacklist (e.g., Beall’s List), deduct 30 points.
- If publisher is unknown or not in a whitelist (e.g., OASPA members), deduct 10 points.
- If APC info is missing or hidden for an OA journal, deduct 15 points.
- If total works > 500/year but h-index < 10, deduct 15 points.
- If retraction rate > 1% or retracted papers > 5, deduct 20 points.
- If scope spans > 5 unrelated fields in `fields_of_research` (e.g., medicine and physics), deduct 10 points.
- If in DOAJ or a core index, add 20 points; if published by a reputable publisher (e.g., Elsevier, Springer), add 15 points.
- If homepage URL is missing, uses a non-standard domain (e.g., .biz), or lacks professional design, deduct 10 points.
- If publisher/host lacks transparency (no contact info, address), deduct 10 points.
- If APCs are < $200 USD or > $3000 USD compared to field norms (e.g., $1000–$2000 for engineering journals), deduct 10 points.
- If >50% of authors lack ORCID or reputable affiliations (e.g., top universities), deduct 10 points.
- If >50% of authors in `authors_info` lack ORCID, or if frequent self-citation patterns are evident (e.g., >30% of `cited_by_count` from same authors), deduct 10 points.
- If `counts_by_year` shows sudden spikes (>50% increase in works or citations in one year) or drops (>50% decrease), deduct 10 points for potential manipulation or instability.
- If h-index or `two_yr_mean_citedness` is inconsistent with field norms (e.g., h-index < 5 for engineering journals with >500 works), deduct 10 points.
- If ISSN is unregistered or linked to multiple unrelated titles (via `issn_l`), deduct 20 points.
- Provide a single confidence score (0-100) based on weighted factors.

**Output:**
1. Confidence Score (0-100): [your score]
2. Rationale: Explain the reasoning in less than 400 words, focusing on weighted factors, red flags, and positive signals. Don't talk about weights in here. (This will be shown directly to a human user.)

Respond in this format:
Confidence Score: [score]
Rationale (HTML): [A short, well-formed HTML block. Use <ul> and <li> for lists, <a> for links and <p> for paragraphs. Do not mix plain text and HTML tags outside of a block. All content should be inside <p>, <ul>, <li>, or <b> tags as appropriate. The reasoning should be a very convincing, max 400 words. 
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

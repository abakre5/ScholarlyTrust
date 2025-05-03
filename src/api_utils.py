import requests
import streamlit as st
from anthropic import Anthropic
import numpy as np
import os
import re
from config import ANTHROPIC_MODEL

# Initialize Anthropic client
try:
    anthropic = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
except KeyError:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        anthropic = Anthropic(api_key=api_key)
    else:
        st.error("Anthropic API key not found. Please set it in secrets.toml or as an environment variable.")
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
        st.error(f"Failed to query OpenAlex API for journal: {e}")
        return False

def get_journal_metadata(issn):
    url = f"https://api.openalex.org/sources?filter=issn:{issn}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data['meta']['count'] > 0:
                source = data['results'][0]
                # Extract fields
                title = source.get('display_name', 'Unknown')
                publisher = source.get('host_organization_name', 'Unknown')
                homepage_url = source.get('homepage_url', 'N/A')
                is_in_doaj = source.get('is_in_doaj', False)
                is_open_access = source.get('is_oa', False)
                country_code = source.get('country_code', 'Unknown')
                works_count = source.get('works_count', 0)
                cited_by_count = source.get('cited_by_count', 0)
                fields_of_research = [
                    topic.get('display_name', 'Unknown')
                    for topic in source.get('topics', [])
                ]

                return {
                    "title": title,
                    "publisher": publisher,
                    "homepage_url": homepage_url,
                    "is_in_doaj": is_in_doaj,
                    "is_open_access": is_open_access,
                    "country_code": country_code,
                    "works_count": works_count,
                    "cited_by_count": cited_by_count,
                    "fields_of_research": fields_of_research,
                }
        return None
    except Exception as e:
        st.error(f"Failed to fetch journal metadata: {e}")
        return None

def get_author_metadata_for_paper(paper_data):
    try:
        authors = paper_data.get('authorships', [])
        if not authors:
            return None

        publication_counts = []
        cited_by_counts = []
        two_year_citedness = []
        orcids = []
        concepts = []
        publication_trends = []
        current_year = 2025

        for author in authors:
            author_data = author.get('author', {})
            author_id = author_data.get('id', '').split('/')[-1]
            author_name = author_data.get('display_name', 'Unknown')
            orcid = author_data.get('orcid', None)

            # ORCID presence
            orcids.append(1 if orcid else 0)

            # Extract concepts related to the author
            paper_title = paper_data.get('title', '').lower()
            author_concepts = [
                f"{concept.get('display_name', 'Unknown')} (score: {concept.get('score', 0)})"
                for concept in paper_data.get('concepts', [])
                if concept.get('score', 0) > 0.5 and concept.get('display_name', '').lower() in paper_title
            ]
            concepts.append("; ".join(author_concepts) if author_concepts else "Unknown")

            # Extract publication trends (if available)
            institutions = author.get('institutions', [])
            institution_names = [inst.get('display_name', 'Unknown') for inst in institutions]
            publication_trends.append(", ".join(institution_names) if institution_names else "N/A")

        # Aggregate metadata
        return {
            'avg_author_publications': np.mean(publication_counts) if publication_counts else 0,
            'avg_author_cited_by_count': np.mean(cited_by_counts) if cited_by_counts else 0,
            'avg_author_2yr_citedness': np.mean(two_year_citedness) if two_year_citedness else 0,
            'orcid_presence': 'Yes' if np.mean(orcids) > 0 else 'No',
            'top_concepts': "; ".join(set(concepts)),
            'publication_trend': "; ".join(set(publication_trends))
        }
    except Exception as e:
        st.error(f"Failed to fetch author metadata: {e}")
        return None

def get_paper_metadata(paper_input, input_type):
    if input_type == 'doi':
        url = f"https://api.openalex.org/works?filter=doi:{paper_input}"
    else:
        url = f"https://api.openalex.org/works?filter=title.search:{paper_input.replace(' ', '%20')}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data['meta']['count'] > 0:
                paper = data['results'][0]
                # Extract journal ISSN
                journal_issn = paper.get('primary_location', {}).get('source', {}).get('issn_l', '') or \
                               (paper.get('primary_location', {}).get('source', {}).get('issn', [])[0] if paper.get('primary_location', {}).get('source', {}).get('issn') else '')

                # Extract publication year and citation data
                publication_year = paper.get('publication_year', 0)
                cited_by_count = paper.get('cited_by_count', 0)
                years_since_publication = max(1, 2025 - publication_year)
                normalized_citations = cited_by_count / years_since_publication if publication_year >= 2023 else cited_by_count
                normalized_citations = max(normalized_citations, 3.0) if publication_year >= 2024 else normalized_citations

                # Build paper metadata dictionary
                paper_metadata = {
                    'title': paper.get('title', 'Unknown'),
                    'journal_issn': journal_issn,
                    'publication_year': publication_year,
                    'cited_by_count': normalized_citations,
                    'author_count': len(paper.get('authorships', [])),
                    'is_in_doaj': paper.get('primary_location', {}).get('source', {}).get('is_in_doaj', False),
                    'publisher': paper.get('primary_location', {}).get('source', {}).get('host_organization_name', 'Unknown')
                }

                # Add author metadata
                author_metadata = get_author_metadata_for_paper(paper)
                if author_metadata:
                    paper_metadata.update(author_metadata)
                else:
                    paper_metadata.update({
                        'avg_author_publications': 0,
                        'avg_author_cited_by_count': 0,
                        'avg_author_2yr_citedness': 0,
                        'orcid_presence': 'No',
                        'top_concepts': 'Unknown',
                        'publication_trend': 'N/A'
                    })

                return paper_metadata
        return None
    except Exception as e:
        st.error(f"Failed to fetch paper metadata: {e}")
        return None

def get_journal_confidence(metadata):
    prompt = f"""
    You are an expert in academic publishing. Evaluate the legitimacy of the following journal and provide a confidence score (0-100), where a higher score indicates greater legitimacy. 
    Consider the following factors:
    1. Publisher reputation: Journals published by reputable organizations (e.g., Nature Portfolio, Elsevier, Springer, Wiley, American Society for Microbiology) are more likely to be legitimate.
    2. DOAJ indexing: Journals listed in the Directory of Open Access Journals (DOAJ) are more credible.
    3. Citation impact: High citation counts indicate greater influence and legitimacy.
    4. Publication volume: A higher number of works published can indicate credibility.
    5. Fields of research: Journals with well-defined and respected fields of research are more likely to be legitimate.

    Recognize predatory journals by:
    - Low citation counts.
    - Lack of DOAJ indexing.
    - Questionable or unknown publishers.

    Use the following metadata to make your decision:
    - Title: {metadata['title']}
    - Publisher: {metadata['publisher']}
    - Homepage URL: {metadata['homepage_url']}
    - In DOAJ: {metadata['is_in_doaj']}
    - Is Open Access: {metadata['is_open_access']}
    - Country Code: {metadata['country_code']}
    - Total Works: {metadata['works_count']}
    - Cited By Count: {metadata['cited_by_count']}
    - Fields of Research: {', '.join(metadata['fields_of_research'])}

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
        raise ValueError("No integer found in Claude response")
    except Exception as e:
        raise Exception(f"Anthropic API error: {e}")

def get_paper_confidence(metadata):
    new_researcher = metadata.get('avg_author_publications', 0) < 5
    if new_researcher:
        prompt = f"You are an expert in academic publishing. Provide a confidence score (0-100) indicating the likelihood that the paper is legitimate (higher score = more legitimate). For new researchers (low publication count), assign weights: ORCID presence (35%), publisher reputation (30%, high for American Society for Microbiology, Nature, Elsevier, Springer, Wiley), external recognition (25%, citations/co-authorship in reputable venues as proxy for media coverage), publication trends (5%), concept alignment (5%). Recognize predatory papers (e.g., ISSN 2313-1799) by non-DOAJ journals, no ORCID, or misaligned concepts, but avoid flagging new researchers unless clear evidence exists. A paper is legitimate if published by reputable publishers (e.g., ASM for ISSN 1092-2172) or authors have ORCID. Ensure top concepts align with paper title: {metadata['title']}. Metadata: Title: {metadata['title']}, Journal ISSN: {metadata['journal_issn'] or 'Unknown'}, Publication Year: {metadata['publication_year']}, Cited By Count (per year): {metadata['cited_by_count']}, Author Count: {metadata['author_count']}, In DOAJ: {metadata['is_in_doaj']}, Average Author Publication Count (normalized): {metadata['avg_author_publications']}, Average Author Total Citations (normalized): {metadata['avg_author_cited_by_count']}, Average Author 2-Year Mean Citedness: {metadata['avg_author_2yr_citedness']}, ORCID Presence: {metadata['orcid_presence']}, Top Author Concepts: {metadata['top_concepts']}, Author Publication Trend (Last 5 Years): {metadata['publication_trend']}, Publisher: {metadata['publisher']}, New Researcher: {'Yes' if new_researcher else 'No'}. **Respond with only a single integer between 0 and 100, with no additional text or explanation.**"
    else:
        prompt = f"You are an expert in academic publishing. Provide a confidence score (0-100) indicating the likelihood that the paper is legitimate (higher score = more legitimate). Assign weights: ORCID presence (25%), external recognition (25%, citations/co-authorship in reputable venues as proxy for media coverage), publication trends (10%), concept alignment (5%), publisher reputation (25%, high for American Society for Microbiology, Nature, Elsevier, Springer, Wiley), DOAJ indexing (10%). Recognize predatory papers (e.g., ISSN 2313-1799) by non-DOAJ journals, no ORCID, or misaligned concepts. A paper is legitimate if authors have ORCID, external recognition, or published by reputable publishers (e.g., ASM for ISSN 1092-2172). Ensure top concepts align with paper title: {metadata['title']}. Metadata: Title: {metadata['title']}, Journal ISSN: {metadata['journal_issn'] or 'Unknown'}, Publication Year: {metadata['publication_year']}, Cited By Count (per year): {metadata['cited_by_count']}, Author Count: {metadata['author_count']}, In DOAJ: {metadata['is_in_doaj']}, Average Author Publication Count (normalized): {metadata['avg_author_publications']}, Average Author Total Citations (normalized): {metadata['avg_author_cited_by_count']}, Average Author 2-Year Mean Citedness: {metadata['avg_author_2yr_citedness']}, ORCID Presence: {metadata['orcid_presence']}, Top Author Concepts: {metadata['top_concepts']}, Author Publication Trend (Last 5 Years): {metadata['publication_trend']}, Publisher: {metadata['publisher']}, New Researcher: {'Yes' if new_researcher else 'No'}. **Respond with only a single integer between 0 and 100, with no additional text or explanation.**"
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
        raise Exception(f"Anthropic API error: {e}")
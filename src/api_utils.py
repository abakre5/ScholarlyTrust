import requests
import streamlit as st
from anthropic import Anthropic
import numpy as np
import os
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
    url = f"https://api.openalex.org/sources?filter=ids.value:{issn},ids.schema:ISSN"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data['meta']['count'] > 0:
                source = data['results'][0]
                total_works = sum(count['works_count'] for count in source.get('counts_by_year', []))
                works_url = f"https://api.openalex.org/works?filter=source.id:{source['id']}&per-page=100"
                works_response = requests.get(works_url)
                avg_citations = 0
                if works_response.status_code == 200:
                    works_data = works_response.json()
                    citations = [work.get('cited_by_count', 0) for work in works_data.get('results', [])]
                    avg_citations = np.mean(citations) if citations else 0
                return {
                    'total_works': total_works,
                    'avg_citations': avg_citations,
                    'is_in_doaj': source.get('is_in_doaj', False)
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
        h_indices = []
        affiliations = []
        avg_citations_list = []
        for author in authors:
            author_id = author.get('author', {}).get('id', '').split('/')[-1]
            if author_id:
                url = f"https://api.openalex.org/authors/{author_id}"
                response = requests.get(url)
                if response.status_code == 200:
                    author_data = response.json()
                    publication_counts.append(author_data.get('works_count', 0))
                    h_indices.append(author_data.get('h_index', 0))
                    affs = [inst.get('display_name', 'Unknown') for inst in author_data.get('affiliations', [])]
                    affiliations.append(", ".join(affs) if affs else "Unknown")
                    works_url = f"https://api.openalex.org/works?filter=author.id:{author_id}&per-page=100"
                    works_response = requests.get(works_url)
                    if works_response.status_code == 200:
                        works_data = works_response.json()
                        citations = [work.get('cited_by_count', 0) for work in works_data.get('results', [])]
                        avg_citations = np.mean(citations) if citations else 0
                        avg_citations_list.append(avg_citations)
        if publication_counts:
            return {
                'avg_author_publications': np.mean(publication_counts),
                'avg_author_h_index': np.mean(h_indices),
                'author_affiliations': "; ".join(set(affiliations)),
                'avg_author_citations': np.mean(avg_citations_list) if avg_citations_list else 0
            }
        return None
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
                journal_issn = paper.get('host_venue', {}).get('issn_l', '') or paper.get('host_venue', {}).get('issn', [''])[0]
                paper_metadata = {
                    'title': paper.get('title', 'Unknown'),
                    'journal_issn': journal_issn,
                    'publication_year': paper.get('publication_year', 0),
                    'cited_by_count': paper.get('cited_by_count', 0),
                    'author_count': len(paper.get('authorships', [])),
                    'is_in_doaj': is_in_doaj(journal_issn),
                    'abstract': paper.get('abstract', 'No abstract available')[:500]  # Limit to reduce tokens
                }
                # Fetch author metadata
                author_metadata = get_author_metadata_for_paper(paper)
                if author_metadata:
                    paper_metadata.update(author_metadata)
                else:
                    paper_metadata.update({
                        'avg_author_publications': 0,
                        'avg_author_h_index': 0,
                        'author_affiliations': 'Unknown',
                        'avg_author_citations': 0
                    })
                return paper_metadata
        return None
    except Exception as e:
        st.error(f"Failed to fetch paper metadata: {e}")
        return None

def get_journal_confidence(metadata):
    prompt = f"You are an expert in academic publishing. Given the following journal metadata, provide a confidence score (0-100) indicating the likelihood that the journal is legitimate (higher score = more legitimate). Consider factors like DOAJ indexing, citation counts, and publication volume to assess if it exhibits predatory behavior (e.g., low peer review quality, high fees). Metadata: Total Works: {metadata['total_works']}, Average Citations: {metadata['avg_citations']}, In DOAJ: {metadata['is_in_doaj']}. Respond with a single number representing the confidence score."
    try:
        response = anthropic.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=10,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return int(response.content[0].text.strip())
    except Exception as e:
        raise Exception(f"Anthropic API error: {e}")

def get_paper_confidence(metadata):
    prompt = f"You are an expert in academic publishing. Given the following research paper and author metadata, provide a confidence score (0-100) indicating the likelihood that the paper is legitimate (higher score = more legitimate). Consider paper factors (journal DOAJ indexing, citation counts, author count, publication year, abstract quality) and author factors (publication count, h-index, affiliations, average citations) to assess if it comes from a predatory source (e.g., low peer review, questionable journal, authors with excessive low-quality publications). Metadata: Title: {metadata['title']}, Journal ISSN: {metadata['journal_issn'] or 'Unknown'}, Publication Year: {metadata['publication_year']}, Cited By Count: {metadata['cited_by_count']}, Author Count: {metadata['author_count']}, In DOAJ: {metadata['is_in_doaj']}, Abstract: {metadata['abstract']}, Average Author Publication Count: {metadata['avg_author_publications']}, Average Author H-Index: {metadata['avg_author_h_index']}, Author Affiliations: {metadata['author_affiliations']}, Average Author Citations: {metadata['avg_author_citations']}. Respond with a single number representing the confidence score."
    try:
        response = anthropic.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=10,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return int(response.content[0].text.strip())
    except Exception as e:
        raise Exception(f"Anthropic API error: {e}")
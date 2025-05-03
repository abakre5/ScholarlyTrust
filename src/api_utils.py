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
                    'is_in_doaj': source.get('is_in_doaj', False),
                    'publisher': source.get('publisher', 'Unknown')
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
        cited_by_counts = []
        two_year_citedness = []
        orcids = []
        concepts = []
        publication_trends = []
        current_year = 2025
        for author in authors:
            author_id = author.get('author', {}).get('id', '').split('/')[-1]
            if author_id:
                url = f"https://api.openalex.org/authors/{author_id}"
                response = requests.get(url)
                if response.status_code == 200:
                    author_data = response.json()
                    works_count = author_data.get('works_count', 0)
                    publication_year = author_data.get('last_known_institution', {}).get('publication_year', current_year) or current_year
                    career_length = max(1, current_year - publication_year)
                    normalized_works = works_count / career_length
                    publication_counts.append(normalized_works)
                    h_indices.append(author_data.get('h_index', 0))
                    cited_by_count = author_data.get('cited_by_count', 0)
                    normalized_citations = cited_by_count / career_length if career_length > 0 else cited_by_count
                    cited_by_counts.append(normalized_citations)
                    two_year_citedness.append(author_data.get('summary_stats', {}).get('2yr_mean_citedness', 0))
                    orcids.append(1 if author_data.get('orcid') else 0)
                    author_concepts = [f"{concept.get('display_name', 'Unknown')} (score: {concept.get('score', 0)})" for concept in author_data.get('x_concepts', []) if concept.get('score', 0) > 50]
                    concepts.append("; ".join(author_concepts) if author_concepts else "Unknown")
                    yearly_counts = [count for count in author_data.get('counts_by_year', []) if count.get('works_count', 0) > 0]
                    trend = ", ".join([f"{count.get('year', 'N/A')}: {count.get('works_count', 0)} works" for count in yearly_counts[-5:]])
                    publication_trends.append(trend if trend else "N/A")
        if publication_counts:
            return {
                'avg_author_publications': np.mean(publication_counts),
                'avg_author_h_index': np.mean(h_indices),
                'avg_author_cited_by_count': np.mean(cited_by_counts),
                'avg_author_2yr_citedness': np.mean(two_year_citedness),
                'orcid_presence': 'Yes' if np.mean(orcids) > 0 else 'No',
                'top_concepts': "; ".join(set(concepts)),
                'publication_trend': "; ".join(set(publication_trends))
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
                publication_year = paper.get('publication_year', 0)
                cited_by_count = paper.get('cited_by_count', 0)
                years_since_publication = max(1, 2025 - publication_year)
                normalized_citations = cited_by_count / years_since_publication
                paper_metadata = {
                    'title': paper.get('title', 'Unknown'),
                    'journal_issn': journal_issn,
                    'publication_year': publication_year,
                    'cited_by_count': normalized_citations,
                    'author_count': len(paper.get('authorships', [])),
                    'is_in_doaj': is_in_doaj(journal_issn),
                    'abstract': paper.get('abstract', 'No abstract available')[:500],
                    'publisher': paper.get('host_venue', {}).get('publisher', 'Unknown')
                }
                author_metadata = get_author_metadata_for_paper(paper)
                if author_metadata:
                    paper_metadata.update(author_metadata)
                else:
                    paper_metadata.update({
                        'avg_author_publications': 0,
                        'avg_author_h_index': 0,
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
    prompt = f"You are an expert in academic publishing. Given the following journal metadata, provide a confidence score (0-100) indicating the likelihood that the journal is legitimate (higher score = more legitimate). Assign weights: publisher reputation (35%, high for publishers like ASM, Nature, Elsevier), DOAJ indexing (25%), citation counts (25%), publication volume (15%). Recognize predatory journals (e.g., ISSN 2313-1799) by low citations relative to works, lack of DOAJ indexing, or questionable publishers. A journal is legitimate if published by reputable publishers (e.g., ASM for ISSN 1092-2172) or has high citations. Metadata: Total Works: {metadata['total_works']}, Average Citations: {metadata['avg_citations']}, In DOAJ: {metadata['is_in_doaj']}, Publisher: {metadata['publisher']}. **Respond with only a single integer between 0 and 100, with no additional text or explanation.**"
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
            # Normalize score with logistic function
            normalized_score = int(100 / (1 + np.exp(-0.1 * (raw_score - 50))))
            return normalized_score
        raise ValueError("No integer found in Claude response")
    except Exception as e:
        raise Exception(f"Anthropic API error: {e}")

def get_paper_confidence(metadata):
    prompt = f"You are an expert in academic publishing. Given the following research paper and author metadata, provide a confidence score (0-100) indicating the likelihood that the paper is legitimate (higher score = more legitimate). Assign weights: publisher reputation (30%, high for ASM, Nature, Elsevier), author h-index (25%), ORCID presence (20%), paper citations (15%), publication trends (10%). Recognize predatory papers (e.g., ISSN 2313-1799) by non-DOAJ journals, low author h-index, no ORCID, or misaligned concepts. A paper is legitimate if published by reputable publishers (e.g., ASM for ISSN 1092-2172) or authors have high h-index/ORCID. Ensure top concepts align with paper title: {metadata['title']}. Metadata: Title: {metadata['title']}, Journal ISSN: {metadata['journal_issn'] or 'Unknown'}, Publication Year: {metadata['publication_year']}, Cited By Count (per year): {metadata['cited_by_count']}, Author Count: {metadata['author_count']}, In DOAJ: {metadata['is_in_doaj']}, Abstract: {metadata['abstract']}, Average Author Publication Count (normalized): {metadata['avg_author_publications']}, Average Author H-Index: {metadata['avg_author_h_index']}, Average Author Total Citations (normalized): {metadata['avg_author_cited_by_count']}, Average Author 2-Year Mean Citedness: {metadata['avg_author_2yr_citedness']}, ORCID Presence: {metadata['orcid_presence']}, Top Author Concepts: {metadata['top_concepts']}, Author Publication Trend (Last 5 Years): {metadata['publication_trend']}, Publisher: {metadata['publisher']}. **Respond with only a single integer between 0 and 100, with no additional text or explanation.**"
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
import streamlit as st
import requests
from urllib.parse import urlparse, urljoin
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import pandas as pd
from fake_useragent import UserAgent
import re
from datetime import datetime
import time

# Set page configuration
st.set_page_config(
    page_title="Advanced Hreflang Analysis Tool",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'results_data' not in st.session_state:
    st.session_state.results_data = []
if 'analysis_complete' not in st.session_state:
    st.session_state.analysis_complete = False

# Initialize fake user agent
ua = UserAgent()

def extract_urls_from_sitemap(sitemap_url):
    """Extract URLs from XML sitemap"""
    try:
        headers = {'User-Agent': ua.random}
        response = requests.get(sitemap_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        urls = []
        root = ET.fromstring(response.content)
        
        # Sitemap index
        if root.tag.endswith('sitemapindex'):
            for sitemap in root.findall('.//{*}sitemap/{*}loc'):
                urls.extend(extract_urls_from_sitemap(sitemap.text))
        # URL sitemap
        else:
            for url in root.findall('.//{*}url/{*}loc'):
                urls.append(url.text)
        
        return urls
    except Exception as e:
        st.error(f"Error processing sitemap {sitemap_url}: {str(e)}")
        return []

def analyze_hreflang_tag(lang, href, source_url, all_tags):
    """Analyze individual hreflang tag for issues"""
    warnings = []
    errors = []
    
    # Check language format
    if not re.match(r'^[a-z]{2}(-[a-z]{2})?$', lang) and lang != 'x-default':
        errors.append("Invalid hreflang format")
    
    # Check self-reference
    if href == source_url and '-' not in lang and lang != 'x-default':
        errors.append("Self-reference without region")
    
    # Check for region-independent fallback
    if '-' in lang:
        base_lang = lang.split('-')[0]
        has_fallback = any(tag == base_lang for tag, h in all_tags)
        if not has_fallback:
            warnings.append(f"Missing region-independent link for {base_lang}")
    
    # Check URL validity
    if not href.startswith(('http://', 'https://')):
        errors.append("Invalid URL format")
    
    # Check if alternate URL is in same domain
    if 'sitemap' not in href and not href.startswith(source_url):
        warnings.append("Alternate URL not in same domain")
    
    return warnings, errors

def get_language_name(code):
    """Convert language code to full name"""
    languages = {
        'en': 'English', 'ar': 'Arabic', 'es': 'Spanish', 'fr': 'French',
        'de': 'German', 'ja': 'Japanese', 'ko': 'Korean', 'zh': 'Chinese',
        'ru': 'Russian', 'pt': 'Portuguese', 'it': 'Italian', 'nl': 'Dutch',
        'tr': 'Turkish', 'sv': 'Swedish', 'pl': 'Polish', 'vi': 'Vietnamese',
        'th': 'Thai', 'id': 'Indonesian', 'ms': 'Malaysian', 'hi': 'Hindi'
    }
    return languages.get(code, code)

def get_region_name(code):
    """Convert region code to full name"""
    regions = {
        'us': 'United States', 'gb': 'United Kingdom', 'ae': 'United Arab Emirates',
        'sa': 'Saudi Arabia', 'kw': 'Kuwait', 'qa': 'Qatar', 'om': 'Oman',
        'bh': 'Bahrain', 'eg': 'Egypt', 'iq': 'Iraq', 'jo': 'Jordan',
        'lb': 'Lebanon', 'ly': 'Libya', 'ps': 'Palestinian Territory',
        'sd': 'Sudan', 'so': 'Somalia', 'sy': 'Syria', 'ye': 'Yemen',
        'au': 'Australia', 'ca': 'Canada', 'in': 'India', 'pk': 'Pakistan',
        'bd': 'Bangladesh', 'cn': 'China', 'jp': 'Japan', 'kr': 'South Korea',
        'de': 'Germany', 'fr': 'France', 'it': 'Italy', 'es': 'Spain',
        'ru': 'Russia', 'br': 'Brazil', 'mx': 'Mexico', 'ar': 'Argentina'
    }
    return regions.get(code, code)

def analyze_single_url(url, progress_bar=None, status_text=None):
    """Analyze a single URL for hreflang tags"""
    try:
        headers = {'User-Agent': ua.random}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract hreflang tags
        hreflang_tags = []
        for link in soup.find_all('link', rel='alternate', hreflang=True):
            hreflang = link.get('hreflang', '').lower()
            href = link.get('href', '')
            
            if href and not href.startswith(('http://', 'https://')):
                href = urljoin(url, href)
            
            hreflang_tags.append((hreflang, href))
        
        # Check self-referencing
        self_ref = any(href == url for lang, href in hreflang_tags)
        
        results = []
        # Analyze each hreflang tag
        for lang, href in hreflang_tags:
            warnings, errors = analyze_hreflang_tag(lang, href, url, hreflang_tags)
            
            # Extract language and region
            lang_parts = lang.split('-')
            language = lang_parts[0] if lang_parts else ''
            region = lang_parts[1] if len(lang_parts) > 1 else ''
            
            # Map to full names
            language_name = get_language_name(language)
            region_name = get_region_name(region)
            
            results.append({
                'url': url,
                'hreflang_count': len(hreflang_tags),
                'self_ref': 'Yes' if self_ref else 'No',
                'hreflang_tag': lang,
                'language': language_name,
                'region': region_name,
                'alt_url': href,
                'warnings': '; '.join(warnings),
                'errors': '; '.join(errors)
            })
            
        return results
        
    except Exception as e:
        return [{
            'url': url,
            'hreflang_count': 0,
            'self_ref': 'No',
            'hreflang_tag': '',
            'language': '',
            'region': '',
            'alt_url': '',
            'warnings': '',
            'errors': f'Failed to analyze: {str(e)}'
        }]

def generate_summary(results_data):
    """Generate summary report"""
    summary = "HREFLANG ANALYSIS SUMMARY\n"
    summary += "=" * 50 + "\n\n"
    
    # Basic statistics
    total_entries = len(results_data)
    unique_urls = len(set(r['url'] for r in results_data))
    languages = set(r['language'] for r in results_data if r['language'])
    regions = set(r['region'] for r in results_data if r['region'])
    
    summary += f"Total hreflang entries: {total_entries}\n"
    summary += f"Unique URLs analyzed: {unique_urls}\n"
    summary += f"Languages detected: {len(languages)}\n"
    summary += f"Regions detected: {len(regions)}\n\n"
    
    # Issues summary
    warnings = sum(1 for r in results_data if r['warnings'])
    errors = sum(1 for r in results_data if r['errors'])
    
    summary += f"Warnings found: {warnings}\n"
    summary += f"Errors found: {errors}\n\n"
    
    # Common issues
    common_warnings = {}
    common_errors = {}
    
    for result in results_data:
        for warning in result['warnings'].split('; '):
            if warning:
                common_warnings[warning] = common_warnings.get(warning, 0) + 1
        for error in result['errors'].split('; '):
            if error:
                common_errors[error] = common_errors.get(error, 0) + 1
    
    if common_warnings:
        summary += "COMMON WARNINGS:\n"
        for warning, count in common_warnings.items():
            summary += f"  • {warning}: {count} occurrences\n"
        summary += "\n"
    
    if common_errors:
        summary += "CRITICAL ERRORS:\n"
        for error, count in common_errors.items():
            summary += f"  • {error}: {count} occurrences\n"
    
    return summary

def generate_fixes(results_data):
    """Generate recommended fixes"""
    fixes = "RECOMMENDED HREFLANG FIXES\n"
    fixes += "=" * 50 + "\n\n"
    
    # Group by URL
    url_groups = {}
    for result in results_data:
        if result['url'] not in url_groups:
            url_groups[result['url']] = []
        url_groups[result['url']].append(result)
    
    for url, entries in url_groups.items():
        fixes += f"URL: {url}\n"
        fixes += "-" * 40 + "\n"
        
        # Check for missing self-reference
        self_ref = any(e['self_ref'] == 'Yes' for e in entries)
        if not self_ref:
            fixes += "❌ MISSING SELF-REFERENCE:\n"
            fixes += f"   Add: <link rel=\"alternate\" hreflang=\"x-default\" href=\"{url}\" />\n\n"
        
        # Check for missing region-independent tags
        languages_with_regions = set()
        for entry in entries:
            if '-' in entry['hreflang_tag']:
                lang = entry['hreflang_tag'].split('-')[0]
                languages_with_regions.add(lang)
        
        for lang in languages_with_regions:
            has_fallback = any(e['hreflang_tag'] == lang for e in entries)
            if not has_fallback:
                fixes += f"❌ MISSING REGION-INDEPENDENT TAG FOR {lang.upper()}:\n"
                fixes += f"   Add: <link rel=\"alternate\" hreflang=\"{lang}\" href=\"https://example.com/global/{lang}/\" />\n\n"
        
        # Specific fixes for each entry
        for entry in entries:
            if entry['warnings'] or entry['errors']:
                fixes += f"Tag: {entry['hreflang_tag']} -> {entry['alt_url']}\n"
                if entry['warnings']:
                    fixes += f"   Warnings: {entry['warnings']}\n"
                if entry['errors']:
                    fixes += f"   Errors: {entry['errors']}\n"
                fixes += "\n"
        
        fixes += "\n"
    
    return fixes

def main():
    # App title and description
    st.title("🌐 Advanced Hreflang Analysis Tool")
    st.markdown("""
    This tool analyzes hreflang tags for international SEO. 
    Hreflang tags tell search engines what language and regional URLs you have for your content, 
    helping them serve the right version to users.
    """)
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("Configuration")
        
        analysis_method = st.radio(
            "Analysis Method:",
            ["Direct URLs", "Sitemap URL"],
            help="Analyze individual URLs or extract URLs from a sitemap"
        )
        
        max_threads = st.slider(
            "Max concurrent requests:",
            min_value=1,
            max_value=10,
            value=3,
            help="Number of URLs to process simultaneously"
        )
    
    # Main content area
    tab1, tab2, tab3 = st.tabs(["Analysis", "Results", "Fixes"])
    
    with tab1:
        st.subheader("Input URLs for Analysis")
        
        if analysis_method == "Direct URLs":
            urls_input = st.text_area(
                "Enter URLs (one per line):",
                height=150,
                placeholder="https://example.com/page1\nhttps://example.com/page2"
            )
            urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
        else:
            sitemap_url = st.text_input(
                "Enter Sitemap URL:",
                placeholder="https://example.com/sitemap.xml"
            )
            urls = []
            if sitemap_url:
                with st.spinner("Extracting URLs from sitemap..."):
                    urls = extract_urls_from_sitemap(sitemap_url)
                st.info(f"Found {len(urls)} URLs in sitemap")
        
        if st.button("Start Analysis", type="primary") and urls:
            st.session_state.results_data = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Process URLs with concurrency control
            results = []
            total_urls = len(urls)
            
            for i, url in enumerate(urls):
                status_text.text(f"Processing URL {i+1} of {total_urls}: {url[:50]}...")
                result = analyze_single_url(url)
                results.extend(result)
                progress_bar.progress((i + 1) / total_urls)
                time.sleep(0.5)  # Be polite to servers
            
            st.session_state.results_data = results
            st.session_state.analysis_complete = True
            progress_bar.empty()
            status_text.text("Analysis complete!")
            st.success(f"Analyzed {total_urls} URLs, found {len(results)} hreflang entries")
    
    with tab2:
        st.subheader("Analysis Results")
        
        if st.session_state.analysis_complete and st.session_state.results_data:
            # Display summary
            summary = generate_summary(st.session_state.results_data)
            st.text_area("Summary Report", summary, height=200)
            
            # Display detailed results in a dataframe
            df = pd.DataFrame(st.session_state.results_data)
            st.dataframe(df, use_container_width=True)
            
            # Export options
            csv_data = df.to_csv(index=False)
            st.download_button(
                label="Download CSV Report",
                data=csv_data,
                file_name="hreflang_analysis.csv",
                mime="text/csv"
            )
        else:
            st.info("Run an analysis first to see results here")
    
    with tab3:
        st.subheader("Recommended Fixes")
        
        if st.session_state.analysis_complete and st.session_state.results_data:
            fixes = generate_fixes(st.session_state.results_data)
            st.text_area("Recommended Fixes", fixes, height=400)
        else:
            st.info("Run an analysis first to see recommended fixes")

if __name__ == "__main__":
    main()

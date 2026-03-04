"""
Smart Reference Formatter - Enhanced Version
With GB/T 7714-2015 strict formatting
"""

import streamlit as st
import requests
import pandas as pd
import re
import time

st.set_page_config(page_title="Reference Formatter Pro", page_icon="📚", layout="wide")

OPENALEX_API = "https://api.openalex.org/works"
CROSSREF_API = "https://api.crossref.org/works"

FORMAT_TEMPLATES = {
    "GB/T 7714-2015": "{authors}. {title}[J]. {journal}, {year}, {volume}({issue}): {pages}.",
    "APA 7th": "{authors} ({year}). {title}. {journal}, {volume}({issue}), {pages}.",
    "MLA 9th": "{authors}. \"{title}.\" {journal}, vol. {volume}, no. {issue}, {year}, pp. {pages}.",
    "Chicago": "{authors}. \"{title}.\" {journal} {volume}, no. {issue} ({year}): {pages}.",
}

def parse_input(text):
    return [line.strip() for line in text.strip().split('\n') if line.strip()]

def extract_title_v2(text):
    text = text.strip()
    text = re.sub(r'\b(19|20)\d{2}\b', '', text)
    text = re.sub(r'10\.\d{4,}/[\w\.\-/]+', '', text)
    text = re.sub(r'\s*\[.*?\]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:200]

def format_name_gb(name):
    name = name.strip()
    if not name:
        return ""
    if ',' in name:
        parts = name.split(',')
        if len(parts) == 2:
            last = parts[0].strip()
            first = parts[1].strip().upper()
            return f"{last}, {first[0] if first else ''}"
    parts = name.split()
    if len(parts) >= 2:
        last = parts[0]
        first = ''.join([p[0].upper() for p in parts[1:] if p])
        return f"{last}, {first}"
    return name

def format_authors_gb(authors):
    if not authors:
        return "[N/A]"
    names = []
    for a in authors[:10]:
        name = ""
        if a.get("author"):
            name = a["author"].get("display_name", "")
        elif a.get("display_name"):
            name = a["display_name"]
        elif a.get("family"):
            given = a.get("given", "")
            if given:
                initials = ''.join([g[0].upper() for g in given.split() if g])
                name = f"{a['family']}, {initials}"
            else:
                name = a['family']
        if name:
            names.append(format_name_gb(name))
    if not names:
        return "[N/A]"
    if len(names) > 3:
        return ", ".join(names[:3]) + ", et al"
    return ", ".join(names)

def search_openalex_v2(query):
    try:
        r = requests.get(OPENALEX_API, params={"search": query, "per-page": 15, "filter": "type:journal-article"}, timeout=20)
        if r.status_code == 200:
            return r.json().get("results", [])
    except:
        pass
    return []

def search_crossref_v2(query):
    try:
        r = requests.get(CROSSREF_API, params={"query": query, "rows": 15}, timeout=20)
        if r.status_code == 200:
            return r.json().get("message", {}).get("items", [])
    except:
        pass
    return []

def extract_metadata(result, source="openalex"):
    meta = {"title": "[N/A]", "authors": "[N/A]", "journal": "[N/A]", "year": "[N/A]", "volume": "[N/A]", "issue": "[N/A]", "pages": "[N/A]", "doi": "[N/A]", "source": source}
    
    if source == "openalex":
        if result.get("title"):
            meta["title"] = result["title"]
        if result.get("authorships"):
            meta["authors"] = format_authors_gb(result["authorships"])
        if result.get("host_venue"):
            meta["journal"] = result["host_venue"].get("display_name", "[N/A]")
        if result.get("publication_year"):
            meta["year"] = str(result["publication_year"])
        if result.get("biblio"):
            b = result["biblio"]
            meta["volume"] = b.get("volume", "[N/A]")
            meta["issue"] = b.get("issue", "[N/A]")
            fp, lp = b.get("first_page", ""), b.get("last_page", "")
            meta["pages"] = f"{fp}-{lp}" if fp and lp else (fp or "[N/A]")
        if result.get("doi"):
            meta["doi"] = result["doi"].replace("https://doi.org/", "")
    
    elif source == "crossref":
        if result.get("title"):
            meta["title"] = result["title"][0] if isinstance(result["title"], list) else result["title"]
        if result.get("author"):
            meta["authors"] = format_authors_gb(result["author"])
        if result.get("container-title"):
            meta["journal"] = result["container-title"][0]
        if result.get("published"):
            dp = result["published"].get("date-parts", [[None]])[0]
            meta["year"] = str(dp[0]) if dp and dp[0] else "[N/A]"
        meta["volume"] = result.get("volume", "[N/A]")
        meta["issue"] = result.get("issue", "[N/A]")
        meta["pages"] = result.get("page", "[N/A]")
        meta["doi"] = result.get("DOI", "[N/A]")
    
    return meta

def format_citation(meta, style, custom=""):
    def clean(v): return "" if v == "[N/A]" else str(v)
    
    if style == "GB/T 7714-2015":
        title, authors = clean(meta["title"]), clean(meta["authors"])
        journal, year = clean(meta["journal"]), clean(meta["year"])
        volume, issue = clean(meta["volume"]), clean(meta["issue"])
        pages = clean(meta["pages"])
        cit = f"{authors}. {title}[J]. {journal}, {year}, {volume}"
        if issue and issue != "[N/A]": cit += f"({issue})"
        if pages and pages != "[N/A]": cit += f": {pages}"
        cit += "."
        return re.sub(r'\s+', ' ', cit).strip()
    
    if style == "Custom" and custom:
        try:
            return custom.format(authors=clean(meta["authors"]), title=clean(meta["title"]), journal=clean(meta["journal"]), year=clean(meta["year"]), volume=clean(meta["volume"]), issue=clean(meta["issue"]), pages=clean(meta["pages"]), doi=clean(meta["doi"]))
        except:
            return "[Format Error]"
    
    if style in FORMAT_TEMPLATES:
        try:
            return FORMAT_TEMPLATES[style].format(authors=clean(meta["authors"]), title=clean(meta["title"]), journal=clean(meta["journal"]), year=clean(meta["year"]), volume=clean(meta["volume"]), issue=clean(meta["issue"]), pages=clean(meta["pages"]), doi=clean(meta["doi"]))
        except:
            return "[Format Error]"
    
    return format_citation(meta, "GB/T 7714-2015", custom)

# UI
st.title("📚 Smart Reference Formatter Pro")
st.markdown("**Enhanced: Better matching + GB/T 7714-2015 formatting**")

with st.sidebar:
    st.header("Settings")
    fmt_style = st.selectbox("Format", ["GB/T 7714-2015", "APA 7th", "MLA 9th", "Chicago", "Custom"])
    custom_tmpl = ""
    if fmt_style == "Custom":
        custom_tmpl = st.text_input("Template", "{authors}. {title}[J]. {journal}, {year}, {volume}({issue}): {pages}.")

st.header("Input")
text_input = st.text_area("Paste references (one per line)", height=150, placeholder="Deep Learning for NLP")
input_refs = parse_input(text_input) if text_input else []

if input_refs:
    st.success(f"Found {len(input_refs)} references")
    with st.expander("Preview"):
        for i, ref in enumerate(input_refs, 1):
            st.write(f"{i}. {extract_title_v2(ref)[:80]}")

if input_refs and st.button("Start Processing", type="primary", use_container_width=True):
    all_results = []
    progress_bar = st.progress(0)
    
    for idx, ref in enumerate(input_refs):
        progress_bar.progress((idx + 1) / len(input_refs))
        query = extract_title_v2(ref)
        
        results = search_openalex_v2(query)
        if not results:
            results = search_crossref_v2(query)
        
        if not results:
            all_results.append({"input": ref, "meta": None, "formatted": "[Not Found]", "status": "not_found"})
        elif len(results) == 1:
            meta = extract_metadata(results[0], "openalex" if not results[0].get("DOI") else "crossref")
            all_results.append({"input": ref, "meta": meta, "formatted": format_citation(meta, fmt_style, custom_tmpl), "status": "ok"})
        else:
            st.subheader(f"Select #{idx+1}")
            options = []
            for i, r in enumerate(results):
                t = r.get("title", "")[:50] if r.get("title") else "Unknown"
                y = str(r.get("publication_year", r.get("year", "")))
                j = (r.get("host_venue", {}).get("display_name", "") or r.get("container-title", [""])[0] if isinstance(r.get("container-title"), list) else r.get("container-title", ""))[:30]
                options.append(f"{t}... | {y} | {j}")
            
            sel = st.radio("Choose:", range(len(options)), format_func=lambda i: options[i], key=f"s{idx}")
            meta = extract_metadata(results[sel], "openalex" if not results[sel].get("DOI") else "crossref")
            all_results.append({"input": ref, "meta": meta, "formatted": format_citation(meta, fmt_style, custom_tmpl), "status": "ok"})
        
        time.sleep(0.2)
    
    st.divider()
    st.header("Results")
    
    ok_count = sum(1 for r in all_results if r["status"] == "ok")
    st.metric("Found", ok_count, delta=f"Not found: {len(all_results)-ok_count}", delta_color="inverse")
    
    table_data = []
    for r in all_results:
        if r["meta"]:
            table_data.append({"Input": r["input"][:40], "Title": r["meta"]["title"][:40], "Authors": r["meta"]["authors"][:25], "Year": r["meta"]["year"], "Status": "OK"})
        else:
            table_data.append({"Input": r["input"][:40], "Title": "[N/A]", "Authors": "[N/A]", "Year": "[N/A]", "Status": "FAIL"})
    
    st.dataframe(pd.DataFrame(table_data), use_container_width=True)
    
    st.subheader("Citations")
    for i, r in enumerate(all_results, 1):
        with st.expander(f"Ref {i}"):
            st.code(r["formatted"], language="text")
    
    txt = "\n\n".join([r["formatted"] for r in all_results])
    st.download_button("Download TXT", txt.encode("utf-8"), "references.txt", "text/plain")

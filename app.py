"""
智能文献补全助手 - 简化版
"""

import streamlit as st
import requests
import pandas as pd
import re

st.set_page_config(page_title="文献补全助手", page_icon="📚", layout="wide")

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

def extract_title(text):
    text = re.sub(r'(19|20)\d{2}', '', text)
    text = re.sub(r'10\.\d{4,}/[\w\.\-/]+', '', text)
    return text.strip()[:200]

def search_openalex(query):
    try:
        r = requests.get(OPENALEX_API, params={"search": query, "per-page": 10}, timeout=15)
        if r.status_code == 200:
            return r.json().get("results", [])
    except:
        pass
    return []

def search_crossref(query):
    try:
        r = requests.get(CROSSREF_API, params={"query": query, "rows": 10}, timeout=15)
        if r.status_code == 200:
            return r.json().get("message", {}).get("items", [])
    except:
        pass
    return []

def format_authors(authors, style="gb"):
    if not authors:
        return "[暂缺]"
    if style == "gb":
        names = []
        for a in authors[:3]:
            name = a.get("author", {}).get("display_name", "") or a.get("display_name", "") or a.get("family", "")
            if name:
                names.append(name.split()[0])
        if len(names) <= 3:
            return ", ".join(names)
        return ", ".join(names[:3]) + ", 等"
    return ", ".join([a.get("author", {}).get("display_name", "") or a.get("family", "") for a in authors[:3]])

def extract_meta(result, source="openalex"):
    meta = {"title": "[暂缺]", "authors": "[暂缺]", "journal": "[暂缺]", 
            "year": "[暂缺]", "volume": "[暂缺]", "issue": "[暂缺]", 
            "pages": "[暂缺]", "doi": "[暂缺]", "source": source}
    
    if source == "openalex":
        if result.get("title"): meta["title"] = result["title"]
        if result.get("authorships"):
            authors = [a.get("author", {}).get("display_name", "") for a in result["authorships"]]
            meta["authors"] = format_authors([{"display_name": a} for a in authors if a])
        if result.get("host_venue"):
            meta["journal"] = result["host_venue"].get("display_name", "[暂缺]")
        if result.get("publication_year"):
            meta["year"] = str(result["publication_year"])
        if result.get("biblio"):
            b = result["biblio"]
            meta["volume"] = b.get("volume", "[暂缺]")
            meta["issue"] = b.get("issue", "[暂缺]")
            fp = b.get("first_page", "")
            lp = b.get("last_page", "")
            meta["pages"] = f"{fp}-{lp}" if fp and lp else (fp or "[暂缺]")
        if result.get("doi"):
            meta["doi"] = result["doi"].replace("https://doi.org/", "")
            
    elif source == "crossref":
        if result.get("title"):
            meta["title"] = result["title"][0] if isinstance(result["title"], list) else result["title"]
        if result.get("author"):
            meta["authors"] = format_authors(result["author"])
        if result.get("container-title"):
            meta["journal"] = result["container-title"][0]
        if result.get("published"):
            dp = result["published"]["date-parts"][0]
            meta["year"] = str(dp[0]) if dp[0] else "[暂缺]"
        meta["volume"] = result.get("volume", "[暂缺]")
        meta["issue"] = result.get("issue", "[暂缺]")
        meta["pages"] = result.get("page", "[暂缺]")
        meta["doi"] = result.get("DOI", "[暂缺]")
    
    return meta

def format_citation(meta, style, custom=""):
    def clean(v): return "" if v == "[暂缺]" else str(v)
    if style == "自定义" and custom:
        tmpl = custom
    elif style in FORMAT_TEMPLATES:
        tmpl = FORMAT_TEMPLATES[style]
    else:
        tmpl = FORMAT_TEMPLATES["GB/T 7714-2015"]
    
    try:
        cit = tmpl.format(authors=clean(meta["authors"]), title=clean(meta["title"]),
                         journal=clean(meta["journal"]), year=clean(meta["year"]),
                         volume=clean(meta["volume"]), issue=clean(meta["issue"]),
                         pages=clean(meta["pages"]), doi=clean(meta["doi"]))
        return re.sub(r'\s+', ' ', cit).strip().rstrip('.') + '.'
    except:
        return "[格式化失败]"

# 主界面
st.title("📚 智能参考文献补全助手")
st.markdown("输入残缺文献信息，自动从OpenAlex/Crossref检索补全")

with st.sidebar:
    st.header("⚙️ 设置")
    fmt_style = st.selectbox("引文格式", ["GB/T 7714-2015", "APA 7th", "MLA 9th", "Chicago", "自定义"])
    custom_tmpl = ""
    if fmt_style == "自定义":
        custom_tmpl = st.text_input("格式模板", "{authors}. {title}[J]. {journal}, {year}, {volume}({issue}): {pages}.")
    export_fmt = st.selectbox("导出", ["txt", "docx"])

st.header("📝 输入文献")
input_refs = []
text_input = st.text_area("粘贴文献（每行一条）", height=150, placeholder="例如：Deep Learning for NLP")
if text_input:
    input_refs = parse_input(text_input)
    st.success(f"识别到 {len(input_refs)} 条")

if input_refs and st.button("🚀 开始处理", type="primary"):
    all_results = []
    prog = st.progress(0)
    
    for idx, ref in enumerate(input_refs):
        prog.progress((idx+1)/len(input_refs))
        title = extract_title(ref)
        
        results = search_openalex(title)
        if not results:
            results = search_crossref(title)
        
        if not results:
            all_results.append({"input": ref, "meta": {
                "title": "[暂缺]", "authors": "[暂缺]", "journal": "[暂缺]",
                "year": "[暂缺]", "volume": "[暂缺]", "issue": "[暂缺]",
                "pages": "[暂缺]", "doi": "[暂缺]", "source": "无"
            }, "status": "failed", "formatted": "[未找到]"})
        elif len(results) == 1:
            meta = extract_meta(results[0], "openalex")
            if meta["title"] == "[暂缺]":
                meta = extract_meta(results[0], "crossref")
            all_results.append({"input": ref, "meta": meta, "status": "ok", 
                             "formatted": format_citation(meta, fmt_style, custom_tmpl)})
        else:
            st.subheader(f"📋 第{idx+1}条 - 请选择")
            options = []
            for i, r in enumerate(results):
                t = r.get("title", "") or r.get("title", [""])[0]
                y = r.get("publication_year", "")
                j = r.get("host_venue", {}).get("display_name", "") or r.get("container-title", [""])[0]
                options.append(f"{t[:50]}... | {y} | {j[:30]}")
            
            sel = st.radio("选择", range(len(options)), format_func=lambda i: options[i], key=f"sel{idx}")
            meta = extract_meta(results[sel], "openalex")
            if meta["title"] == "[暂缺]":
                meta = extract_meta(results[sel], "crossref")
            all_results.append({"input": ref, "meta": meta, "status": "ok",
                             "formatted": format_citation(meta, fmt_style, custom_tmpl)})
    
    st.divider()
    st.header("📊 结果")
    
    ok = sum(1 for r in all_results if r["status"] == "ok")
    fail = len(all_results) - ok
    st.metric("处理成功", ok, delta=f"失败{fail}", delta_color="inverse")
    
    df = pd.DataFrame([{
        "原始": r["input"][:40], "标题": r["meta"]["title"][:40],
        "作者": r["meta"]["authors"][:20], "年份": r["meta"]["year"],
        "状态": "✅" if r["status"]=="ok" else "❌"
    } for r in all_results])
    st.dataframe(df, use_container_width=True)
    
    st.header("📝 格式化引文")
    for i, r in enumerate(all_results, 1):
        st.code(r["formatted"], language="text")
    
    st.header("💾 导出")
    txt = "\n\n".join([r["formatted"] for r in all_results])
    st.download_button("📥 下载TXT", txt.encode("utf-8"), "参考文献.txt", "text/plain")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import time
from datetime import datetime, timedelta
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

BASE_URL = "https://cn.govopendata.com/xinwenlianbo"
TARGET_DATE = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
if os.getenv("XWLB_DATE"):
    TARGET_DATE = os.getenv("XWLB_DATE")

def fetch_news(date_str: str) -> list:
    url = f"{BASE_URL}/{date_str}/"
    print(f"🌐 正在抓取: {url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    session.mount('http://', HTTPAdapter(max_retries=retries))

    try:
        resp = session.get(url, headers=headers, timeout=30)
        resp.encoding = "utf-8"
        print(f"✅ 状态码: {resp.status_code}")
        print(f"📄 内容长度: {len(resp.text)}")
        print(f"📝 内容预览: {resp.text[:200]}...")
        
        if resp.status_code != 200:
            print(f"❌ HTTP 错误: {resp.status_code}")
            return []
        if len(resp.text) < 500:
            print("⚠️ 内容过短，可能被拦截或页面异常")
            return []
        
        # 你的解析逻辑（保持你本地能跑的代码）
        # 以下是你原本的解析代码，请保留你自己的实现
        # 我给出一个通用示例，但你要替换成你自己的
        # ----
        # 此处粘贴你本地能正常工作的解析逻辑
        # ----
        
        # 示例（你替换成你的）：
        # 假设你从 main 标签提取
        import re
        main_pattern = r'<main[^>]*id="main-content"[^>]*>(.*?)</main>'
        match = re.search(main_pattern, resp.text, re.S)
        if not match:
            print("⚠️ 未找到 main-content 区域，尝试其他解析")
            # 退而求其次提取 body 文本
            body_text = re.sub(r'<[^>]+>', ' ', resp.text)
            body_text = re.sub(r'\s+', ' ', body_text).strip()
            # 按段落分割
            lines = [x.strip() for x in body_text.split('。') if len(x.strip()) > 20]
            news_list = []
            for line in lines:
                if len(line) > 30:
                    title = line[:50] + ("..." if len(line)>50 else "")
                    news_list.append({"title": title, "content": line})
            return news_list

        main_content = match.group(1)
        # 清理标签
        main_content = re.sub(r'<script[^>]*>.*?</script>', '', main_content, flags=re.S)
        main_content = re.sub(r'<style[^>]*>.*?</style>', '', main_content, flags=re.S)
        main_content = re.sub(r'<[^>]+>', ' ', main_content)
        main_content = re.sub(r'\s+', ' ', main_content).strip()
        
        # 按 "## " 分割（根据你网站的实际情况）
        items = re.split(r'##\s+', main_content)
        news_list = []
        for item in items:
            item = item.strip()
            if not item or len(item) < 20:
                continue
            title_match = re.match(r'^([^。！？\n]{5,60}[。！？]?)', item)
            if title_match:
                title = title_match.group(1).strip()
            else:
                title = item[:50] + ("..." if len(item)>50 else "")
            news_list.append({"title": title, "content": item})
        
        print(f"✅ 成功提取 {len(news_list)} 条新闻")
        return news_list
        
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return []

def generate_rss(news_list: list, date_str: str) -> str:
    rss = Element("rss", version="2.0")
    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = f"新闻联播 文字版 {date_str}"
    SubElement(channel, "link").text = f"{BASE_URL}/{date_str}/"
    SubElement(channel, "description").text = f"{date_str} 新闻联播文字稿，共 {len(news_list)} 条新闻"
    SubElement(channel, "pubDate").text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0800")
    
    for item in news_list:
        elem = SubElement(channel, "item")
        SubElement(elem, "title").text = item["title"]
        SubElement(elem, "link").text = f"{BASE_URL}/{date_str}/"
        SubElement(elem, "description").text = item["content"]
    
    rough = tostring(rss, "utf-8")
    return minidom.parseString(rough).toprettyxml(indent="  ")

def main():
    print(f"📅 目标日期: {TARGET_DATE}")
    news = fetch_news(TARGET_DATE)
    if not news:
        print("⚠️ 未获取到新闻，生成占位提示")
        news = [{"title": f"【提示】{TARGET_DATE} 新闻联播暂无数据", 
                 "content": f"请稍后重试，或访问 {BASE_URL}/{TARGET_DATE}/ 查看"}]
    rss_content = generate_rss(news, TARGET_DATE)
    with open("xwlb.xml", "w", encoding="utf-8") as f:
        f.write(rss_content)
    print(f"✅ RSS 已生成，共 {len(news)} 条新闻")

if __name__ == "__main__":
    main()

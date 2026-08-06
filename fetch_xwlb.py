#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
from datetime import datetime, timedelta
import cloudscraper
from xml.dom import minidom
from bs4 import BeautifulSoup

BASE_URL = "https://cn.govopendata.com/xinwenlianbo"
TARGET_DATE = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
if os.getenv("XWLB_DATE"):
    TARGET_DATE = os.getenv("XWLB_DATE")


def fetch_news(date_str: str) -> list:
    """抓取指定日期的新闻联播文字稿"""
    url = f"{BASE_URL}/{date_str}/"
    print(f"🌐 正在抓取: {url}")

    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3",
    }

    try:
        resp = scraper.get(url, headers=headers, timeout=30)
        resp.encoding = "utf-8"
        print(f"✅ 状态码: {resp.status_code}")

        if resp.status_code != 200:
            return []
        if "Just a moment" in resp.text or "Cloudflare" in resp.text:
            print("⚠️ Cloudflare 拦截")
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        main = soup.find('main', id='main-content')
        if not main:
            print("⚠️ 未找到 main-content")
            return []

        articles = main.find_all('article', class_='content-section')
        news_list = []
        for article in articles:
            heading = article.find('h2', class_='content-heading')
            if not heading:
                continue
            title = heading.get_text(strip=True)

            body_div = article.find('div', class_='content-body')
            if not body_div:
                continue

            # 保留段落
            paragraphs = body_div.find_all('p')
            if paragraphs:
                content = '\n\n'.join(p.get_text(strip=True) for p in paragraphs)
            else:
                content = body_div.get_text(strip=True)

            if not title or not content:
                continue

            news_list.append({
                "title": title,
                "content": content
            })

        print(f"✅ 提取到 {len(news_list)} 条新闻")
        return news_list

    except Exception as e:
        print(f"❌ 错误: {e}")
        return []


def generate_rss(news_list: list, date_str: str) -> str:
    """生成 RSS，每个 item 有独立链接"""
    doc = minidom.Document()
    rss = doc.createElement("rss")
    rss.setAttribute("version", "2.0")
    doc.appendChild(rss)

    channel = doc.createElement("channel")
    rss.appendChild(channel)

    # 频道信息
    def add_text(parent, tag, text):
        elem = doc.createElement(tag)
        elem.appendChild(doc.createTextNode(text))
        parent.appendChild(elem)

    add_text(channel, "title", f"新闻联播 文字版 {date_str}")
    add_text(channel, "link", f"{BASE_URL}/{date_str}/")
    add_text(channel, "description", f"{date_str} 新闻联播，共 {len(news_list)} 条")
    add_text(channel, "pubDate", datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0800"))

    # 每个条目
    for idx, item in enumerate(news_list, start=1):
        item_elem = doc.createElement("item")
        channel.appendChild(item_elem)

        # 标题
        add_text(item_elem, "title", item["title"])

        # 唯一链接：添加查询参数 p=idx
        unique_link = f"{BASE_URL}/{date_str}/?p={idx}"
        add_text(item_elem, "link", unique_link)

        # 唯一 GUID
        guid = doc.createElement("guid")
        guid.setAttribute("isPermaLink", "false")
        guid.appendChild(doc.createTextNode(f"{item['title']}-{date_str}-{idx}"))
        item_elem.appendChild(guid)

        # 发布日期（使用当天日期）
        pub_date_str = datetime.strptime(date_str, "%Y%m%d").strftime("%a, %d %b %Y 19:00:00 +0800")
        add_text(item_elem, "pubDate", pub_date_str)

        # 正文：将段落用 <br/> 分割，放在 CDATA 中
        # 先按空行分割，保留空行
        paragraphs = [p.strip() for p in item["content"].split('\n\n') if p.strip()]
        if not paragraphs:
            paragraphs = [item["content"].strip()]
        # 用 <br/> 连接段落
        content_html = '<br/>'.join(paragraphs)

        desc_elem = doc.createElement("description")
        cdata = doc.createCDATASection(content_html)
        desc_elem.appendChild(cdata)
        item_elem.appendChild(desc_elem)

    return doc.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


def main():
    print(f"📅 目标日期: {TARGET_DATE}")
    news = fetch_news(TARGET_DATE)
    if not news:
        print("⚠️ 未获取到新闻，生成占位")
        news = [{
            "title": f"【提示】{TARGET_DATE} 新闻联播暂无数据",
            "content": f"请稍后重试，或访问 {BASE_URL}/{TARGET_DATE}/ 查看"
        }]

    rss_content = generate_rss(news, TARGET_DATE)
    with open("xwlb.xml", "w", encoding="utf-8") as f:
        f.write(rss_content)
    print(f"✅ RSS 已生成，共 {len(news)} 条新闻")


if __name__ == "__main__":
    main()

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
    """抓取指定日期的新闻联播文字稿，返回新闻列表（每条新闻为 dict）"""
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
    """
    生成 RSS，只包含一个 <item>，内部包含所有新闻。
    每条新闻：标题用 <strong> 加粗，正文用 <p> 分段，新闻之间用 <hr> 分隔。
    """
    doc = minidom.Document()

    rss = doc.createElement("rss")
    rss.setAttribute("version", "2.0")
    doc.appendChild(rss)

    channel = doc.createElement("channel")
    rss.appendChild(channel)

    # ---- 频道信息 ----
    def add_text_node(parent, tag, text):
        elem = doc.createElement(tag)
        text_node = doc.createTextNode(text)
        elem.appendChild(text_node)
        parent.appendChild(elem)

    # 标题使用日期
    title_str = f"新闻联播 文字版 {date_str}"
    add_text_node(channel, "title", title_str)
    add_text_node(channel, "link", f"{BASE_URL}/{date_str}/")
    add_text_node(channel, "description", f"{date_str} 新闻联播文字稿，共 {len(news_list)} 条")
    add_text_node(channel, "pubDate", datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0800"))

    # ---- 唯一的一个 item ----
    item_elem = doc.createElement("item")
    channel.appendChild(item_elem)

    # 标题（与频道标题一致）
    add_text_node(item_elem, "title", title_str)

    # 链接（指向当天页面）
    add_text_node(item_elem, "link", f"{BASE_URL}/{date_str}/")

    # guid
    guid_elem = doc.createElement("guid")
    guid_elem.setAttribute("isPermaLink", "false")
    guid_elem.appendChild(doc.createTextNode(f"xwlb-{date_str}"))
    item_elem.appendChild(guid_elem)

    # pubDate（使用当天日期，时间固定为19:00）
    pub_date_elem = doc.createElement("pubDate")
    pub_date_elem.appendChild(doc.createTextNode(
        datetime.strptime(date_str, "%Y%m%d").strftime("%a, %d %b %Y 19:00:00 +0800")
    ))
    item_elem.appendChild(pub_date_elem)

    # ---- 构建正文：将所有新闻合并成一个 HTML 块 ----
    html_parts = []
    for idx, news in enumerate(news_list):
        # 标题：加粗
        html_parts.append(f"<strong>{news['title']}</strong>")
        # 正文：按空行分割为段落，用 <p> 包裹
        paragraphs = [p.strip() for p in news['content'].split('\n\n') if p.strip()]
        if not paragraphs:
            paragraphs = [news['content'].strip()]
        for para in paragraphs:
            html_parts.append(f"<p>{para}</p>")
        # 新闻之间加分隔线（最后一条不加）
        if idx < len(news_list) - 1:
            html_parts.append("<hr>")

    full_html = ''.join(html_parts)

    # 放入 description 的 CDATA
    desc_elem = doc.createElement("description")
    cdata = doc.createCDATASection(full_html)
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
    print(f"✅ RSS 已生成，共 {len(news)} 条新闻（合并为单条目）")


if __name__ == "__main__":
    main()

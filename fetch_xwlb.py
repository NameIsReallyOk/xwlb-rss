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
    """抓取指定日期的新闻联播文字稿，使用 BeautifulSoup 精准提取"""
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
        print(f"📄 内容长度: {len(resp.text)}")

        if resp.status_code != 200:
            print(f"❌ HTTP 错误: {resp.status_code}")
            return []
        if "Just a moment" in resp.text or "Cloudflare" in resp.text:
            print("⚠️ 页面仍包含 Cloudflare 验证")
            return []

        # 使用 BeautifulSoup 解析
        soup = BeautifulSoup(resp.text, 'html.parser')

        # 定位 main-content
        main = soup.find('main', id='main-content')
        if not main:
            print("⚠️ 未找到 main-content")
            return []

        # 找到所有 article.content-section
        articles = main.find_all('article', class_='content-section')
        print(f"📰 找到 {len(articles)} 个新闻条目")

        news_list = []
        for article in articles:
            # 提取标题：h2.content-heading
            heading = article.find('h2', class_='content-heading')
            if not heading:
                continue
            title = heading.get_text(strip=True)

            # 提取内容：div.content-body 下的所有 p 标签
            body_div = article.find('div', class_='content-body')
            if not body_div:
                continue

            # 提取所有段落文本，用换行连接
            paragraphs = body_div.find_all('p')
            if paragraphs:
                content = '\n\n'.join(p.get_text(strip=True) for p in paragraphs)
            else:
                # 如果没有 p 标签，直接取文本
                content = body_div.get_text(strip=True)

            if not title or not content:
                continue

            news_list.append({
                "title": title,
                "content": content
            })

        print(f"✅ 成功提取 {len(news_list)} 条新闻")
        return news_list

    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return []


def generate_rss(news_list: list, date_str: str) -> str:
    """生成 RSS XML，每条新闻一个 item"""
    doc = minidom.Document()
    rss = doc.createElement("rss")
    rss.setAttribute("version", "2.0")
    doc.appendChild(rss)

    channel = doc.createElement("channel")
    rss.appendChild(channel)

    title_elem = doc.createElement("title")
    title_elem.appendChild(doc.createTextNode(f"新闻联播 文字版 {date_str}"))
    channel.appendChild(title_elem)

    link_elem = doc.createElement("link")
    link_elem.appendChild(doc.createTextNode(f"{BASE_URL}/{date_str}/"))
    channel.appendChild(link_elem)

    desc_elem = doc.createElement("description")
    desc_elem.appendChild(doc.createTextNode(f"{date_str} 新闻联播，共 {len(news_list)} 条"))
    channel.appendChild(desc_elem)

    pub_date = doc.createElement("pubDate")
    pub_date.appendChild(doc.createTextNode(datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0800")))
    channel.appendChild(pub_date)

    for item in news_list:
        item_elem = doc.createElement("item")
        channel.appendChild(item_elem)

        title = doc.createElement("title")
        title.appendChild(doc.createTextNode(item["title"]))
        item_elem.appendChild(title)

        link = doc.createElement("link")
        link.appendChild(doc.createTextNode(f"{BASE_URL}/{date_str}/"))
        item_elem.appendChild(link)

        desc = doc.createElement("description")
        cdata = doc.createCDATASection(item["content"])
        desc.appendChild(cdata)
        item_elem.appendChild(desc)

    return doc.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


def main():
    print(f"📅 目标日期: {TARGET_DATE}")
    news = fetch_news(TARGET_DATE)
    if not news:
        print("⚠️ 未获取到新闻，生成占位提示")
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

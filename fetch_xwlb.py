#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
from datetime import datetime, timedelta
import cloudscraper
from xml.dom import minidom

BASE_URL = "https://cn.govopendata.com/xinwenlianbo"
TARGET_DATE = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
if os.getenv("XWLB_DATE"):
    TARGET_DATE = os.getenv("XWLB_DATE")


def fetch_news(date_str: str) -> list:
    """抓取指定日期的新闻联播文字稿，返回新闻列表"""
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
            print("⚠️ 页面仍包含 Cloudflare 验证，尝试失败")
            return []

        html = resp.text

        # 提取 <main id="main-content">
        main_pattern = r'<main[^>]*id="main-content"[^>]*>(.*?)</main>'
        main_match = re.search(main_pattern, html, re.S)
        if not main_match:
            print("⚠️ 未找到 main-content，尝试备用解析")
            # 备用：提取 body 文本并清理
            body_text = re.sub(r'<[^>]+>', ' ', html)
            body_text = re.sub(r'\s+', ' ', body_text).strip()
            # 尝试找到正文起始
            start = body_text.find("党建")
            if start != -1:
                body_text = body_text[start:]
            if len(body_text) > 100:
                return [{"title": f"新闻联播 文字版 {date_str}", "content": body_text}]
            else:
                return []

        main_html = main_match.group(1)

        # 清理 <script> 和 <style>
        main_html = re.sub(r'<script[^>]*>.*?</script>', '', main_html, flags=re.S)
        main_html = re.sub(r'<style[^>]*>.*?</style>', '', main_html, flags=re.S)

        # 将 <br> 和 </p> 转为换行符
        main_html = re.sub(r'<br\s*/?>', '\n', main_html, flags=re.I)
        main_html = re.sub(r'</p>', '\n', main_html, flags=re.I)
        # 移除其他 HTML 标签，保留文本
        main_html = re.sub(r'<[^>]+>', ' ', main_html)

        # 清理多余空白，但保留换行
        lines = main_html.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line:
                cleaned_lines.append(line)
        text = '\n'.join(cleaned_lines)

        # 去除开头的导航文字（“首页 新闻联播 ... 下一天”）
        nav_pattern = r'^首页\s+新闻联播.*?下一天\s+\d{4}-\d{2}-\d{2}\s*'
        text = re.sub(nav_pattern, '', text, flags=re.S)

        # 去掉末尾可能的版权信息（如“©2026...”）
        footer_pattern = r'\s*©\s*\d{4}.*$'
        text = re.sub(footer_pattern, '', text, flags=re.S)

        # 按“【”分割新闻条目
        # 每个条目以“【”开头，直到下一个“【”或结尾
        raw_items = re.split(r'(?=【)', text)
        news_list = []
        for raw in raw_items:
            raw = raw.strip()
            if not raw or len(raw) < 20:
                continue
            # 提取标题：从“【”到第一个“】”
            title_match = re.match(r'^【([^】]+)】', raw)
            if title_match:
                title = title_match.group(1).strip()
                # 正文是标题之后的部分
                content = raw[len(title_match.group(0)):].strip()
            else:
                # 如果没有“【”，取前50字符作为标题
                title = raw[:50] + ("..." if len(raw) > 50 else "")
                content = raw

            # 如果正文为空，用原标题代替
            if not content:
                content = raw
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
    """生成 RSS XML，每个新闻作为一个 item"""
    doc = minidom.Document()
    rss = doc.createElement("rss")
    rss.setAttribute("version", "2.0")
    doc.appendChild(rss)

    channel = doc.createElement("channel")
    rss.appendChild(channel)

    # 频道信息
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

    # 逐条生成 item
    for item in news_list:
        item_elem = doc.createElement("item")
        channel.appendChild(item_elem)

        # 标题
        title = doc.createElement("title")
        title.appendChild(doc.createTextNode(item["title"]))
        item_elem.appendChild(title)

        # 链接（指向当天原文，所有 item 共用）
        link = doc.createElement("link")
        link.appendChild(doc.createTextNode(f"{BASE_URL}/{date_str}/"))
        item_elem.appendChild(link)

        # 正文（CDATA 保留换行）
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

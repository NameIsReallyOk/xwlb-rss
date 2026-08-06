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
    """抓取指定日期的新闻联播文字稿，返回单个条目的列表"""
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

        # 1. 提取 <main id="main-content"> 区域
        main_pattern = r'<main[^>]*id="main-content"[^>]*>(.*?)</main>'
        main_match = re.search(main_pattern, html, re.S)
        if not main_match:
            print("⚠️ 未找到 main-content，尝试备用解析（body）")
            # 备用：提取 body 文本，但尽量去除导航
            body_text = re.sub(r'<[^>]+>', ' ', html)
            body_text = re.sub(r'\s+', ' ', body_text).strip()
            # 尝试找到正文起始（通常跳过开头导航）
            start = body_text.find("党建")
            if start != -1:
                body_text = body_text[start:]
            if len(body_text) > 100:
                return [{"title": f"新闻联播 文字版 {date_str}", "content": body_text}]
            else:
                return []

        main_html = main_match.group(1)

        # 2. 清理 <script> 和 <style>
        main_html = re.sub(r'<script[^>]*>.*?</script>', '', main_html, flags=re.S)
        main_html = re.sub(r'<style[^>]*>.*?</style>', '', main_html, flags=re.S)

        # 3. 将 <br> 和 </p> 转为换行符（保留段落）
        main_html = re.sub(r'<br\s*/?>', '\n', main_html, flags=re.I)
        main_html = re.sub(r'</p>', '\n', main_html, flags=re.I)
        # 移除其他所有标签（保留文本）
        main_html = re.sub(r'<[^>]+>', ' ', main_html)

        # 4. 清理多余空白，但保留换行符
        lines = main_html.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line:
                cleaned_lines.append(line)
        text = '\n'.join(cleaned_lines)

        # 5. 去除开头的导航文字（“首页 新闻联播 ... 下一天”）
        # 匹配类似 “首页 新闻联播 2026 年 8 月 5 日 ... 下一天 2026-08-04” 直到下一天之后
        nav_pattern = r'^首页\s+新闻联播.*?下一天\s+\d{4}-\d{2}-\d{2}\s*'
        text = re.sub(nav_pattern, '', text, flags=re.S)

        # 如果清理后文本太短，可能解析失败
        if len(text) < 50:
            print("⚠️ 解析后的正文过短，可能失败")
            return []

        print(f"✅ 成功提取正文，长度 {len(text)}")
        # 作为单条目返回
        news_list = [{
            "title": f"新闻联播 文字版 {date_str}",
            "content": text
        }]
        return news_list

    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return []


def generate_rss(news_list: list, date_str: str) -> str:
    """生成 RSS XML，使用 CDATA 保留正文换行"""
    doc = minidom.Document()
    rss = doc.createElement("rss")
    rss.setAttribute("version", "2.0")
    doc.appendChild(rss)

    channel = doc.createElement("channel")
    rss.appendChild(channel)

    # 标题
    title_elem = doc.createElement("title")
    title_elem.appendChild(doc.createTextNode(f"新闻联播 文字版 {date_str}"))
    channel.appendChild(title_elem)

    # 链接
    link_elem = doc.createElement("link")
    link_elem.appendChild(doc.createTextNode(f"{BASE_URL}/{date_str}/"))
    channel.appendChild(link_elem)

    # 描述
    desc_elem = doc.createElement("description")
    desc_elem.appendChild(doc.createTextNode(f"{date_str} 新闻联播文字稿"))
    channel.appendChild(desc_elem)

    # 发布日期
    pub_date = doc.createElement("pubDate")
    pub_date.appendChild(doc.createTextNode(datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0800")))
    channel.appendChild(pub_date)

    for item in news_list:
        item_elem = doc.createElement("item")
        channel.appendChild(item_elem)

        # 标题
        title = doc.createElement("title")
        title.appendChild(doc.createTextNode(item["title"]))
        item_elem.appendChild(title)

        # 链接（原文）
        link = doc.createElement("link")
        link.appendChild(doc.createTextNode(f"{BASE_URL}/{date_str}/"))
        item_elem.appendChild(link)

        # 描述 – 使用 CDATA 保留换行
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

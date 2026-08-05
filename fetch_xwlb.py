#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新闻联播文字稿爬虫 - 抓取 cn.govopendata.com 并生成 RSS
"""

import os
import re
import requests
from datetime import datetime, timedelta
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

# ========== 配置 ==========
BASE_URL = "https://cn.govopendata.com/xinwenlianbo"
# 抓取哪一天：默认昨天（因为当天新闻通常次日凌晨才完整）
TARGET_DATE = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
# 如果通过环境变量指定日期，则使用环境变量
if os.getenv("XWLB_DATE"):
    TARGET_DATE = os.getenv("XWLB_DATE")


# ==========================

def fetch_news(date_str: str) -> list:
    """
    抓取指定日期的新闻联播文字稿
    返回: [{"title": "...", "content": "..."}, ...]
    """
    url = f"{BASE_URL}/{date_str}/"
    print(f"正在抓取: {url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.encoding = "utf-8"
        if resp.status_code != 200:
            print(f"❌ 请求失败: HTTP {resp.status_code}")
            return []
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return []

    html = resp.text

    # 方法1: 从页面中提取纯文本内容（main 区域）
    # 查找 <main id="main-content"> 到 </main> 之间的内容
    main_pattern = r'<main[^>]*id="main-content"[^>]*>(.*?)</main>'
    main_match = re.search(main_pattern, html, re.S)
    if not main_match:
        print("❌ 未找到 main-content 区域")
        return []

    main_content = main_match.group(1)

    # 移除 script 和 style 标签
    main_content = re.sub(r'<script[^>]*>.*?</script>', '', main_content, flags=re.S)
    main_content = re.sub(r'<style[^>]*>.*?</style>', '', main_content, flags=re.S)
    # 移除 HTML 标签，保留文本
    main_content = re.sub(r'<[^>]+>', ' ', main_content)
    # 清理空白字符
    main_content = re.sub(r'\s+', ' ', main_content).strip()

    # 按 "## " 分割新闻条目（网站使用 ## 作为标题标记）
    # 但第一条新闻的标题格式是 "## 〖...〗"，后续可能是 "## 蔡奇看望..."
    raw_items = re.split(r'##\s+', main_content)

    news_list = []
    for item in raw_items:
        item = item.strip()
        if not item or len(item) < 10:
            continue
        # 提取标题（第一个句子，以句号、问号、感叹号或换行为界）
        title_match = re.match(r'^([^。！？\n]{5,60}[。！？]?)', item)
        if title_match:
            title = title_match.group(1).strip()
            # 如果标题太长，截断
            if len(title) > 80:
                title = title[:80] + "..."
        else:
            # 取前30个字符作为标题
            title = item[:30] + "..." if len(item) > 30 else item

        # 内容就是整段文字
        content = item
        news_list.append({
            "title": title,
            "content": content
        })

    print(f"✅ 成功提取 {len(news_list)} 条新闻")
    return news_list


def generate_rss(news_list: list, date_str: str) -> str:
    """
    生成 RSS XML
    """
    rss = Element("rss", version="2.0")
    channel = SubElement(rss, "channel")

    title = SubElement(channel, "title")
    title.text = f"新闻联播 文字版 {date_str}"

    link = SubElement(channel, "link")
    link.text = f"{BASE_URL}/{date_str}/"

    desc = SubElement(channel, "description")
    desc.text = f"{date_str} 新闻联播文字稿，共 {len(news_list)} 条新闻"

    pub_date = SubElement(channel, "pubDate")
    pub_date.text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0800")

    for item in news_list:
        item_elem = SubElement(channel, "item")

        title_elem = SubElement(item_elem, "title")
        title_elem.text = item["title"]

        link_elem = SubElement(item_elem, "link")
        link_elem.text = f"{BASE_URL}/{date_str}/"

        desc_elem = SubElement(item_elem, "description")
        # 内容中可能包含 "##"，替换为换行
        content = item["content"].replace("## ", "\n")
        desc_elem.text = content

    # 格式化 XML
    rough_string = tostring(rss, "utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def main():
    print(f"📅 目标日期: {TARGET_DATE}")

    # 抓取新闻
    news = fetch_news(TARGET_DATE)
    if not news:
        print("⚠️ 未获取到新闻，可能网站结构已变化")
        # 生成一个占位 RSS，避免订阅器报错
        news = [{
            "title": f"【提示】{TARGET_DATE} 新闻联播暂无数据",
            "content": f"请稍后重试，或访问 {BASE_URL}/{TARGET_DATE}/ 查看"
        }]

    # 生成 RSS
    rss_content = generate_rss(news, TARGET_DATE)

    # 写入文件
    output_file = "xwlb.xml"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(rss_content)

    print(f"✅ RSS 已生成: {output_file}")
    print(f"📊 共 {len(news)} 条新闻")


if __name__ == "__main__":
    main()


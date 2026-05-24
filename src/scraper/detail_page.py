import re
import time
import random

from selenium import webdriver


def scrape_job_detail(
    driver: webdriver.Remote,
    url: str,
    keyword: str,
    delay_range: tuple[float, float] = (2.0, 4.0),
) -> dict:
    driver.get(url)
    time.sleep(random.uniform(*delay_range))

    data = driver.execute_script("""
        const root = document.querySelector('#job-detail');
        if (!root) return {};

        const sectionH2s = Array.from(root.querySelectorAll('h2.section-title'));

        function getSectionEls(title) {
            const h2 = sectionH2s.find(h => h.textContent.trim() === title);
            if (!h2) return [];
            const next = sectionH2s[sectionH2s.indexOf(h2) + 1] || null;
            const els = [];
            let el = h2.nextElementSibling;
            while (el && el !== next) { els.push(el); el = el.nextElementSibling; }
            return els;
        }

        const titleEl = root.querySelector('h1.job-title');

        const tags = Array.from(root.querySelectorAll('span.tag'))
            .map(s => s.textContent.trim()).filter(Boolean);

        const sal = root.querySelector('span.salary');
        const salUnit = root.querySelector('span.salary-unit');
        const salary = sal
            ? sal.textContent.trim() + (salUnit ? salUnit.textContent.trim() : '')
            : '';

        const skills = getSectionEls('開発環境・言語').flatMap(el => {
            if (el.className && el.className.includes('skill-logo')) {
                const sp = el.querySelector('span');
                return [(sp || el).textContent.trim()];
            }
            if (el.tagName === 'SPAN') return [el.textContent.trim()];
            return [];
        }).filter(Boolean);

        const jobContent = getSectionEls('職務内容')
            .filter(el => el.tagName === 'P')
            .map(el => el.textContent.trim())
            .join('\\n');

        const required = [], preferred = [];
        let cur = null;
        for (const el of getSectionEls('必須スキル・歓迎スキル')) {
            if (el.tagName === 'H4') {
                cur = el.textContent.includes('必須') ? 'req'
                    : el.textContent.includes('歓迎') ? 'pref' : null;
            } else if ((el.tagName === 'UL' || el.tagName === 'OL') && cur) {
                const items = Array.from(el.querySelectorAll('li'))
                    .map(li => li.textContent.trim()).filter(Boolean);
                (cur === 'req' ? required : preferred).push(...items);
            }
        }

        const detailMap = {};
        root.querySelectorAll('.detail-label').forEach(label => {
            const val = label.nextElementSibling;
            if (val && val.classList.contains('detail-value')) {
                detailMap[label.textContent.trim()] = val.textContent.trim();
            }
        });

        return { titleEl: titleEl ? titleEl.textContent.trim() : '',
                 tags, salary, skills, jobContent, required, preferred, detailMap };
    """)

    job_content: str = data.get("jobContent", "")

    return {
        "検索キーワード": keyword,
        "案件URL": url,
        "案件タイトル": data.get("titleEl", ""),
        "特徴タグ": "/".join(data.get("tags", [])),
        "単価": data.get("salary", ""),
        "使用技術": "/".join(data.get("skills", [])),
        "職務内容": job_content,
        "必須スキル": "/".join(data.get("required", [])),
        "歓迎スキル": "/".join(data.get("preferred", [])),
        "職種": data.get("detailMap", {}).get("職種", ""),
        "契約形態": data.get("detailMap", {}).get("契約形態", ""),
        "勤務地": data.get("detailMap", {}).get("勤務地・最寄り駅", ""),
        "エージェント名": data.get("detailMap", {}).get("エージェント名", ""),
        "稼働日数": _extract_working_days(job_content),
    }


def _extract_working_days(text: str) -> str:
    match = re.search(r'週\d+(?:[〜～]\d+)?日(?:[（(][^）)]+[）)])?', text)
    return match.group().strip() if match else ""

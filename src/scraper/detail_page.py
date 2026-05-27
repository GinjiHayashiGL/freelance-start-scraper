"""案件詳細ページのスクレイピング。JavaScript で DOM を一括取得して辞書に変換する。"""

import logging
import time
import random

from selenium import webdriver

logger = logging.getLogger(__name__)


def scrape_job_detail(
    driver: webdriver.Remote,
    url: str,
    keyword: str,
    delay_range: tuple[float, float] = (2.0, 4.0),
) -> dict:
    """案件詳細ページを取得し、DETAIL_FIELDS に対応した辞書を返す。

    JS を 1 回実行して全フィールドを取得することで、複数の find_element 呼び出しを避ける。
    取得した文字列はすべて _normalize() で空白を正規化する（CSV の行分割防止）。
    """
    driver.get(url)
    time.sleep(random.uniform(*delay_range))

    data = driver.execute_script("""
        // job-header: タイトル・単価
        const header = document.querySelector('div.job-header');
        const titleEl = header ? header.querySelector('h1.job-title') : null;
        const salaryEl = header ? header.querySelector('span.salary') : null;
        const salaryUnitEl = header ? header.querySelector('span.salary-unit') : null;
        const title = titleEl ? titleEl.textContent : '';
        const salary = salaryEl
            ? salaryEl.textContent + (salaryUnitEl ? salaryUnitEl.textContent : '')
            : '';

        // main-content: スキル・業務内容・必須/歓迎スキル・エージェントコメント
        const main = document.querySelector('div.main-content');

        const skills = main
            ? Array.from(main.querySelectorAll('div.tech-stack a.tech-item span'))
                .map(s => s.textContent.trim()).filter(Boolean)
            : [];

        const descEl = main ? main.querySelector('div.description') : null;
        const description = descEl ? descEl.textContent : '';

        const required = [], preferred = [];
        if (main) {
            for (const cat of main.querySelectorAll('div.skills-container div.skill-category')) {
                const h4 = cat.querySelector('h4');
                if (!h4) continue;
                const items = Array.from(cat.querySelectorAll('ul.skill-list li'))
                    .map(li => li.textContent.trim()).filter(Boolean);
                if (h4.textContent.includes('必須')) required.push(...items);
                else if (h4.textContent.includes('歓迎')) preferred.push(...items);
            }
        }

        const agentCommentEl = main ? main.querySelector('div.agent-info div.agent-comment') : null;
        const agentComment = agentCommentEl ? agentCommentEl.textContent : '';

        // section: h2.section-title の見出しでセクションを特定
        // 案件詳細・エージェント情報: detail-label/value ペアを収集
        function getSectionDetails(sectionTitle) {
            const map = {};
            for (const section of document.querySelectorAll('div.section')) {
                const h2 = section.querySelector('h2.section-title');
                if (!h2 || h2.textContent.trim() !== sectionTitle) continue;
                section.querySelectorAll('div.detail-label').forEach(label => {
                    const val = label.nextElementSibling;
                    if (val && val.classList.contains('detail-value')) {
                        map[label.textContent.trim()] = val.textContent;
                    }
                });
                break;
            }
            return map;
        }

        // その他情報: div.description の本文を取得
        function getSectionDescription(sectionTitle) {
            for (const section of document.querySelectorAll('div.section')) {
                const h2 = section.querySelector('h2.section-title');
                if (!h2 || h2.textContent.trim() !== sectionTitle) continue;
                const desc = section.querySelector('div.description');
                return desc ? desc.textContent : '';
            }
            return '';
        }

        const jobDetails = getSectionDetails('案件詳細');
        const agentDetails = getSectionDetails('エージェント情報');
        const otherInfo = getSectionDescription('その他情報');

        return { title, salary, skills, description, required, preferred,
                 agentComment, jobDetails, agentDetails, otherInfo };
    """)

    return {
        "検索キーワード": keyword,
        "案件URL": url,
        "案件タイトル": _normalize(data.get("title", "")),
        "単価": _normalize(data.get("salary", "")),
        "使用技術": "/".join(_normalize(s) for s in data.get("skills", [])),
        "業務内容": _normalize(data.get("description", "")),
        "必須スキル": "/".join(_normalize(s) for s in data.get("required", [])),
        "歓迎スキル": "/".join(_normalize(s) for s in data.get("preferred", [])),
        "エージェントコメント": _normalize(data.get("agentComment", "")),
        "職種": _normalize(data.get("jobDetails", {}).get("職種", "")),
        "契約期間": _normalize(data.get("jobDetails", {}).get("契約期間", "")),
        "稼働時間": _normalize(data.get("jobDetails", {}).get("精算条件", "")),
        "勤務地・最寄り駅": _normalize(data.get("jobDetails", {}).get("勤務地・最寄り駅", "")),
        "エージェント名": _normalize(data.get("agentDetails", {}).get("エージェント名", "")),
        "特徴": _normalize(data.get("agentDetails", {}).get("特徴", "")),
        "支払いサイト": _normalize(data.get("agentDetails", {}).get("支払いサイト", "")),
        "手数料": _normalize(data.get("agentDetails", {}).get("手数料", "")),
        "その他情報": _normalize(data.get("otherInfo", "")),
    }


def _normalize(s: str) -> str:
    """連続する空白・改行を単一スペースに畳み込む。CSV 内での改行によるレコード分割を防ぐ。"""
    return " ".join(s.split())

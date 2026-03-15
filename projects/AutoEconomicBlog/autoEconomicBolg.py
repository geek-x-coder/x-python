import argparse
import json
import logging
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import google.genai as genai
from google.genai.errors import ClientError
from openai import OpenAI
import requests

from modules.xConfiguration.xConfiguration import Configuration

# ==========================================
# 1. API 키 및 설정 (appConfig.json)
# ==========================================

configFilePath = os.path.join(os.path.dirname(__file__), "appConfig.json")
config = Configuration(configFilePath).load()

NAVER_CLIENT_ID = config["naver"]["client_id"]
NAVER_CLIENT_SECRET = config["naver"]["client_secret"]
GEMINI_API_KEY = config["gemini"]["api_key"]
GEMINI_MODEL = config["gemini"].get("model", "models/gemini-3.0-pro")
GEMINI_SUMMARY_MODEL = config["gemini"].get("summary_model", "models/gemini-2.5-flash")
OPENAI_API_KEY = config.get("openai", {}).get("api_key", "")

# API 클라이언트 초기화
if not GEMINI_API_KEY:
    print("[WARN] Gemini API 키가 설정되어 있지 않습니다. Gemini 기능이 작동하지 않습니다.")
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

if not OPENAI_API_KEY:
    print("[WARN] OpenAI API 키가 설정되어 있지 않습니다. 썸네일 생성 기능이 제한됩니다.")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# 결과 저장 경로 (설정에 따라 변경 가능)
RESULT_CONFIG = config.get("result", {})
RESULT_DIR = os.path.join(os.path.dirname(__file__), RESULT_CONFIG.get("dir", "result"))

# 날짜별 하위 폴더
if RESULT_CONFIG.get("use_date_subfolder", False):
    RESULT_DIR = os.path.join(RESULT_DIR, datetime.now().strftime("%Y-%m-%d"))

os.makedirs(RESULT_DIR, exist_ok=True)

USE_TIMESTAMPED_FILENAME = RESULT_CONFIG.get("use_timestamped_filename", False)
THUMBNAIL_ENABLED = config.get("thumbnail", {}).get("enabled", True)
DOWNLOAD_THUMBNAIL = config.get("thumbnail", {}).get("download", False)

# 로그 설정 (실행파일 위치 /log/YYYY-MM-DD.log)
LOG_DIR = os.path.join(os.path.dirname(__file__), "log")
os.makedirs(LOG_DIR, exist_ok=True)

# 상태 저장 파일 (스케줄러 중복 실행 방지 등)
STATE_FILE = os.path.join(LOG_DIR, "state.json")

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

current_log_date = datetime.now().date()

# 파일 핸들러 (날짜별 파일)
log_file_path = os.path.join(LOG_DIR, f"{current_log_date:%Y-%m-%d}.log")
file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
logger.addHandler(file_handler)

# 콘솔 출력 핸들러
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
logger.addHandler(console_handler)


def _refresh_log_handler_if_needed() -> None:
    """날짜가 바뀌면 새로운 로그 파일로 교체합니다."""
    global current_log_date, file_handler

    today = datetime.now().date()
    if today == current_log_date:
        return

    # 이전 핸들러 제거
    logger.removeHandler(file_handler)
    file_handler.close()

    # 새 핸들러 추가
    current_log_date = today
    new_log_path = os.path.join(LOG_DIR, f"{current_log_date:%Y-%m-%d}.log")
    file_handler = logging.FileHandler(new_log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(file_handler)


def _load_state() -> dict:
    """스케줄 상태를 로드합니다."""
    if not os.path.exists(STATE_FILE):
        return {"last_runs": []}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"last_runs": []}


def _save_state(state: dict) -> None:
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        logger.exception("스케줄 상태 저장 실패")

# ==========================================
# 2. 네이버 뉴스 API로 최신 경제 기사 검색
# ==========================================
def get_latest_economy_news(query="경제 주식", display=3):
    encText = urllib.parse.quote(query)
    # sort=sim(유사도순) 또는 date(최신순)
    url = f"https://openapi.naver.com/v1/search/news.json?query={encText}&display={display}&sort=sim"
    
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        news_list = []
        for item in data['items']:
            title = item['title'].replace('<b>', '').replace('</b>', '').replace('&quot;', '"')
            desc = item['description'].replace('<b>', '').replace('</b>', '').replace('&quot;', '"')
            news_list.append(f"- 제목: {title}\n  내용: {desc}")
        return "\n".join(news_list)
    else:
        logger.error(f"뉴스 검색 에러: {response.status_code}")
        return None

# ==========================================
# 3. Gemini API로 블로그 포스팅 원고 작성
# ==========================================
def evaluate_blog_quality(text, quality_conf):
    # 기본 품질 지표
    length = len(text)
    sections = max(text.count("\n#"), text.count("###"), text.count("["))  # 단순 추정
    has_table = "|" in text and "---" in text

    required_keywords = quality_conf.get("required_keywords", [])
    keyword_hits = {kw: (kw in text) for kw in required_keywords}

    missing = []
    if length < quality_conf.get("min_length", 0):
        missing.append(f"length<{quality_conf.get('min_length')}")
    if sections < quality_conf.get("min_sections", 0):
        missing.append(f"sections<{quality_conf.get('min_sections')}")
    if quality_conf.get("require_table", False) and not has_table:
        missing.append("no_table")
    for kw, hit in keyword_hits.items():
        if not hit:
            missing.append(f"missing_keyword:{kw}")

    # 점수 계산 (0~100)
    score = 0
    score += min(length / max(quality_conf.get("min_length", 1), 1), 2) * 20
    score += min(sections / max(quality_conf.get("min_sections", 1), 1), 2) * 20
    score += 20 if has_table else 0
    if required_keywords:
        score += (sum(keyword_hits.values()) / len(required_keywords)) * 20
    score = min(int(score), 100)

    return {
        "length": length,
        "sections": sections,
        "has_table": has_table,
        "keyword_hits": keyword_hits,
        "missing": missing,
        "score": score,
        "pass": score >= quality_conf.get("min_score", 0)
    }


def generate_blog_post(news_context, feedback=None):
    prompt = f"""
    당신은 수년간 활동해 온 친절하고 전문적인 경제/주식 블로거입니다. 
    아래 제공된 최신 경제 뉴스들을 바탕으로 국내 및 해외 주식 시장의 현재 상황을 분석하고 향후 주가를 예상하는 블로그 포스팅을 작성해 주세요.

    {f'[피드백] {feedback}\n' if feedback else ''}

    [최신 경제 뉴스 데이터]
    {news_context}

    [작성 필수 가이드라인 - 반드시 지켜주세요]
    1. 어조 및 문체: 매우 친절하고 친근하지만 격식을 갖춘 존댓말(~습니다, ~합니다, ~까요?)을 사용하세요. 독자에게 조곤조곤 이야기하듯 자연스럽게 풀어써야 합니다.
    2. 사람다운 글쓰기: '결론적으로', '요약하자면', '이 글에서는' 같은 AI 특유의 기계적인 표현을 절대 사용하지 마세요. 사람이 직접 타이핑하며 고민한 흔적이 느껴지는 자연스러운 문맥을 만들어주세요.
    3. 분량 및 구조: 글을 6개 ~ 7개의 섹션으로 나누고, 각 섹션 위에는 흥미를 유발하는 [소제목]을 달아주세요.
    4. 시각적 자료(표): 글의 중간(3~4번째 섹션 쯤)에 기사 내용이나 시장 상황, 국내외 주식 비교 등을 한눈에 볼 수 있는 '마크다운 표(Table)'를 반드시 1개 이상 작성해 주세요.
    5. 내용 깊이: 단순한 기사 요약이 아닙니다. 이 뉴스가 경제에 미칠 영향과 우리가 주목해야 할 투자 포인트, 섹터 등을 분석적으로 서술하세요.
    6. 해시태그: 전체 글이 끝난 후, 맨 마지막 줄에 블로그 검색 노출을 위한 핵심 키워드 30개를 추천해 주세요. (형식: #키워드1 #키워드2 ...)
    """
    
    logger.info("✍️ 블로그 원고를 작성하는 중입니다. (약 30초~1분 소요)...")

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
            return response.candidates[0].content.parts[0].text
        except ClientError as e:
            status = getattr(e, "status_code", None)
            if status == 429:
                logger.warning(f"Quota exceeded (attempt {attempt}/{max_attempts}): {e}")
                # 가능하면 retryDelay 파싱
                retry_after = 5
                try:
                    detail = getattr(e, "response", {})
                    if isinstance(detail, dict):
                        for d in detail.get("error", {}).get("details", []):
                            if d.get("@type", "").endswith("RetryInfo"):
                                retry = d.get("retryDelay", "")
                                if retry.endswith("s"):
                                    retry_after = float(retry[:-1])
                except Exception:
                    pass
                time.sleep(retry_after)
                continue
            logger.error(f"Gemini 생성 중 오류: {e}")
            return None
        except Exception as e:
            logger.error(f"Gemini 생성 중 예기치 못한 오류: {e}")
            return None

    logger.error("최대 시도 횟수를 초과하여 블로그 원고를 생성하지 못했습니다.")
    return None

# ==========================================
# 4. OpenAI DALL-E 3로 썸네일 이미지 생성
# ==========================================
def generate_thumbnail(blog_text):
    if not OPENAI_API_KEY:
        logger.warning("OpenAI API 키가 설정되어 있지 않아 썸네일 생성이 불가능합니다.")
        return None

    logger.info("🎨 글 내용에 맞는 썸네일 이미지를 생성 중입니다...")
    
    # 썸네일 프롬프트를 만들기 위해 글의 핵심 주제를 짧게 요약 (Gemini 활용)
    try:
        response = client.models.generate_content(
            model=GEMINI_SUMMARY_MODEL,
            contents=f"다음 글의 핵심 경제 주제를 영어로 1문장으로 요약해줘. 이미지 생성용 프롬프트야:\n\n{blog_text[:1000]}"
        )
        image_prompt = response.candidates[0].content.parts[0].text.strip()
    except Exception as e:
        logger.warning(f"썸네일용 요약 생성 실패: {e}")
        return None
    
    # 세련된 블로그 썸네일 스타일 추가
    # (OpenAI 이미지 생성은 ASCII만 처리하는 경우가 있어, 한글을 제거하고 요청)
    safe_prompt = (
        f"A high-quality, modern, and professional blog thumbnail illustration representing: {image_prompt}. "
        "3D isometric style, vibrant colors, clean background, no text."
    )
    safe_prompt = safe_prompt.encode("ascii", "ignore").decode("ascii")

    try:
        response = openai_client.images.generate(
            model="dall-e-3",
            prompt=safe_prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        image_url = response.data[0].url
        return image_url
    except Exception as e:
        logger.error(f"이미지 생성 실패: {e}")
        return None

# ==========================================
# 5. 메인 실행부
# ==========================================
SEARCH_QUERY = config.get("search_query", "미국 금리 인하 한국 증시")


def should_run_now(schedule_conf: dict, state: dict) -> bool:
    now = datetime.now()
    key = now.strftime("%Y-%m-%d %H:%M")

    last_runs = set(state.get("last_runs", []))
    if key in last_runs:
        return False

    time_str = now.strftime("%H:%M")

    daily_conf = schedule_conf.get("daily", {})
    if isinstance(daily_conf, list):
        # 호환성: 기존 list 형식
        times = daily_conf
    else:
        times = daily_conf.get("times", [])

    # 특정 시각 일정
    for t in times:
        if t == time_str:
            last_runs.add(key)
            state["last_runs"] = _prune_old_runs(last_runs)
            return True

    # 시간 주기 일정
    interval_str = daily_conf.get("interval")
    if interval_str:
        try:
            h, m = map(int, interval_str.split(":"))
            interval_td = timedelta(hours=h, minutes=m)
            last_run_str = state.get("last_run")
            if last_run_str:
                last_run = datetime.fromisoformat(last_run_str)
                if now - last_run >= interval_td:
                    last_runs.add(key)
                    state["last_runs"] = _prune_old_runs(last_runs)
                    state["last_run"] = now.isoformat()
                    return True
            else:
                # 첫 실행
                last_runs.add(key)
                state["last_runs"] = _prune_old_runs(last_runs)
                state["last_run"] = now.isoformat()
                return True
        except ValueError:
            logger.warning(f"잘못된 interval 형식: {interval_str}")

    return False


def _prune_old_runs(runs: set, keep_days: int = 2) -> list:
    """상태 파일에 너무 오래된 실행 기록이 쌓이지 않도록 정리합니다."""
    cutoff = datetime.now().date() - timedelta(days=keep_days)
    pruned = [r for r in runs if datetime.strptime(r, "%Y-%m-%d %H:%M").date() >= cutoff]
    return sorted(pruned)


def run_job(search_query: str):
    _refresh_log_handler_if_needed()

    # 1. 뉴스 데이터 수집
    news_data = get_latest_economy_news(search_query)

    if not news_data:
        logger.warning("뉴스 데이터 수집에 실패했습니다. 다음 일정까지 대기합니다.")
        return

    # 2. 블로그 글 작성 (품질 평가 포함)
    #    * max_retries 만큼 다양한 버전을 생성하고, 품질 점수가 가장 높은 결과를 최종 선택합니다.
    quality_conf = config.get("quality", {})
    blog_content = None
    quality_report = None

    max_retries = quality_conf.get("max_retries", 1)
    best_content = None
    best_report = None
    best_score = -1

    for attempt in range(1, max_retries + 1):
        blog_content = generate_blog_post(news_data)
        if not blog_content:
            logger.warning(f"[{attempt}/{max_retries}] 블로그 원고 생성에 실패했습니다. 다음 시도를 진행합니다.")
            continue

        quality_report = evaluate_blog_quality(blog_content, quality_conf)

        if quality_report["score"] > best_score:
            best_score = quality_report["score"]
            best_content = blog_content
            best_report = quality_report

        missing_text = ", ".join(quality_report.get("missing", []))
        logger.info(f"[{attempt}/{max_retries}] 점수: {quality_report['score']} (누락: {missing_text or '없음'})")

    if not best_content:
        logger.error("블로그 원고를 생성하지 못해 작업을 종료합니다.")
        return

    blog_content = best_content
    quality_report = best_report

    # 3. 썸네일 이미지 생성 (설정에 따라 수행)
    thumbnail_url = None
    if THUMBNAIL_ENABLED:
        thumbnail_url = generate_thumbnail(blog_content)
    else:
        logger.info("썸네일 생성 기능이 비활성화되어 있습니다 (config.thumbnail.enabled=False).")

    # 4. 결과 출력 및 저장
    filename_base = "economy_blog_post"
    if USE_TIMESTAMPED_FILENAME:
        filename_base += "_" + datetime.now().strftime("%Y%m%d_%H%M%S")

    out_path = os.path.join(RESULT_DIR, f"{filename_base}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(blog_content)

    # 메타 정보 저장
    meta = {
        "generated_at": datetime.now().isoformat(),
        "search_query": search_query,
        "gemini_model": GEMINI_MODEL,
        "gemini_summary_model": GEMINI_SUMMARY_MODEL,
        "output_file": out_path,
        "thumbnail_url": thumbnail_url,
        "quality_report": quality_report,
    }
    meta_path = os.path.join(RESULT_DIR, f"{filename_base}_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    logger.info("=" * 50)
    logger.info(f"✅ 블로그 포스팅 원고가 성공적으로 작성되었습니다! ('{out_path}' 확인)")
    if thumbnail_url:
        logger.info(f"🖼️ 썸네일 이미지 다운로드 링크:\n{thumbnail_url}")
        if DOWNLOAD_THUMBNAIL:
            try:
                img_data = requests.get(thumbnail_url, timeout=30)
                img_data.raise_for_status()
                thumb_path = os.path.join(RESULT_DIR, f"{filename_base}_thumbnail.png")
                with open(thumb_path, "wb") as f:
                    f.write(img_data.content)
                logger.info(f"🖼️ 썸네일이 '{thumb_path}'에 저장되었습니다.")
            except Exception as e:
                logger.error(f"썸네일 다운로드 중 오류 발생: {e}")
    logger.info(f"📄 메타 정보가 '{meta_path}'에 저장되었습니다.")
    logger.info("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="AutoEconomicBlog 실행 스크립트")
    parser.add_argument("--once", action="store_true", help="한 번만 실행하고 종료")
    parser.add_argument("--search", type=str, help="검색어(뉴스 쿼리)를 덮어쓰기")
    parser.add_argument("--no-thumbnail", action="store_true", help="썸네일 생성 기능 비활성화")
    parser.add_argument("--dry-run", action="store_true", help="실제 파일 생성 없이 동작만 확인")
    args = parser.parse_args()

    schedule_conf = config.get("schedule", {})

    search_query = args.search or SEARCH_QUERY

    if args.no_thumbnail:
        globals()["THUMBNAIL_ENABLED"] = False

    if args.once or not schedule_conf:
        if args.dry_run:
            logger.info("Dry run: 작업을 수행하지 않고 종료합니다.")
            return
        run_job(search_query)
        return

    logger.info(f"스케줄 모드: {schedule_conf}")
    state = _load_state()
    interval = schedule_conf.get("check_interval_minutes", 1)

    while True:
        try:
            _refresh_log_handler_if_needed()
            if should_run_now(schedule_conf, state):
                if args.dry_run:
                    logger.info("Dry run: 스케줄 실행 조건에 해당하나 실제 작업을 수행하지 않습니다.")
                else:
                    run_job(search_query)
                _save_state(state)
        except Exception:
            logger.exception("스케줄 실행 중 오류 발생")
        time.sleep(interval * 60)


if __name__ == "__main__":
    main()
import urllib.request
import json
import random
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import google.genai as genai
from modules.xConfiguration.xConfiguration import Configuration

# ==========================================
# 1. API 키 설정
# ==========================================
configFilePath = os.path.join(os.path.dirname(__file__), "appConfig.json")
config = Configuration(configFilePath).load()

NAVER_CLIENT_ID = config["naver"]["client_id"]
NAVER_CLIENT_SECRET = config["naver"]["client_secret"]
GEMINI_API_KEY = config["gemini"]["api_key"]
MODEL_NAME = config["gemini"].get("model", "models/gemini-2.5-flash")

# google.genai client
client = genai.Client(api_key=GEMINI_API_KEY)

# 결과 파일을 저장할 디렉토리
RESULT_DIR = os.path.join(os.path.dirname(__file__), "result")
os.makedirs(RESULT_DIR, exist_ok=True)

# ==========================================
# 2. 카테고리(키워드) 자동 선택 풀 설정
# ==========================================
# 평소 관심 있는 주제나 블로그의 방향성에 맞는 키워드들을 넣어둡니다.
CATEGORY_POOL = [
    "미러리스 카메라", 
    "홈서버용 NAS 장비", 
    "미러리스 카메라 렌즈", 
    "최신형 맥미니", 
    "로보락 로봇청소기",
    "키보드"
]

def select_random_category():
    """풀에서 무작위로 하나의 카테고리를 선택합니다."""
    return random.choice(CATEGORY_POOL)

# ==========================================
# 3. 네이버 쇼핑 API로 인기 상품 검색
# ==========================================
def search_popular_product(keyword):
    encText = urllib.parse.quote(keyword)
    # display=1 (1개만), sort=sim (유사도/인기순)
    url = f"https://openapi.naver.com/v1/search/shop?query={encText}&display=1&sort=sim"
    
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", NAVER_CLIENT_ID)
    request.add_header("X-Naver-Client-Secret", NAVER_CLIENT_SECRET)
    
    try:
        response = urllib.request.urlopen(request)
        rescode = response.getcode()
        if rescode == 200:
            response_body = response.read()
            data = json.loads(response_body.decode('utf-8'))
            if data['items']:
                return data['items'][0] # 가장 인기 있는 첫 번째 상품 반환
    except Exception as e:
        print(f"네이버 API 호출 에러: {e}")
    return None

# ==========================================
# 4. LLM을 활용한 블로그 포스팅 초안 생성
# ==========================================
def generate_blog_post(product_info, category):
    title = product_info['title'].replace('<b>', '').replace('</b>', '')
    lprice = product_info['lprice']
    link = product_info['link']
    mall_name = product_info['mallName']
    
    prompt = f"""
    당신은 네이버 블로그에서 활동하는 친근하고 솔직한 상품 리뷰어(브랜드 커넥터)입니다.
    오늘의 리뷰 주제는 '{category}'입니다.
    블로그 이야기를 작성해줘. 
    글을 요약하듯이 작성하지 말고 이야기 하듯이 문장을 만들어서 완성해줘. 
    글은 6~7개의 섹션으로 나누고 글에 대한 소제목을 넣어줘. 
    글의 어조는 친절하고 친근하며 이해가 쉽게 작성해줘. 
    인공지능이 작성한 것과 같은 단어나 문장을 사용하지 말고 사람이 작성한 것처럼 완성해줘. 
    글의 주요내용을 한눈에 확인할 수 있도록 글 중간에 표를 하나 이상 작성해주면 좋겠어. 
    모든 문장은 ~습니다와 같은 격식있는 문체였으면 좋겠어. 
    그리고 블로그 글 내용의 키워드 30개도 추천해줘. 상품 및 전체 글에 대해서 썸네일 그림도 생성해줘.
    
    [상품 정보]
    - 상품명: {title}
    - 가격: {int(lprice):,}원
    - 판매처: {mall_name}
    - 구매 링크: {link}
    
    [작성 가이드]
    1. 도입부: 오늘의 주제인 '{category}'에 대한 평소의 생각이나 일상 이야기로 자연스럽게 시작할 것.
    2. 본론: 이 상품이 왜 인기 있는지, 어떤 장점이 있는지 설득력 있게 적을 것.
    3. 결론: 가격 정보를 언급하고 구매 링크를 자연스럽게 유도할 것.
    4. 글 중간중간 적절한 이모지(😊, ✨, 🛍️ 등)를 사용할 것.
    """

    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    # google.genai response structure: response.candidates[0].content.parts[0].text
    try:
        return response.candidates[0].content.parts[0].text
    except Exception:
        # fallback to string conversion if structure differs
        return str(response)

# ==========================================
# 5. 실행부
# ==========================================
if __name__ == "__main__":
    # 1. 카테고리 자동 선택
    search_keyword = select_random_category()
    print(f"🎲 오늘 선택된 카테고리: [{search_keyword}]")
    print("인기 상품 검색 중...")
    
    # 2. 상품 검색
    product = search_popular_product(search_keyword)
    
    if product:
        product_title = product['title'].replace('<b>', '').replace('</b>', '')
        print(f"✅ 상품을 찾았습니다: {product_title}")
        print("블로그 포스팅 초안을 생성합니다...\n" + "-"*50)
        
        # 3. 블로그 글 생성 (카테고리 정보도 함께 넘겨서 문맥을 살림)
        blog_post = generate_blog_post(product, search_keyword)
        print(blog_post)
        print("-"*50)
        
        # 4. 파일로 저장
        out_path = os.path.join(RESULT_DIR, "blog_draft.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(blog_post)
        print(f"🎉 초안이 '{out_path}' 파일로 저장되었습니다!")
        
    else:
        print("해당 카테고리의 상품을 찾지 못했습니다.")
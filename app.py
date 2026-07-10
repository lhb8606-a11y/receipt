import streamlit as st
import pandas as pd
from google import genai
import json
import io
from pdf2image import convert_from_bytes
from PIL import Image

# =====================================================================
# 🔑 Streamlit의 안전한 금고(Secrets)에서 키를 몰래 불러옵니다.
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
# =====================================================================

# 🚀 2026년형 최신 구글 GenAI 클라이언트 엔진 장착!
client = genai.Client(api_key=GEMINI_API_KEY)

def analyze_receipt_with_gemini(image_obj):
    prompt_text = """
    이 이미지에는 하나 또는 여러 개의 영수증이 있습니다. 
    각 영수증을 분리하여 다음 정보를 추출하고, 반드시 JSON 배열(Array) 형태로만 반환하세요.
    마크다운 코드 블록(```json 등)을 제외하고 순수한 JSON 문자열만 반환해야 합니다.

    추출 항목:
    - 날짜 (YYYY-MM-DD 형식으로 가능한 변환)
    - 사업자 이름
    - 사업자 등록번호
    - 결제항목 (가장 대표적인 품목 1~2개 또는 '외식대', '주유비' 등으로 요약. 품목이 없다면 전체 금액에 대한 항목 기재)
    - 결제금액 (숫자만, 콤마 제외)

    특정 정보를 도저히 찾을 수 없다면 해당 값은 빈 문자열("")로 남겨주세요.
    """
    
    try:
        # 💡 최신 클라이언트 문법과 gemini-2.5-flash 적용
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt_text, image_obj]
        )
        result_text = response.text.strip()
        
        # JSON 포맷팅 (마크다운 백틱 제거)
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
            
        return json.loads(result_text)
    except Exception as e:
        st.error(f"AI 분석 중 에러 발생: {e}")
        return []

# 웹사이트 UI 구성
st.set_page_config(page_title="영수증 자동 인식기 (Pro)", page_icon="🧾", layout="centered")
st.title("🧾 인공지능 영수증 자동 인식기 (Gemini Vision)")
st.markdown("Google 최신 AI를 탑재하여 구겨진 영수증도 완벽하게 인식합니다. 캡처 이미지를 **아무 곳이나 클릭 후 Ctrl+V**로 바로 붙여넣으세요!")

uploaded_files = st.file_uploader("📂 영수증 파일 업로드 (PDF, 이미지 여러 장 가능)", type=['pdf', 'png', 'jpg', 'jpeg'], accept_multiple_files=True)

if st.button("AI 정보 추출 시작", type="primary"):
    if not GEMINI_API_KEY:
        st.error("올바른 Gemini API Key를 입력해주세요.")
    elif not uploaded_files:
        st.warning("파일을 업로드하거나 이미지를 붙여넣어 주세요.")
    else:
        with st.spinner("AI가 영수증을 꼼꼼히 읽고 있습니다... 잠시만 기다려주세요 ⏳"):
            all_extracted_data = []

            for file in uploaded_files:
                file_name = file.name
                ext = file_name.split('.')[-1].lower()
                pil_images = []

                if ext == 'pdf':
                    try:
                        pages = convert_from_bytes(file.read())
                        pil_images.extend(pages)
                    except Exception as e:
                        st.error(f"PDF 변환 에러 ({file_name}): {e}")
                else:
                    try:
                        img = Image.open(file)
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                        pil_images.append(img)
                    except Exception as e:
                        st.error(f"이미지 열기 에러 ({file_name}): {e}")

                for img in pil_images:
                    receipts_data = analyze_receipt_with_gemini(img)
                    
                    for data in receipts_data:
                        all_extracted_data.append({
                            "파일이름": file_name,
                            "날짜": data.get("날짜", ""),
                            "사업자 이름": data.get("사업자 이름", ""),
                            "사업자 등록번호": data.get("사업자 등록번호", ""),
                            "결제항목": data.get("결제항목", ""),
                            "결제금액": data.get("결제금액", "")
                        })

            if not all_extracted_data:
                st.error("추출된 데이터가 없습니다.")
            else:
                df = pd.DataFrame(all_extracted_data)
                df = df[["파일이름", "날짜", "사업자 이름", "사업자 등록번호", "결제항목", "결제금액"]]
                
                st.success(f"🎉 완벽합니다! {len(all_extracted_data)}개의 데이터 추출을 완료했습니다.")
                st.dataframe(df)

                # 엑셀 다운로드
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='영수증추출')
                excel_data = output.getvalue()

                st.download_button(
                    label="⬇️ 추출된 엑셀 파일 다운로드",
                    data=excel_data,
                    file_name="영수증_AI추출결과.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

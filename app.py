import streamlit as st
import pandas as pd
from google import genai
import json
import io
from pdf2image import convert_from_bytes
from PIL import Image
import datetime
import re

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
client = genai.Client(api_key=GEMINI_API_KEY)

def analyze_receipt_with_gemini(image_obj):
    prompt_text = """
    이 이미지에는 하나 또는 여러 개의 영수증이 있습니다. 
    각 영수증을 분리하여 다음 정보를 추출하고, 반드시 JSON 배열(Array) 형태로만 반환하세요.
    마크다운 코드 블록(```json 등)을 제외하고 순수한 JSON 문자열만 반환해야 합니다.

    추출 항목:
    - 날짜 (YYYY-MM-DD 형식으로 변환)
    - 사업자 이름
    - 사업자 등록번호
    - 결제항목 (가장 대표적인 품목 1~2개 또는 '외식대', '주유비' 등으로 요약)
    - 결제금액 (숫자만, 콤마 제외)
    """
    try:
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=[prompt_text, image_obj]
        )
        result_text = response.text.strip()
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
        return json.loads(result_text)
    except Exception as e:
        st.error(f"AI 분석 중 에러 발생: {e}")
        return []

st.set_page_config(page_title="영수증 자동 인식기 (Pro)", page_icon="🧾", layout="centered")
st.title("🧾 인공지능 영수증 자동 인식기 (Gemini Vision)")
st.markdown("Google 최신 AI를 탑재하여 구겨진 영수증도 완벽하게 인식합니다.")

uploaded_files = st.file_uploader("📂 영수증 파일 업로드 박스", type=['pdf', 'png', 'jpg', 'jpeg'], accept_multiple_files=True)

if st.button("AI 정보 추출 시작", type="primary"):
    if not GEMINI_API_KEY:
        st.error("올바른 Gemini API Key를 입력해주세요.")
    elif not uploaded_files:
        st.warning("파일을 업로드해주세요.")
    else:
        with st.spinner("AI가 영수증을 분석 중입니다... ⏳"):
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
                        st.error(f"PDF 변환 에러: {e}")
                else:
                    try:
                        img = Image.open(file)
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                        pil_images.append(img)
                    except Exception as e:
                        st.error(f"이미지 열기 에러: {e}")

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

            if all_extracted_data:
                df = pd.DataFrame(all_extracted_data)
                df = df[["파일이름", "날짜", "사업자 이름", "사업자 등록번호", "결제항목", "결제금액"]]
                
                def clean_amount(val):
                    val = str(val)
                    cleaned = re.sub(r'[^\d]', '', val)
                    return int(cleaned) if cleaned else 0
                df["결제금액"] = df["결제금액"].apply(clean_amount)
                
                st.success(f"🎉 {len(all_extracted_data)}개의 데이터 추출 완료!")
                st.dataframe(df)

                if len(uploaded_files) == 1:
                    base_name = uploaded_files[0].name.rsplit('.', 1)[0]
                    download_filename = f"{base_name}_추출결과.xlsx"
                else:
                    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    download_filename = f"다중영수증추출_{now_str}.xlsx"

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='영수증추출')
                    worksheet = writer.sheets['영수증추출']
                    for cell in worksheet['F']:
                        if cell.row != 1:
                            cell.number_format = '#,##0'
                            
                excel_data = output.getvalue()
                st.download_button("⬇️ 추출된 엑셀 파일 다운로드", data=excel_data, file_name=download_filename, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

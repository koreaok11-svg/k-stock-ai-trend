# K-Stock AI Trend WebApp

아이폰 Safari에서 접속해 앱처럼 사용하는 한국 주식 트렌드 추천 웹앱입니다.

## 기능
- 코스피/코스닥 종목 스캔
- 추천종목 TOP10
- 관심종목 TOP30
- 테마별 흐름
- 종목별 의견 자동 생성
- 아이폰 카드형 UI

## PC에서 테스트
pip install -r requirements.txt
python app.py

접속:
http://localhost:10000

## Render 배포
1. GitHub 새 저장소 생성
2. 파일 전체 업로드
3. Render.com > New Web Service
4. GitHub 저장소 연결
5. Build Command: pip install -r requirements.txt
6. Start Command: gunicorn app:app
7. Deploy

## 아이폰 사용
Render 주소를 Safari에서 열기 → 공유 버튼 → 홈 화면에 추가

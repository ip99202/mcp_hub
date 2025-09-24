### Docker 실행 가이드

- **요구사항**: Docker, Docker Compose

### 빌드
```bash
docker compose build
```

### 실행
```bash
docker compose up -d
```

### 접속/헬스체크
- 백엔드 헬스: `curl http://localhost:8000/healthz`
- API 문서: `http://localhost:8000/docs`
- 프론트: `http://localhost:5173`

### 로그 확인
```bash
docker compose logs -f backend
# 또는
docker compose logs -f frontend
```

### 중지/정리
```bash
docker compose down
# 볼륨/로컬 이미지까지 정리
docker compose down -v --rmi local
```

### 부분 리빌드/재시작
```bash
# 백엔드만
docker compose build backend && docker compose up -d backend
# 프론트만
docker compose build frontend && docker compose up -d frontend
```

### 네트워크/프록시
- 컨테이너 네트워크: `mcp_hub_net`
- 프론트(Nginx) → 백엔드(uvicorn) 프록시:
  - `/api/*`, `/mcp/*` → `http://backend:8000`
- 호스트 포트 매핑:
  - 백엔드: `8000:8000`
  - 프론트: `5173:80`

### 트러블슈팅
- 포트 사용 중: 다른 프로세스가 8000/5173 점유 시 종료 후 재시도
- 빌드 실패(프론트 TS 에러): 이미 설정해둔 `vite build`가 타입체크 최소화, 그래도 실패 시 `frontend` 수정 후 재빌드
- 백엔드 모듈 누락: `requirements.txt` 변경 후 `docker compose build backend`

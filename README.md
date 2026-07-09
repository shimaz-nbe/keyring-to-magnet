# RubberKeyring → RefrigeratorMagnet

캐릭터 러버 키링을 스캔해 냉장고 마그넷 베이스(3D 프린트용 STL)를 자동 생성하는 파이프라인.

사용자 매뉴얼(상세 단계별 가이드 + 옵션 레퍼런스 + 트러블슈팅): https://claude.ai/code/artifact/fb389db5-c204-48c3-97c2-f71e5693fd32

## 워크플로

1. **스캔 (사람)**: 금속 고리를 제거한 러버 키링 1개 + 지름 10mm 검정 원 1개를 함께 스캔. 앞면은 요철 때문에 외곽선이 왜곡되므로 **뒷면을 스캔** — Stage 1이 기본으로 좌우 반전을 적용해 앞면 기준 실루엣으로 보정함(이미 앞면을 스캔했다면 `--no-flip`).
2. **Stage 1 (자동)**: 스캔 이미지 → SVG 3종(기준원/키링/베이스) + calibration.json + debug_overlay.png
3. **사람 검수**: `debug_overlay.png`를 보고 외곽선 검출이 정확한지 확인.
4. **Stage 2 (자동, 승인 후)**: SVG 3종 → Blender headless로 STL 생성 (마그넷 포켓 2개 + 키링 홈)
5. **3D 프린트** 후 러버 키링을 홈에 접착.

## 환경 설정

```powershell
py -3.14 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Potrace

- **Windows**: `vendor\potrace\potrace.exe`에 이미 배치됨 (공식 배포: https://potrace.sourceforge.net/ , GPLv2+).
- **macOS**: `brew install potrace`로 설치하면 PATH에서 자동으로 찾음. 직접 바이너리를 두려면 `vendor/potrace/potrace`(확장자 없음)에 배치.
- 다른 위치를 쓰려면 `POTRACE_EXE` 환경변수로 경로 지정 (모든 OS 공통).

### Blender

- **Windows**: `C:\Program Files\Blender Foundation\Blender <버전>\` 아래에서 설치된 버전을 자동으로 찾음(여러 버전이 있으면 최신 버전 사용).
- **macOS**: `/Applications/Blender*.app`에서 자동으로 찾음.
- 못 찾으면 PATH의 `blender`도 시도. 다른 경로를 쓰려면 `pipeline.py stage2 --blender-exe "..."` 또는 `BLENDER_EXE` 환경변수로 지정.

## 사용법

```powershell
# Stage 1: 스캔 이미지 -> SVG 3종 + 미리보기
python pipeline.py stage1 scan.png --outdir out\my_keyring

# debug_overlay.png 확인 후...

# Stage 2: SVG -> STL (대화형 승인 프롬프트)
python pipeline.py stage2 --outdir out\my_keyring
```

## 테스트

```powershell
pytest
python tools\make_test_scan.py --out tests\fixtures\synthetic_scan.png
python pipeline.py stage1 tests\fixtures\synthetic_scan.png --outdir out\synthetic
python pipeline.py stage2 --outdir out\synthetic --approve
python tools\validate_stl.py out\synthetic\model.stl
```

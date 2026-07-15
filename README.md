이 프로젝트의 코드는 claude로 제작되었습니다.
러버 마그넷을 좋아하지만 그나마 나오는 가샤폰은 러버 키링이 대부분이라 
키링을 냉장고에 마그넷처럼 붙이기 위해 3D 프린터 출력용 모델 파일 제작의 자동화를 진행했습니다. 
생성된 STL 파일을 슬라이서 프로그램 (뱀부랩 등)에 넣고 출력하시면 됩니다. 
아크릴 키링의 경우 외곽선이 정상적으로 인식 되는지 검증하지 않았습니다. 

이 작업에는 다음의 기기와 재료가 필요합니다. 
- 스캐너
- 3D 프린터
- 10mm x 2mm 원형 네오디뮴 자석

아직 설명을 정리하지 못해 터미널에 익숙하지 않으면 사용법이 살짝 복잡할 수 있습니다만 
한단계씩 따라하면 어렵지 않게 결과물을 만들 수 있습니다. 

설치 매니저와 드래그앤드랍을 사용한 GUI 버전도 계획중이긴 합니다만 일정에 기약은 없습니다. 

아래 부터는 claude로 생성한 문서입니다. 
직접 그대로 해보며 검증도 완료했습니다. 

# RubberKeyring → RefrigeratorMagnet



## 워크플로

1. **스캔 (사람)**: 금속 고리를 제거한 러버 키링 1개 + 지름 10mm 검정 원 1개를 함께 스캔. 앞면은 요철 때문에 외곽선이 왜곡되므로 **뒷면을 스캔** — Stage 1이 기본으로 좌우 반전을 적용해 앞면 기준 실루엣으로 보정함(이미 앞면을 스캔했다면 `--no-flip`).
2. **Stage 1 (자동)**: 스캔 이미지 → SVG 3종(기준원/키링/베이스) + calibration.json + debug_overlay.png
3. **사람 검수**: `debug_overlay.png`를 보고 외곽선 검출이 정확한지 확인.
4. **Stage 2 (자동, 승인 후)**: SVG 3종 → Blender headless로 STL 생성 (마그넷 포켓 2개 + 키링 홈)
5. **3D 프린트** 후 러버 키링을 홈에 접착.

같은 스캔 세팅(조명/배경/기준원 배치 등)으로 이미 여러 장을 검증해 검출 정확도를 신뢰할 수 있게 됐다면, 3번(사람 검수)을 생략하고 `run` 서브커맨드로 스캔 이미지에서 STL까지 한 번에 생성할 수 있음 — 아래 사용법 참고.

## 환경 설정

**Windows**:

```powershell
py -3.14 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**macOS**:

```bash
python3 -m venv .venv
source .venv/bin/activate
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
- **버전 호환성**: Blender 4.2 LTS와 5.1에서 확인됨(동일 입력에 대해 STL 볼륨/치수 완전 일치). Stage 2가 쓰는 오퍼레이터(`import_curve.svg`, `wm.stl_export`/`wm.obj_export`, Boolean modifier `EXACT` solver)는 모두 Blender 4.0에서 도입된 것들이라 4.0~4.1도 동작할 가능성이 높지만 실기 확인은 4.2/5.1만 됨. 4.0 미만은 미확인/비권장.
- **macOS 실기 검증 완료** (2026-07-14, Apple Silicon/macOS 26.x, `brew install --cask blender` + `brew install potrace`): 자동 탐색·pytest·합성 및 실물 스캔 전체 파이프라인 전부 성공, STL 수치가 Windows와 소수점까지 완전히 일치.

## 사용법

```powershell
# Stage 1: 스캔 이미지 -> SVG 3종 + 미리보기
python pipeline.py stage1 scan.png --outdir out\my_keyring

# debug_overlay.png 확인 후...

# Stage 2: SVG -> STL (대화형 승인 프롬프트)
python pipeline.py stage2 --outdir out\my_keyring
```

검수 없이 바로 STL까지 생성하려면(Stage 1 + Stage 2를 한 번에, debug_overlay.png 검토 없이):

```powershell
python pipeline.py run scan.png --outdir out\my_keyring
```

## 테스트

```powershell
pytest
python tools\make_test_scan.py --out tests\fixtures\synthetic_scan.png
python pipeline.py stage1 tests\fixtures\synthetic_scan.png --outdir out\synthetic
python pipeline.py stage2 --outdir out\synthetic --approve
python tools\validate_stl.py out\synthetic\model.stl
```

## Python 설치 없이 쓰기 (Windows exe)

Python/venv 설치 없이 바로 쓸 수 있는 단일 실행파일(`keyring-to-magnet.exe`)을 만들 수 있음. `pipeline.py`와 완전히 동일한 명령/옵션을 그대로 사용:

```powershell
keyring-to-magnet.exe check                                  # potrace/Blender 설치 여부 확인 + 미설치 시 설치 안내
keyring-to-magnet.exe run scan.png --outdir out\my_keyring    # 스캔 이미지 -> STL
```

인자 없이 더블클릭하면 potrace/Blender 확인 결과와 간단한 사용법을 보여주고 대기함(콘솔 창이 바로 닫히지 않도록).

- potrace는 exe 안에 함께 번들링됨(빌드 시점에 `vendor/potrace/potrace.exe`가 있으면 자동 포함) — 별도 설치 불필요. 만약 potrace 없이 빌드된 exe를 쓰는 경우(또는 번들된 것과 다른 버전을 쓰고 싶은 경우), **`potrace.exe`를 `keyring-to-magnet.exe`와 같은 폴더에 두면 별도 PATH/환경변수 설정 없이 자동 인식됨**(exe 실행 파일 자체의 실제 경로 기준으로 찾음 — 어느 위치에서/어떻게 실행하든 동일하게 동작, 실측 확인됨).
- **Blender는 exe에 포함되지 않음**(수백MB라 비현실적). `check`가 못 찾으면 설치 페이지를 안내하고, 열어볼지 물어봄.
- exe 용량 약 54MB(`opencv-python-headless` 사용 + 실제로 안 쓰이는 `scipy`/`PIL`/ffmpeg 비디오 코덱을 빌드에서 제외한 결과 — 자세한 근거는 `keyring_to_magnet.spec` 상단 주석 참고).

**빌드 방법** (개발자용, 최종 사용자는 이미 빌드된 exe만 받으면 됨):

```powershell
pip install pyinstaller
pyinstaller keyring_to_magnet.spec
# 결과물: dist\keyring-to-magnet.exe (단일 파일)
```

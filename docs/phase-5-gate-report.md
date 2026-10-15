# Phase 5 gate report — 2026-10-16

## Quyết định

**Phase 5 / release v1.0: NOT_READY.** Bản prototype có runner sáu policy,
raw trace/manifest, validator, replay và demo offline trên fixture disposable.
Đây là smoke evidence; chưa có full evaluation, live provider hoặc sandbox cho
repository không tin cậy.
Không kết luận RQ1–RQ3 từ dữ liệu này.

Trạng thái ban đầu trước yêu cầu push của người dùng: HEAD là
`cd6f9c5dcaa13d938cc49d4350d2dcde377f4123` (`main`, ahead 1 so với
`origin/main`). Working tree đã có nhiều thay đổi Phase 2–4 chưa commit;
`src/rewindcoder/recovery/workflow.py` và các script Phase 5 không có trong
HEAD. Các thay đổi sẵn có được giữ nguyên. Không reset, xóa artifact, commit
hay push ở giai đoạn đó. `runner_source_sha256` và protocol hash ghi lại bytes
cục bộ, nhưng không biến HEAD cũ thành revision có thể clone lại.

Sau khi được yêu cầu đẩy code, source commit
`53bf579e41d7fcbfcaaa7c76270dfe86cb5953d3` đã được clone mới trên
Windows. Clone này qua preflight 3/3 fixture, 58 tests OK với một skip do
quyền tạo symlink, và validator 18/18 ô hợp lệ. Commit cập nhật báo cáo sau
đó chỉ sửa tài liệu, không đổi source hoặc fixture bytes.

## Exit gates

| Gate | Trạng thái | Bằng chứng / lý do |
|---|---|---|
| Protocol và ma trận smoke | PASS trong fixture | `evals/protocol.json`, SHA-256 `b7eca02e2af0c12a56125eff85b6ecb000533ba02aec117540cd612ea730f4b6`; 3 task × 6 variant × 1 seed = 18 ô. `v1`–`v4` là exploratory, không vào mẫu. |
| Đánh giá chính công bằng 10–20 task | NOT_READY | 18/18 ô smoke chạy trên 3 fixture scripted. Người dùng xác nhận chưa có tập 10–20 task và provider dùng chung; sandbox cũng chưa hoạt động. Chưa khóa protocol chính trước kết quả. |
| Sáu variant và integrity | PASS cho fixture smoke | Trên cả 3 task: forward FAIL, retry PASS, agent-only và repo-only NOT_READY, aligned-no-memory PASS, full PASS. Một phía bị independent post-restore verifier từ chối; không nới PASS. |
| Raw data và validator | PASS cho fixture smoke | 18 bundle hợp lệ có trace, manifest, patch, checkpoint; 0 skip/missing/duplicate/invalid. Validator kiểm schema, hash, base, budget, provider, source, policy, trace và verifier. |
| RQ1–RQ3 từ dữ liệu thực nghiệm | NOT_READY | Full = retry-only trên cả 3 scripted task. One-sided bị loại bởi integrity rule nên không đo được chất lượng solve cho RQ2. Mock đưa ra cùng alternative có/không memory, nên RQ3 chưa đo được. |
| Fixture security và fail-closed | PASS có giới hạn | 58 tests OK, 1 skip quyền symlink Windows. Test issue và repository observation cố điều khiển provider sửa forbidden file nhưng tool chặn; kiểm thêm secret path, traversal, approval denial, wrong HEAD/workspace, corrupt checkpoint, one-sided restore, timeout/budget. Chưa có live-model injection test. |
| Sandbox cho arbitrary repository | NOT_READY | `docker version --format '{{.Server.Version}}'` không kết nối được `//./pipe/docker_engine`. Không chạy repo không tin cậy. |
| Manifest replay | PASS trong working tree | Cả 3 full-run manifest replay ở fixture mới đều khớp base, budget, tests, status, verifier và restore conclusion. |
| Fresh-clone preflight, suite và validator | PASS cho fixture offline | Clone source commit `53bf579e41d7fcbfcaaa7c76270dfe86cb5953d3`: preflight 3/3, 58 tests OK (1 skip), validator 18/18. Đây chưa phải live-provider hay container gate. |
| Demo và release media | PASS demo offline; video NOT_READY | `scripts/phase4_demo.py` chứng minh failure → checkpoint selection → aligned restore → rewind memory → alternative plan → independent verifier. Chưa tạo video dự phòng. |
| Release v1.0 | NOT_READY | Các gate full evaluation, sandbox và RQ evidence chưa đạt. |

## Dữ liệu và metric

- Protocol: `evals/protocol.json`; raw: `evals/results/raw/phase5-fixture-smoke-v5/`;
  index: `.../index.json`; summary: `evals/results/summary/phase5-fixture-smoke.json`.
- 18 ô dự kiến và 18 bundle có run ID, raw JSONL trace, manifest, diff patch
  và verifier evidence; 12 run hoàn tất đến final verifier, 6 dừng
  `NOT_READY` sau one-sided restore. Missing 0, corrupt 0, duplicate 0,
  skip 0 theo validator.
- Task Success Rate trên run hoàn tất: forward 0/3, retry 3/3, aligned no
  memory 3/3, full 3/3; hai one-sided N/A (0 run hoàn tất). Coverage mỗi
  variant là 3/3 task dự kiến. Planned-cell yield: forward 0/3, retry 3/3,
  agent-only 0/3, repo-only 0/3, aligned-no-memory 3/3, full 3/3.
- Recovery Success Rate: agent-only 0/3, repo-only 0/3, aligned no memory
  3/3, full 3/3; forward/retry N/A. Restore Integrity Rate tương ứng
  0/3, 0/3, 3/3, 3/3. Wrong Rewind Rate (one-sided được xem là
  policy-invalid) tương ứng 3/3, 3/3, 0/3, 0/3.
- Repeated Failure Rate N/A: chưa quan sát failure sau một restore hợp lệ,
  mẫu số 0. Regression Rate: forward/retry/aligned/full đều 0/3; one-sided
  N/A vì dừng trước final regression test. Token estimate, latency, tool calls,
  rewind count và checkpoint bytes có đủ tử/mẫu/giá trị tại
  `docs/experiment-report.md` và machine-readable summary. Một seed không cho
  khoảng bất định; token là byte/4 estimate, không phải usage từ model.

## Lệnh đã thực chạy

Từ root, với `PYTHONPATH=src`, `PYTHONDONTWRITEBYTECODE=1`:

```powershell
python -B -m unittest discover -s tests -t .
python -B scripts/phase1_preflight.py
python -B scripts/phase5_evaluate.py
python -B scripts/phase5_validate.py
python -B scripts/phase5_replay.py <full-run-manifest>
python -B scripts/phase4_demo.py
git diff --check
docker version --format '{{.Server.Version}}'
```

Kết quả: **58 tests OK, 1 skipped** (real symlink creation permission; mock
symlink rejection vẫn được test); preflight **3/3** base/gold/forbidden check;
matrix **18 recorded/0 skipped**; validator **0 invalid/missing**; replay
**6/6 checks PASS trên cả 3 manifest**; Phase 4 demo **PASS**; `git diff --check` exit 0 (chỉ
cảnh báo LF→CRLF); Docker Engine **unavailable**. Unit policy tests, fixture
integration/E2E, security negative tests, replay và demo là các mức bằng chứng
khác nhau; không đồng nhất với live provider hoặc sandbox production.
Python mặc định trong tool sandbox hiện tại bị `WinError 5` khi
`Path.resolve(strict=True)` trên thư mục fixture; suite/preflight/demo/replay
được chạy bằng quyền đã được auto-review chấp thuận. Đây là giới hạn môi
trường thực thi của lần kiểm chứng, không phải một assertion failure.

## Thay đổi để review

- Runner/variant/restore: `src/rewindcoder/agent/graph.py`,
  `src/rewindcoder/recovery/{workflow,executor}.py`,
  `src/rewindcoder/tools/workspace.py`,
  `src/rewindcoder/contracts/manifest.py`,
  `evals/schemas/run_manifest.schema.json`.
- Protocol/scripts/tests/data: `evals/protocol.json`,
  `evals/phase5_tasks/{tsv_whitespace,adapter_service}.json`,
  `scripts/phase5_{evaluate,validate,replay}.py`,
  `tests/integration/test_phase5_variants.py`,
  `tests/unit/test_phase5_security.py`, `evals/results/raw/`,
  `evals/results/summary/`, `evals/baselines/README.md`,
  `evals/ablation/README.md`.
- Docs: `README.md`, `docs/{architecture,evaluation,security,limitations,experiment-report,reproducibility,phase-5-gate-report}.md`.
  Các file Phase 2–4 có sẵn trong working tree không được gộp thành evidence
  Phase 5 mới.

## Việc cần làm trước v1.0

1. Chọn 10–20 task đủ điều kiện và provider dùng được cho cùng ma trận sáu
   variant; khóa protocol chính trước khi xem kết quả, chọn nhiều seed nếu
   nondeterministic, chạy trong sandbox đã kiểm tra.
2. Kiểm raw/manifest/verifier toàn bộ run, giữ skip/invalid trong báo cáo,
   phân tích paired outcomes và failure cases. Chỉ kết luận RQ1–RQ3 nếu metric
   thực nghiệm hỗ trợ; nếu full không hơn retry-only, báo nguyên trạng.
3. Chạy lại security/replay trong image hoặc môi trường cô lập có version rõ,
   rồi chuẩn bị video demo nếu có công cụ ghi hình phù hợp.

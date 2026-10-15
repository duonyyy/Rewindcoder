# RewindCoder — Kế hoạch triển khai Phase 1

> **Tên phase:** Contract và môi trường tái lập
> **Mục tiêu:** tạo nền tảng offline, có hợp đồng dữ liệu rõ ràng và có thể kiểm chứng trước khi tích hợp LLM thật.
> **Trạng thái tài liệu:** kế hoạch triển khai; chưa phải báo cáo hoàn thành.

## 1. Phạm vi và kết quả cần đạt

### 1.1. Mục tiêu

Phase 1 phải chứng minh được rằng RewindCoder có một nền tảng tối thiểu nhưng đáng tin cậy để chạy các thí nghiệm recovery sau này:

- task, state, trace và run manifest có schema/version rõ ràng;
- repository fixture nhỏ, cố định và có thể chạy lại;
- chính sách command phân biệt thao tác an toàn, thao tác cần phê duyệt và thao tác bị từ chối;
- mock provider chạy hoàn toàn offline, có cả nhánh thành công và thất bại;
- mọi lần chạy đều để lại bằng chứng đủ để tái lập và kiểm tra.

Kết quả cuối phase là một **baseline v0.1** có thể chạy bằng Python và test local, chưa phải coding agent hoàn chỉnh.

### 1.2. Ngoài phạm vi

Không triển khai trong Phase 1:

- LLM thật, API key, vLLM, GPU hoặc Docker;
- agent tự sửa code trong repository thật;
- tự động rewind/restore hoàn chỉnh;
- MCP, LangGraph runtime, multi-agent;
- SWE-bench, SWE-RPG hoặc benchmark hiệu năng lớn;
- claim về độ chính xác, latency hoặc chi phí khi chưa có benchmark hợp lệ.

Nếu một hạng mục chưa thực sự chạy được thì báo cáo phải ghi `NOT_RUN` hoặc `NOT_READY`, không được suy diễn thành `PASS`.

## 2. Hiện trạng trước khi bắt đầu

### Đã có trong scaffold

- contract cho `RewindCoderState`;
- metadata và manager cho checkpoint;
- recovery decision, selector và restore plan;
- command policy với các mức `AUTO`, `APPROVAL`, `DENY`;
- JSONL trace cơ bản;
- verifier cơ bản;
- test unit hiện có chạy được bằng:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -t .
```

### Còn thiếu để đóng Phase 1

- schema versioned cho task và run manifest;
- `docs/requirements.md` mô tả requirement có thể kiểm thử;
- ba fixture repository độc lập, nhỏ và deterministic;
- mock provider có hành vi thành công, lỗi và timeout;
- harness tạo trace và manifest cho từng run;
- kiểm thử reproducibility, secret safety và workspace boundary;
- gate report kết luận `PASS` hoặc `NOT_READY` dựa trên bằng chứng.

Các file/contract đang có phải được mở rộng có kiểm soát, không tạo thêm một bộ state hoặc trace song song chỉ vì tên khác nhau.

## 3. Nguyên tắc triển khai

1. **Offline-first:** test Phase 1 không gọi internet, model server hoặc dịch vụ bên ngoài.
2. **Schema trước implementation:** mọi object đi qua boundary phải có version và validator.
3. **Fixture nhỏ, có chủ đích:** mỗi fixture chứng minh một rủi ro khác nhau; không sao chép một repository lớn.
4. **Evaluator-only tách khỏi agent input:** gold patch, expected answer và hidden requirement không được đưa vào context của agent.
5. **Fail closed:** command chưa được phân loại, provider lỗi, timeout hoặc thiếu evidence không được coi là thành công.
6. **Deterministic:** cùng fixture base, cùng seed/config phải cho cùng hash, cùng kết quả kiểm thử và cùng cấu trúc trace cần thiết.
7. **Evidence over claim:** report phải trỏ được tới command, artifact, test và thời điểm chạy.
8. **Scope nhỏ:** chỉ sửa các file phục vụ Phase 1; không đưa kỹ thuật triển khai LLM vào phase này.

## 4. Cấu trúc công việc

Phase 1 vẫn là **một phase duy nhất**. Bên trong chia thành bốn work package để triển khai và review dễ hơn:

| Work package | Mục tiêu | Output chính | Điều kiện hoàn thành |
|---|---|---|---|
| WP1 | Chuẩn hóa contract | schema, validator, requirements | sample hợp lệ và không hợp lệ đều được kiểm tra |
| WP2 | Tạo môi trường tái lập | 3 fixture repository | base/gold/negative case chạy đúng kỳ vọng |
| WP3 | Tạo offline harness | mock provider, policy, trace, manifest | chạy được success/failure mà không có network |
| WP4 | Đóng phase bằng bằng chứng | integration tests, gate report | toàn bộ gate G1–G8 đạt hoặc có kết luận `NOT_READY` |

---

## 5. WP1 — Contract và schema versioned

### Mục tiêu

Biến các giả định hiện tại thành hợp đồng dữ liệu có thể validate độc lập với agent và model.

### Output

Tạo hoặc hoàn thiện:

```text
docs/requirements.md
evals/schemas/task.schema.json
evals/schemas/run_manifest.schema.json
src/rewindcoder/contracts/__init__.py
src/rewindcoder/contracts/task.py
src/rewindcoder/contracts/state.py
src/rewindcoder/contracts/trace.py
src/rewindcoder/contracts/validation.py
tests/unit/test_contracts.py
```

Nếu state/trace hiện đang nằm ở module khác, giữ backward compatibility cần thiết và chuyển dần qua contract module; không xóa API cũ nếu chưa có test thay thế.

### Nội dung contract bắt buộc

#### Task contract

Task tối thiểu cần có:

- `schema_version`, ví dụ `task/v1`;
- `task_id` ổn định và không chứa secret;
- `repository.kind`, `repository.path` hoặc fixture reference, `base_commit`;
- `issue` mô tả lỗi hoặc yêu cầu bằng ngôn ngữ tự nhiên;
- `explicit_requirements` là các điều kiện có thể kiểm thử;
- `target_commands` và `regression_commands`;
- `forbidden_paths` hoặc vùng không được phép sửa;
- `budget` gồm timeout/retry/tool-call nếu áp dụng;
- phần `evaluator_only` tách riêng cho hidden requirement, gold patch và expected result.

`evaluator_only` chỉ được dùng bởi evaluator, không được serialize vào prompt/context của agent.

#### Agent state contract

State phải biểu diễn được tối thiểu:

- `task_id`, `issue`, `requirements`;
- `current_goal`, `plan`, `current_step`, `context_summary`;
- `changed_files`, `test_results`, `errors`;
- `retry_count`, `rewind_count`, `current_checkpoint`;
- `tool_history`, `budget_remaining`.

State phải round-trip được qua JSON mà không làm mất field quan trọng. Field mới phải có default hoặc migration rule rõ ràng.

#### Trace contract

Mỗi event JSONL phải có:

- `schema_version`, ví dụ `trace/v1`;
- timestamp UTC;
- `run_id` opaque;
- `task_id`;
- `node` hoặc component phát event;
- `event`;
- `details` có cấu trúc, không chứa secret.

Trace không ghi API key, access token, nội dung `.env`, full environment dump hoặc đường dẫn ngoài workspace nếu không cần thiết.

#### Run manifest contract

Manifest phải ghi được:

- `run_id`, `task_id`;
- commit của RewindCoder và commit base của fixture;
- phiên bản Python và mode chạy;
- command test và kết quả;
- timestamp UTC;
- version của policy/tool;
- trạng thái `PASS`, `FAIL`, `NOT_RUN` hoặc `NOT_READY`.

### Kiểm thử WP1

- sample task hợp lệ được parse và validate;
- task thiếu `task_id`, `schema_version`, requirement hoặc command bị reject;
- field ngoài contract bị reject hoặc được xử lý theo policy đã ghi rõ;
- `evaluator_only` không xuất hiện trong agent-facing payload;
- state serialize rồi deserialize vẫn giữ nguyên nội dung;
- trace thiếu field bắt buộc bị reject;
- trace/manifest có API key giả, token giả hoặc `.env` bị test chặn;
- manifest chấp nhận `NOT_RUN` cho hạng mục chưa chạy;
- schema có version, test version mismatch cho kết quả dễ hiểu.

### Exit gate WP1

WP1 chỉ đạt khi có schema file, validator, test hợp lệ/không hợp lệ và tài liệu requirements liên kết được từng requirement với test hoặc gate.

## 6. WP2 — Ba repository fixture tái lập

### Mục tiêu

Tạo các repository rất nhỏ nhưng đại diện cho các tình huống mà recovery agent phải phân biệt. Fixture phải build/test được trên máy local, không phụ thuộc network.

### Cấu trúc chung

Mỗi fixture nên có:

```text
evals/fixtures/<fixture_id>/
├── README.md
├── fixture-manifest.json
├── pyproject.toml
├── src/
├── tests/
└── .gitignore
```

Manifest của fixture phải ghi fixture ID, base commit/hash, build command, test command, expected base result, expected gold result, forbidden paths và cleanup rule. Gold patch chỉ dành cho evaluator; không copy vào agent workspace/context.

### Fixture 001 — Bug đơn giản, target test fail

**Mục tiêu:** kiểm tra đường cơ bản từ issue đến patch nhỏ.

**Ví dụ phạm vi:** hàm `parse_name` xử lý sai input rỗng hoặc whitespace.

**Kỳ vọng:**

- base revision: target test fail;
- gold revision: target test pass;
- regression test với tên hợp lệ vẫn pass;
- chỉ cho phép sửa file thuộc module đích và test cần thiết theo manifest.

### Fixture 002 — Requirement ngầm và regression

**Mục tiêu:** kiểm tra agent có đọc evidence trong repository thay vì chỉ sửa theo một câu issue mơ hồ.

**Ví dụ phạm vi:** dữ liệu TSV phải giữ nguyên whitespace có ý nghĩa, trong khi CSV vẫn giữ behavior cũ.

**Kỳ vọng:**

- hidden requirement nằm trong test/evidence của fixture;
- target test thể hiện boundary case;
- regression test chứng minh behavior cũ không bị phá;
- gold patch của evaluator không được gửi vào agent input.

### Fixture 003 — Cross-file regression và boundary

**Mục tiêu:** kiểm tra thay đổi qua service/adapter/test và ràng buộc file được phép sửa.

**Ví dụ phạm vi:** service gọi adapter theo contract; thay đổi adapter phải giữ compatibility với caller hiện tại.

**Kỳ vọng:**

- target test yêu cầu thay đổi có kiểm soát qua nhiều file;
- regression test kiểm tra caller cũ;
- sửa `forbidden_paths` bị phát hiện và không được coi là pass;
- không cần network, database thật hoặc package ngoài.

### Kiểm thử WP2

- hash của fixture base ổn định giữa hai lần tạo;
- base test cho mỗi fixture có kết quả đúng với manifest;
- gold patch chỉ được evaluator dùng và làm test pass;
- regression test pass sau gold patch;
- sửa forbidden path bị fail;
- chạy lại cùng fixture không tạo khác biệt ngoài artifact run được phép;
- không có symlink ra ngoài workspace;
- không có secret, private key hoặc URL cần network trong fixture;
- cleanup đưa workspace về trạng thái đã quy định.

### Exit gate WP2

WP2 chỉ đạt khi cả ba fixture có manifest, base commit/hash, target test, regression test và evidence cho base/gold/negative case.

## 7. WP3 — Offline harness, policy, mock provider và trace

### Mục tiêu

Chạy một task end-to-end ở mức harness mà không cần LLM thật, đồng thời chứng minh command policy và trace hoạt động đúng.

### Output

Tạo hoặc hoàn thiện:

```text
src/rewindcoder/providers/__init__.py
src/rewindcoder/providers/base.py
src/rewindcoder/providers/mock.py
src/rewindcoder/runtime/__init__.py
src/rewindcoder/runtime/run_manifest.py
src/rewindcoder/runtime/budget.py
tests/integration/test_phase1_harness.py
scripts/run_phase1_preflight.ps1
```

### Mock provider

Mock provider phải:

- nhận input theo task/state contract;
- trả về output có schema ổn định;
- có scenario thành công, provider error và timeout;
- dùng seed/config cố định nếu có dữ liệu sinh ngẫu nhiên;
- không gọi network, không đọc secret và không giả vờ là LLM thật;
- ghi rõ `provider=mock` trong trace/manifest.

Mock provider chỉ kiểm tra plumbing và failure handling. Nó không chứng minh năng lực sửa code của model.

### Command policy tối thiểu

| Nhóm thao tác | Mức mặc định | Kiểm tra |
|---|---|---|
| đọc file trong workspace, `rg`, `git status`, `git diff` | `AUTO` | path boundary |
| test local có timeout | `AUTO` | command allowlist và timeout |
| ghi file qua tool contract | `APPROVAL` hoặc policy cụ thể | path + diff |
| `git reset`, `rm`, cài package, đổi remote | `APPROVAL` | không chạy ngầm |
| command chưa biết, network, truy cập ngoài workspace | `DENY` | fail closed |

Policy phải quyết định dựa trên command đã parse, không dựa trên chuỗi prefix đơn giản có thể bị bypass.

### Preflight command

`run_phase1_preflight.ps1` phải kiểm tra:

- Python version và import path;
- schema parse được;
- fixture manifest đầy đủ;
- test discovery;
- repository/fixture ở base commit đúng;
- output directory hợp lệ;
- không yêu cầu API key, Docker, GPU hoặc model server.

Script chỉ chuẩn bị và kiểm tra; không tự động push, reset repository người dùng hoặc xóa dữ liệu ngoài thư mục run.

### Kiểm thử WP3

- mock success tạo state/trace/manifest hợp lệ;
- mock provider error trả trạng thái lỗi, không tạo fake success;
- timeout trả `provider_timeout` và kết thúc theo budget;
- unknown command bị `DENY`;
- risky command yêu cầu `APPROVAL`;
- budget vượt quá trả `fail_closed` hoặc `NOT_RUN`;
- mọi trace có cùng `run_id` và `task_id` trong một run;
- không ghi ngoài workspace/output directory đã allowlist;
- manifest vẫn được ghi khi run kết thúc do failure;
- chạy offline khi tắt network hoặc trong môi trường không có network.

### Exit gate WP3

WP3 chỉ đạt khi có ít nhất một run thành công và các run lỗi/timeout tương ứng, với trace và manifest có thể đọc lại để giải thích kết quả.

## 8. WP4 — Verification và Phase 1 gate report

### Mục tiêu

Đóng phase bằng một quy trình kiểm chứng lặp lại được và một báo cáo không phóng đại kết quả.

### Quy trình chạy chuẩn

1. Kiểm tra working tree và fixture base commit.
2. Chạy preflight.
3. Validate schema và sample task.
4. Chạy test base của ba fixture.
5. Chạy gold validation ở evaluator boundary.
6. Chạy mock success, failure và timeout.
7. Sinh trace, run manifest và kết quả test.
8. Chạy toàn bộ unit/integration test.
9. Kiểm tra secret, path boundary và reproducibility.
10. Sinh gate report với trạng thái cuối cùng.

### Output

```text
docs/phase-1-gate-report.md
evals/results/phase-1/
├── manifest.json
├── schema-validation.json
├── fixture-validation.json
├── test-summary.json
├── traces/
└── limitations.md
```

Không commit raw secret, log chứa token, cache, temporary workspace hoặc private absolute path không cần thiết.

### Gate matrix

| Gate | Nội dung | Tiêu chí PASS |
|---|---|---|
| G1 | Task/state/trace schema | sample valid pass, sample invalid reject |
| G2 | State round-trip | serialize/deserialize không mất dữ liệu |
| G3 | Fixture integrity | 3 fixture có hash/base manifest ổn định |
| G4 | Policy safety | unknown deny, risky approval, boundary pass |
| G5 | Offline provider | success/error/timeout phân biệt đúng |
| G6 | Trace/manifest | run_id, task_id, status và evidence đầy đủ |
| G7 | Reproducibility | lặp lại cho cùng kết quả kỳ vọng |
| G8 | Test suite | unit/integration pass, không có test bị bỏ qua im lặng |

### Exit gate của Phase 1

Phase 1 chỉ được kết luận `PASS` khi:

- G1–G8 đều `PASS`;
- ba fixture có base/gold/negative evidence;
- mock provider chạy offline;
- test suite và preflight pass;
- không cần API key, GPU, Docker hoặc dịch vụ ngoài;
- limitations được ghi rõ;
- không có thay đổi ngoài scope;
- không đưa ra metric hiệu năng chưa đo.

Nếu một gate chưa chạy, kết luận là `NOT_READY`, không phải `PASS_WITHOUT_EVIDENCE`.

## 9. Tiến độ đề xuất

### Ngày 1–2: contract

- chốt requirements và field names;
- thêm schema/validator;
- test valid/invalid và state round-trip;
- thống nhất version `task/v1`, `trace/v1`.

### Ngày 3–5: fixture

- tạo fixture 001, 002, 003;
- tạo manifest và base commit;
- viết target/regression/forbidden-path tests;
- kiểm tra hash và cleanup.

### Ngày 6–7: offline harness

- thêm mock provider;
- hoàn thiện policy boundary;
- thêm trace/run manifest/budget;
- viết success/error/timeout tests.

### Ngày 8–10: gate và report

- viết preflight;
- chạy G1–G8 hai lần trong môi trường sạch;
- lưu artifacts cần thiết;
- viết gate report và limitations;
- review diff, secret và phạm vi trước khi commit.

Tiến độ trên là ước lượng để tổ chức công việc, không phải bằng chứng rằng Phase 1 đã hoàn thành.

## 10. Commit plan và kiểm soát thay đổi

Có thể chia commit theo vertical slice:

```text
chore(phase1): define versioned task and trace contracts
test(phase1): add reproducible repository fixtures
feat(phase1): add offline mock provider and preflight harness
test(phase1): add phase one integration gates
docs(phase1): record baseline gate report
```

Trước mỗi commit cần kiểm tra:

- `git diff --check`;
- test command của project;
- `git status --short`;
- không stage file ngoài scope;
- không có secret hoặc output tạm;
- report khớp với kết quả chạy thực tế.

Không push remote trong bước triển khai này nếu chưa có yêu cầu rõ ràng.

## 11. Definition of Done

- [ ] `docs/requirements.md` mô tả requirement và cách kiểm thử.
- [ ] Task, state, trace và run manifest có version/schema.
- [ ] Có sample valid và invalid; validator có test.
- [ ] Có ba fixture độc lập, nhỏ và offline.
- [ ] Base/gold/regression/negative case có evidence.
- [ ] Evaluator-only data không đi vào agent input.
- [ ] Mock provider có success/error/timeout.
- [ ] Policy thực hiện `AUTO`/`APPROVAL`/`DENY` theo boundary.
- [ ] Preflight kiểm tra được môi trường mà không gọi LLM thật.
- [ ] Trace và manifest sinh được cả khi run fail.
- [ ] Reproducibility test pass.
- [ ] G1–G8 có trạng thái và bằng chứng.
- [ ] `docs/phase-1-gate-report.md` ghi rõ PASS/NOT_READY và limitations.
- [ ] Diff cuối chỉ nằm trong scope RewindCoder Phase 1.

Kết luận Phase 1 chỉ được viết là **PASS** sau khi checklist trên được đánh dấu bằng kết quả chạy thực tế. Trước thời điểm đó, trạng thái đúng là **IN PROGRESS** hoặc **NOT READY**.

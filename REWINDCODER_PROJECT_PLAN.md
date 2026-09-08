# REWINDCODER PROJECT PLAN

## 1. Mục đích của tài liệu

Tài liệu này là kế hoạch triển khai chính thức cho **RewindCoder**. Kế hoạch
được chia thành **5 phase**, đủ ngắn để theo dõi nhưng vẫn tách rõ các rủi ro kỹ
thuật quan trọng.

Mỗi phase đều có:

- mục tiêu cần chứng minh;
- phạm vi công việc;
- output phải tạo ra;
- kiểm thử bắt buộc;
- exit gate để quyết định có được chuyển sang phase tiếp theo hay không.

Nguyên tắc thực hiện:

> Không chuyển phase chỉ vì đã viết xong code. Chỉ chuyển phase khi output tồn
> tại, kiểm thử chạy được và exit gate có bằng chứng PASS.

---

## 2. Bài toán và contribution của dự án

### 2.1. Bài toán

Coding agent thường hoạt động theo vòng lặp:

```text
Observe -> Plan -> Act -> Verify -> Retry
```

Nếu agent hiểu sai yêu cầu hoặc lập kế hoạch sai, các lần sửa tiếp theo có thể
được xây dựng trên một repository state và context state đã sai. Retry từ trạng
thái hiện tại không giải quyết được nguyên nhân gốc.

RewindCoder mở rộng vòng lặp thành:

```text
Observe
  -> Clarify Requirements
  -> Plan
  -> Create Aligned Checkpoint
  -> Act
  -> Verify
  -> Diagnose
  -> Rewind
  -> Record Rewind Memory
  -> Alternative Plan
  -> Act again
```

### 2.2. Contribution chính

RewindCoder không tuyên bố điểm mới là “dùng LLM để viết code” hoặc “dùng
LangGraph”. Contribution cần được chứng minh là:

> Một recovery harness cho coding agent, trong đó agent state và repository
> state được liên kết bằng cùng một checkpoint ID; khi trajectory thất bại, hệ
> thống phát hiện lỗi, chọn checkpoint an toàn, restore hai state đồng bộ, lưu
> structured rewind memory và lập một kế hoạch khác.

### 2.3. Ba câu hỏi nghiên cứu

- **RQ1:** Rewind có làm tăng tỷ lệ hoàn thành task so với forward-only và
  retry-only không?
- **RQ2:** Restore đồng bộ agent state và repository state có tốt hơn restore
  một phía không?
- **RQ3:** Rewind memory có làm giảm việc lặp lại cùng một chiến lược thất bại
  không?

---

## 3. Phạm vi MVP

### Trong phạm vi

- Repository Python nhỏ hoặc vừa, có test chạy được.
- Issue mô tả bug hoặc feature nhỏ.
- Requirement clarification dựa trên issue và repository evidence.
- Lập kế hoạch có file/symbol, cách sửa, constraint và cách kiểm thử.
- Đọc, tìm kiếm, sửa file và chạy command theo policy.
- Agent state, repository manifest và workspace snapshot.
- Failure detection, retry, rewind và alternative planning.
- Unit test, integration test, E2E test và evaluation trace.
- Chạy trong local fixture hoặc Docker sandbox.

### Ngoài phạm vi MVP

- Checkpoint toàn bộ hệ điều hành hoặc container runtime.
- Tự động undo side effect trên database, cloud service hoặc API bên ngoài.
- Tự động rollback Git push, package publication hoặc deployment.
- Multi-agent phức tạp, GraphRAG, Kubernetes hoặc nhiều UI.
- Chạy toàn bộ SWE-bench/SWE-RPG ngay từ đầu.

Nếu task cần side effect bên ngoài, hệ thống phải chặn, yêu cầu human approval
hoặc ghi rõ là **không thể rollback**.

---

## 4. Kiến trúc mục tiêu

```text
Issue / Task
    |
    v
Requirement Clarification
    |
    v
Repository Onboarding
    |
    v
Implementation Plan
    |
    v
Aligned Checkpoint Manager
    |
    v
Coding Agent -> Tools -> Repository
    |
    v
Independent Verifier
    |
    +---- PASS ----> Final Review -> Result
    |
   FAIL
    |
    v
Failure Detector -> Failure Diagnosis
    |
    v
Checkpoint Selector
    |
    v
Restore Agent State + Repository State
    |
    v
Rewind Memory -> Alternative Plan -> Coding Agent
```

### Các ranh giới bắt buộc

| Thành phần | Được sở hữu | Không được sở hữu |
|---|---|---|
| Agent | requirement, plan, task state | thực thi shell trực tiếp |
| Tool layer | side effect đã được policy cho phép | tự quyết định mục tiêu |
| Checkpoint manager | metadata và snapshot | tự đánh dấu restore thành công |
| Recovery manager | detect, select, rewind memory | bỏ qua approval hoặc verifier |
| Verifier | bằng chứng hoàn thành độc lập | sinh patch để tự chấm patch đó |
| Evaluator | metric và so sánh hệ thống | cho agent xem gold patch/hidden test |

---

## 5. Các contract phải ổn định

### 5.1. Task contract

Mỗi evaluation task phải có tối thiểu:

```text
task_id
repository_url hoặc fixture_path
base_commit
issue
explicit_requirements
hidden_requirements_for_evaluation
target_test_command
regression_test_command
forbidden_paths
budget
timeout
```

Gold patch và hidden requirements chỉ dành cho evaluator. Agent không được đọc
chúng trong lúc chạy, nếu không kết quả bị data leakage.

### 5.2. Agent state contract

Agent state phải lưu được:

- task ID và issue;
- clarified requirements;
- plan và bước hiện tại;
- context summary;
- changed files và test results;
- retry count và rewind count;
- current checkpoint ID;
- tool history, errors và rewind memories;
- token, thời gian và số tool call còn lại.

State phải serialize/deserialize được và có version schema.

### 5.3. Recoverable checkpoint contract

Một recoverable checkpoint chỉ hợp lệ khi cùng một `checkpoint_id` liên kết:

```text
checkpoint_id
  + agent state
  + Git HEAD
  + tracked-file manifest
  + untracked-file manifest
  + workspace snapshot
  + test status
  + verified requirements
  + safety status
```

Chỉ lưu metadata hoặc chỉ lưu Git commit không đủ để gọi là recoverable
checkpoint.

### 5.4. Rewind memory contract

Rewind memory phải là dữ liệu có cấu trúc:

```text
failure_type
failed_hypothesis
evidence
failed_actions
avoid_actions
suggested_direction
confidence
source_trace_ids
```

Không dùng toàn bộ chat history làm rewind memory vì chứa nhiều dữ liệu nhiễu
và reasoning chưa được kiểm chứng.

### 5.5. Definition of Done

Một task chỉ PASS khi:

```text
Target tests pass
AND regression tests pass
AND explicit requirements are satisfied
AND hidden acceptance checks pass
AND no forbidden path is modified
AND no security policy is violated
AND final patch can be reproduced from the recorded base commit
```

Agent tự nói “đã hoàn thành” không phải bằng chứng hoàn thành.

---

## 6. Tổng quan 5 phase

| Phase | Phiên bản | Kết quả chính | Thời lượng gợi ý |
|---|---|---|---:|
| 1 | v0.1 | Contract, fixture và nền tảng tái lập | 1-2 tuần |
| 2 | v0.3 | Coding agent forward-only chạy được | 2 tuần |
| 3 | v0.5 | Aligned checkpoint và manual rewind | 2 tuần |
| 4 | v0.8 | Self-recovery tự động | 2-3 tuần |
| 5 | v1.0 | Evaluation, hardening và demo | 2-3 tuần |

Thời gian có thể thay đổi, nhưng thứ tự phụ thuộc không được đảo: chưa có
forward-only baseline thì không thể chứng minh rewind tạo ra cải thiện.

---

# PHASE 1 - Contract và môi trường tái lập

## Mục tiêu

Tạo nền tảng mà mọi lần chạy có thể tái lập và kiểm tra độc lập. Phase này chưa
cần LLM thật và chưa cần tự động rewind.

## Công việc

1. Hoàn thiện task schema, agent state schema, checkpoint metadata và trace
   schema.
2. Tạo ba fixture task nhỏ:
   - một bug đơn giản;
   - một bug có implicit requirement;
   - một thay đổi nhiều file dễ gây regression.
3. Với mỗi fixture, khóa base commit và cung cấp:
   - test fail trước khi sửa;
   - test pass với gold patch;
   - regression tests;
   - forbidden paths.
4. Hoàn thiện command policy theo nguyên tắc default deny.
5. Cung cấp mock provider để test workflow không phụ thuộc API key.
6. Chuẩn hóa JSONL trace và run manifest.

## Output bắt buộc

- `docs/requirements.md`
- `docs/architecture.md`
- `docs/security.md`
- `evals/tasks/*.json`
- `evals/fixtures/`
- `src/rewindcoder/agent/state.py`
- `src/rewindcoder/tools/policy.py`
- `src/rewindcoder/observability/trace.py`
- `tests/unit/`
- Một command duy nhất để chạy toàn bộ unit test.

## Kiểm thử

- Validate task JSON bằng schema; thiếu `base_commit`, test command hoặc budget
  phải bị từ chối.
- Agent state serialize rồi deserialize phải giữ nguyên dữ liệu.
- Unknown command phải bị DENY.
- Command rủi ro phải yêu cầu approval.
- Fixture phải tạo được cùng test result từ cùng base commit.
- `.env`, API key và token không được nằm trong Git history.
- Trace event phải có `run_id`, timestamp, node, event và details.

## Exit gate

Phase 1 PASS khi:

- ba fixture đều tái lập được;
- toàn bộ unit test pass;
- task/state/trace schema được đóng version `v1`;
- không cần API key để chạy test;
- có báo cáo ngắn ghi rõ giới hạn môi trường.

---

# PHASE 2 - Coding agent forward-only

## Mục tiêu

Xây agent có thể nhận issue, làm rõ requirement, đọc repository, lập kế hoạch,
sửa code và được verifier kiểm tra. Agent chỉ được retry cục bộ; chưa được
rewind.

Phase này tạo baseline cần thiết cho RQ1.

## Workflow

```text
parse_issue
  -> clarify_requirements
  -> repo_onboarding
  -> create_plan
  -> implement
  -> run_target_tests
  -> run_regression_tests
  -> verify
  -> final_review hoặc stop
```

Requirement clarification phải xem xét ít nhất:

- intent và phạm vi;
- technical context;
- interface/protocol;
- code structure/convention;
- data semantics;
- constraint và validation obligation.

Plan phải trả lời được:

- sửa để đạt mục tiêu gì;
- file/symbol nào liên quan;
- cách thay đổi dự kiến;
- constraint nào phải giữ;
- kiểm thử kết quả bằng cách nào.

## Công việc

1. Tạo provider interface và hai implementation:
   - deterministic mock cho test;
   - một LLM provider thật, cấu hình bằng environment variable.
2. Triển khai tool thật với workspace scope:
   - repository search;
   - read file;
   - edit file;
   - Git status/diff;
   - target/regression test runner.
3. Tích hợp workflow framework-neutral hoặc LangGraph.
4. Thêm budget: max step, max token, timeout và max tool calls.
5. Tạo CLI chạy một task và xuất patch, verifier result, trace, run manifest.

## Output bắt buộc

- `src/rewindcoder/providers/`
- `src/rewindcoder/agent/graph.py`
- `src/rewindcoder/agent/prompts.py`
- `src/rewindcoder/tools/`
- `src/rewindcoder/verification/`
- `src/rewindcoder/cli.py`
- `evals/baselines/forward_only/`
- Integration trace của ít nhất ba fixture task.

## Kiểm thử

- Mock-provider E2E phải chạy offline và cho kết quả xác định.
- Agent không được sửa file ngoài workspace hoặc forbidden paths.
- Plan thiếu validation step phải bị schema validation từ chối.
- Tool output lỗi phải trở thành structured observation, không làm workflow
  crash âm thầm.
- Verifier phải phát hiện target test fail, regression và forbidden edit.
- Cùng fixture, model config và seed phải sinh run manifest có thể so sánh.

## Exit gate

Phase 2 PASS khi:

- forward-only agent hoàn thành ít nhất một fixture end-to-end;
- cả ba fixture đều kết thúc có kiểm soát, không treo vô hạn;
- mọi edit và command xuất hiện trong trace;
- verifier độc lập đưa ra kết quả cuối;
- baseline result được lưu, chưa tuyên bố rewind tốt hơn baseline.

---

# PHASE 3 - Aligned checkpoint và manual rewind

## Mục tiêu

Chứng minh hệ thống có thể tạo và restore đồng bộ agent state cùng repository
state. Việc chọn và kích hoạt rewind ở phase này thực hiện thủ công để tách lỗi
restore khỏi lỗi quyết định của agent.

## Công việc

1. Triển khai repository manifest bằng hash nội dung file.
2. Thu thập Git HEAD, tracked diff, untracked files và test status.
3. Tạo workspace snapshot trong khu vực lưu trữ nằm ngoài target repository.
4. Lưu metadata theo kiểu atomic write.
5. Tạo CLI:
   - `checkpoint create`;
   - `checkpoint list`;
   - `checkpoint inspect`;
   - `rewind --checkpoint <id>`.
6. Restore agent state và repository state bằng cùng checkpoint ID.
7. Sau restore, bắt buộc chạy manifest check, Git diff check và target tests.
8. Trong repository thật, restore cần approval. Tự động restore chỉ được phép
   trong fixture/sandbox đã đánh dấu disposable.

## Output bắt buộc

- `src/rewindcoder/checkpoint/manager.py`
- `src/rewindcoder/checkpoint/repository_snapshot.py`
- `src/rewindcoder/recovery/executor.py`
- Checkpoint storage layout có version.
- Integration tests cho capture/restore.
- Demo manual rewind có trace trước và sau restore.

## Kiểm thử

- Thay đổi tracked file rồi restore: hash phải giống checkpoint.
- Tạo, sửa và xóa untracked file rồi restore: manifest phải khớp.
- Agent state sau restore phải có đúng goal, plan, step, budget và context
  summary của checkpoint.
- Restore agent state nhưng không restore repository, hoặc ngược lại, phải bị
  verifier từ chối.
- Snapshot ghi dở do crash không được xuất hiện trong danh sách checkpoint an
  toàn.
- Checkpoint thiếu archive, manifest hoặc test evidence không được chọn.
- Symlink/path traversal không được ghi ra ngoài workspace.

## Exit gate

Phase 3 PASS khi demo được:

```text
Clean state -> CP1 -> harmful edit -> failed tests
-> approved restore CP1 -> manifest matches -> tests return to CP1 result
```

Đồng thời agent state và repository state phải cùng tham chiếu `CP1`. Nếu chỉ
Git diff được phục hồi nhưng context/plan vẫn là state cũ thì phase chưa PASS.

---

# PHASE 4 - Self-recovery tự động

## Mục tiêu

Tự động phát hiện trajectory thất bại, quyết định retry/diagnose/rewind/stop,
chọn checkpoint an toàn, tạo rewind memory và thử một kế hoạch khác.

## Recovery policy

Ưu tiên deterministic signal trước LLM diagnosis:

```text
Security violation hoặc budget exhausted -> STOP
Transient failure lần đầu                  -> RETRY
Test regression hoặc no progress           -> DIAGNOSE
Cùng failure lặp lại >= N lần               -> REWIND
Unexpected edit ngoài scope                 -> REWIND hoặc STOP
Không có safe checkpoint                    -> STOP + request human action
```

LLM được dùng để giải thích nguyên nhân và đề xuất hướng mới, không được tự bỏ
qua security rule hoặc tự đánh dấu checkpoint là an toàn.

## Công việc

1. Hoàn thiện failure signals và failure taxonomy.
2. Lưu evidence liên kết với trace event, test output và diff.
3. Triển khai safe-checkpoint selector bằng deterministic policy trước.
4. Tạo rewind memory từ bằng chứng đã xác thực.
5. Inject rewind memory vào replan context.
6. Kiểm tra alternative plan khác kế hoạch thất bại ở hành động cốt lõi.
7. Giới hạn max retries, max rewinds, token, thời gian và checkpoint storage.
8. Ghi lại mọi recovery decision và lý do vào trace.

## Output bắt buộc

- `src/rewindcoder/recovery/detector.py`
- `src/rewindcoder/recovery/selector.py`
- `src/rewindcoder/recovery/memory.py`
- `src/rewindcoder/recovery/executor.py`
- Workflow có nhánh recovery hoàn chỉnh.
- `evals/results/self_recovery/`
- E2E failure-injection scenarios.

## Kiểm thử

- Failure lần đầu được retry, lặp cùng lỗi đủ ngưỡng mới rewind.
- Security violation phải STOP ngay, không hỏi LLM để nới policy.
- Selector không bao giờ trả checkpoint `safe=false`.
- Rewind memory phải chứa failed hypothesis, evidence và avoid actions.
- Alternative plan lặp lại avoid action mà không có evidence mới phải bị từ
  chối.
- Max rewind và budget exhaustion phải kết thúc workflow rõ ràng.
- Sau rewind, final verifier vẫn phải chạy toàn bộ target và regression tests.
- Test recovery không được phụ thuộc vào việc agent tự báo thành công.

## Exit gate

Phase 4 PASS khi ba failure-injection scenario đều chứng minh được:

1. hệ thống phát hiện đúng failure;
2. restore đúng aligned checkpoint;
3. không lặp lại failed action đã bị cấm;
4. tạo alternative plan;
5. kết thúc bằng verifier PASS hoặc STOP có lý do, không vòng lặp vô hạn.

---

# PHASE 5 - Evaluation, hardening và release v1.0

## Mục tiêu

Đánh giá contribution bằng thực nghiệm công bằng, kiểm tra security và đóng gói
một prototype có thể chạy lại bởi giảng viên hoặc người dùng GitHub.

## Hệ thống cần so sánh

| Variant | Agent rollback | Repository rollback | Rewind memory |
|---|:---:|:---:|:---:|
| Forward-only | No | No | No |
| Retry-only | No | No | No |
| Agent-state rewind | Yes | No | Yes |
| Repository-only rewind | No | Yes | No |
| Aligned rewind without memory | Yes | Yes | No |
| RewindCoder full | Yes | Yes | Yes |

Forward-only và retry-only phải có policy khác nhau rõ ràng, dù cả hai đều không
có rollback.

## Quy tắc thực nghiệm

Mọi variant phải dùng cùng:

- task set và base commit;
- model/provider và tham số;
- prompt phần không liên quan đến recovery;
- token/tool/time budget;
- Docker image hoặc môi trường thực thi;
- target test và regression test;
- số lần lặp.

Khuyến nghị cho đồ án:

- bắt đầu với ba fixture để debug;
- đánh giá chính trên 10-20 task phù hợp ngân sách;
- chạy mỗi variant nhiều hơn một lần nếu LLM không deterministic;
- công bố raw trace và run manifest, không chỉ bảng tổng hợp.

## Metrics

- **Task Success Rate:** số task verifier PASS / tổng số task.
- **Recovery Success Rate:** số trajectory sau rewind đạt verifier PASS / số
  trajectory đã thực hiện rewind.
- **Repeated Failure Rate:** số failure sau rewind trùng failed action hoặc root
  cause trước / tổng failure sau rewind.
- **Wrong Rewind Rate:** số rewind không thỏa policy hoặc quay về checkpoint
  không cải thiện được state / tổng rewind.
- **Restore Integrity Rate:** số restore khớp agent state, manifest và Git diff /
  tổng restore.
- **Regression Rate:** số task làm hỏng pass-to-pass tests / tổng task.
- Token usage, latency, tool calls, số rewind và checkpoint storage.

Không gọi số liệu là “measured” nếu run không hoàn thành hoặc thiếu raw trace.

## Output bắt buộc

- `evals/baselines/`
- `evals/ablation/`
- `evals/results/raw/`
- `evals/results/summary/`
- `docs/evaluation.md`
- `docs/security.md`
- `docs/limitations.md`
- `docs/experiment-report.md`
- Dockerfile hoặc hướng dẫn môi trường tái lập.
- README có quickstart, architecture, demo và kết quả có provenance.
- Demo trực tiếp và video dự phòng.

## Kiểm thử

- Chạy toàn bộ unit, integration và E2E suite từ môi trường sạch.
- Re-run cùng run manifest phải dựng lại đúng repository base state.
- Prompt injection từ issue/repository không được thay đổi tool policy.
- Secret leakage test phải pass.
- Restore phải bị từ chối ngoài sandbox hoặc khi thiếu approval.
- Evaluation script phải phát hiện missing run, duplicate run và metric input
  không hợp lệ.
- README quickstart phải được kiểm tra trên fresh clone.

## Exit gate

RewindCoder v1.0 chỉ được tuyên bố hoàn thành khi:

- full evaluation có raw trace và run manifest;
- các baseline và ablation dùng điều kiện công bằng;
- ít nhất một kết luận cho RQ1-RQ3 được hỗ trợ bằng metric thực nghiệm;
- limitation và failure cases được báo cáo;
- fresh clone chạy được quickstart và test suite;
- demo thể hiện rõ failure -> rewind -> alternative plan -> verifier result.

Nếu RewindCoder không vượt retry-only, vẫn phải báo cáo kết quả thật và phân
tích nguyên nhân. Không thay đổi metric hoặc loại task sau khi xem kết quả chỉ
để tạo kết luận đẹp.

---

## 7. Mapping với repository hiện tại

| Khu vực | Vai trò hiện tại |
|---|---|
| `src/rewindcoder/agent/` | state, workflow và prompt contracts |
| `src/rewindcoder/checkpoint/` | checkpoint metadata và snapshot adapter |
| `src/rewindcoder/recovery/` | detector, selector, memory và restore plan |
| `src/rewindcoder/tools/` | tool contracts và command policy |
| `src/rewindcoder/verification/` | Definition of Done và verifier |
| `src/rewindcoder/security/` | approval decision và policy boundary |
| `src/rewindcoder/observability/` | JSONL trace |
| `src/rewindcoder/skills/` | reusable skill contracts |
| `tests/` | unit, integration và E2E |
| `evals/` | task, baseline, ablation và result artifacts |
| `docs/` | architecture, checkpoint, security và evaluation |

### Trạng thái tại thời điểm lập kế hoạch

Repository đã có scaffold và các core contract ban đầu. Unit test hiện tại
kiểm tra state/checkpoint serialization, recovery decision, checkpoint
selection, restore plan, verifier và command policy.

Những phần **chưa được coi là triển khai xong**:

- chưa có LLM/provider integration;
- chưa có coding workflow end-to-end;
- chưa có tool adapter thực thi thật;
- chưa capture/restore workspace thật;
- chưa có Docker sandbox;
- chưa có fixture benchmark hoàn chỉnh;
- chưa có số liệu chứng minh rewind tốt hơn retry.

Việc tồn tại class hoặc interface không đồng nghĩa với chức năng đã hoàn thành.

---

## 8. Rủi ro chính và cách kiểm soát

| Rủi ro | Hậu quả | Kiểm soát |
|---|---|---|
| Restore chỉ một state | agent và repository lệch nhau | invariant cùng checkpoint ID + post-restore verification |
| Agent thấy gold patch | evaluation leakage | tách agent input và evaluator-only artifacts |
| LLM tự quyết định failure | recovery thiếu ổn định | deterministic signals trước, LLM diagnosis sau |
| Rewind quá sớm | tốn chi phí, mất progress | retry/diagnose thresholds + wrong rewind metric |
| Lặp lại cùng chiến lược | rewind không tạo giá trị | structured avoid actions + alternative-plan check |
| Snapshot không đầy đủ | restore giả | tracked/untracked manifest + hash + tests |
| Tool injection | chạy lệnh nguy hiểm | default deny, sandbox và approval gate |
| Benchmark quá lớn | không kịp đồ án | fixture trước, subset sau |
| Chỉ có demo đẹp | không chứng minh contribution | baseline, ablation, raw traces và verifier |

---

## 9. Definition of Done cho toàn dự án

- [ ] Nhận và chuẩn hóa được issue/task.
- [ ] Làm rõ requirement có repository evidence.
- [ ] Sinh plan có mục tiêu, location, approach, constraints và validation.
- [ ] Forward-only baseline chạy được.
- [ ] Tạo recoverable checkpoint gắn hai state.
- [ ] Restore integrity được kiểm tra bằng manifest, Git diff và tests.
- [ ] Failure detector phân biệt retry, diagnose, rewind và stop.
- [ ] Rewind memory lưu bằng chứng và hành động không nên lặp lại.
- [ ] Alternative plan được kiểm tra trước khi thực thi.
- [ ] Security policy, sandbox và approval gate hoạt động.
- [ ] Mọi quyết định quan trọng có trace.
- [ ] Unit, integration và E2E tests pass.
- [ ] Baseline và ablation dùng cùng điều kiện.
- [ ] Báo cáo có raw results, limitations và failure analysis.
- [ ] Fresh clone chạy được README quickstart.

---

## 10. Việc cần làm ngay

Không bắt đầu bằng LangGraph UI hoặc benchmark lớn. Bước tiếp theo là hoàn thành
**Phase 1** theo thứ tự:

1. tạo task/state/trace schema version 1;
2. tạo ba fixture repositories có test xác định;
3. tạo mock provider;
4. chạy unit test và fixture reproducibility test;
5. ghi Phase 1 gate report.

Sau khi Phase 1 PASS mới bắt đầu coding agent forward-only của Phase 2.


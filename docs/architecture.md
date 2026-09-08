# Architecture

## Core invariant

A **recoverable checkpoint** is valid only when one `checkpoint_id` identifies
both a serializable `RewindCoderState` and an immutable repository snapshot
manifest. Restore is not complete until the repository adapter restores the
workspace and the verifier confirms the manifest, `git diff`, and target tests.

## Architecture at a glance

```mermaid
flowchart TB
    I[Issue / Goal] --> C[Clarify Requirements]
    C --> O[Repository Onboarding]
    O --> P[Create Implementation Plan]
    P --> CP[Create Aligned Checkpoint]
    CP --> A[Implement with Allowlisted Tools]
    A --> V[Independent Verifier]

    V -->|PASS| F[Final Review]
    V -->|FAIL| D[Failure Detector]
    D -->|Retry| A
    D -->|Diagnose| DG[Failure Diagnosis]
    DG --> S[Select Safe Checkpoint]
    S --> R[Restore Agent State + Repository State]
    R --> M[Create Rewind Memory]
    M --> RP[Alternative Plan]
    RP --> A
    D -->|STOP| X[Failed Closed]

    subgraph H[Harness: controls every side effect]
        ST[(Durable Agent State)]
        PO[Policy + Approval Gate]
        TR[Trace + Audit Log]
        VE[Checkpoint Manifest + Tests]
    end

    ST -. persists .-> C
    ST -. persists .-> R
    PO -. authorizes .-> A
    PO -. authorizes .-> R
    TR -. records .-> A
    TR -. records .-> D
    VE -. proves .-> CP
    VE -. proves .-> V

    classDef core fill:#dbeafe,stroke:#2563eb,color:#111827
    classDef recovery fill:#fef3c7,stroke:#d97706,color:#111827
    classDef harness fill:#dcfce7,stroke:#16a34a,color:#111827
    classDef terminal fill:#fee2e2,stroke:#dc2626,color:#111827

    class I,C,O,P,A,V,F core
    class CP,D,DG,S,R,M,RP recovery
    class ST,PO,TR,VE harness
    class X terminal
```

Đọc sơ đồ theo ba lớp:

1. **Core workflow:** hiểu issue, lập kế hoạch, sửa code và kiểm chứng.
2. **Recovery loop:** khi verifier báo lỗi, hệ thống retry, diagnose hoặc rewind
   về checkpoint an toàn rồi lập kế hoạch khác.
3. **Harness:** state, policy, trace và verification kiểm soát mọi side effect;
   model không được tự có quyền đọc/ghi hoặc chạy command.

## MVP control flow

```text
parse issue -> onboard repository -> plan -> checkpoint -> implement
-> test/verify -> diagnose -> select safe checkpoint -> approved restore
-> inject rewind memory -> replan -> implement
```

The current implementation contains framework-neutral contracts. Future
adapters can map the workflow to LangGraph, connect an LLM provider, collect
Git metadata, capture a workspace snapshot, and execute approved commands in a
sandbox. Adapters must not change the core invariant.

## Boundaries

| Component | Owns | Must not own |
|---|---|---|
| Agent | task state and plans | shell execution or filesystem mutation |
| Checkpoint manager | metadata persistence | unverified workspace restore |
| Recovery | policy, selection, memory | bypassing approval |
| Tools | controlled side effects | agent planning |
| Verifier | independent completion evidence | patch generation |

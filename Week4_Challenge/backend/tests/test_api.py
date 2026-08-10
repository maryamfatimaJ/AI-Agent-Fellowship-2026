"""FastAPI endpoint integration tests. Uses TestClient, which runs
BackgroundTasks synchronously as part of each request/response cycle, so a
POST /research call has already run the graph to its first pause/completion
by the time `.post()` returns."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


def test_workflow_status_404_for_unknown_run():
    response = client.get("/workflow/run_does_not_exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "run_not_found"


def test_approve_409_once_run_is_already_completed(happy_path_llm):
    # TestClient runs BackgroundTasks synchronously as part of the
    # request/response cycle, so by the time POST /research returns, the
    # scripted happy-path run has already reached "awaiting_approval".
    happy_path_llm()
    start = client.post("/research", json={"text": "Should we enter the market?"})
    run_id = start.json()["run_id"]

    first_approval = client.post("/approve", json={"run_id": run_id, "feedback": None})
    assert first_approval.status_code == 202
    assert client.get(f"/workflow/{run_id}").json()["workflow_status"] == "completed"

    second_approval = client.post("/approve", json={"run_id": run_id, "feedback": None})
    assert second_approval.status_code == 409
    assert second_approval.json()["error"]["code"] == "invalid_workflow_state"


def test_full_research_lifecycle_via_api(happy_path_llm):
    happy_path_llm()

    start = client.post("/research", json={"text": "Should we enter the vertical SaaS market?"})
    assert start.status_code == 202
    run_id = start.json()["run_id"]

    status = client.get(f"/workflow/{run_id}")
    assert status.status_code == 200
    body = status.json()
    assert body["workflow_status"] == "awaiting_approval"
    assert body["awaiting_approval"] is True
    assert body["pending_clarification"] is None

    tasks = client.get(f"/tasks/{run_id}")
    assert tasks.status_code == 200
    task_list = tasks.json()["tasks"]
    assert len(task_list) == 2
    assert all(t["status"] == "completed" for t in task_list)

    evidence = client.get(f"/evidence/{run_id}")
    assert evidence.status_code == 200
    assert len(evidence.json()["evidence"]) == 2

    logs = client.get(f"/logs/{run_id}")
    assert logs.status_code == 200
    trace = logs.json()["trace"]
    assert trace["revision_count"] == 0
    assert "research" in trace["agents_invoked"]
    assert "analyst" in trace["agents_invoked"]

    report_before = client.get(f"/report/{run_id}")
    assert report_before.status_code == 200
    assert report_before.json()["report"] is not None
    assert report_before.json()["workflow_status"] == "awaiting_approval"

    approve = client.post("/approve", json={"run_id": run_id, "feedback": None})
    assert approve.status_code == 202

    final_status = client.get(f"/workflow/{run_id}")
    assert final_status.json()["workflow_status"] == "completed"

    final_report = client.get(f"/report/{run_id}")
    assert final_report.json()["report"]["approval_status"] == "approved"


def test_clarification_endpoint_resumes_paused_run(happy_path_llm):
    from app.schemas.request import StructuredRequest

    ambiguous_then_resolved = [
        StructuredRequest(
            objective="Decide on a market",
            research_questions=[],
            deliverable="decision brief",
            is_ambiguous=True,
            clarification_question="Which market should this focus on?",
        ),
        StructuredRequest(
            objective="Decide whether to enter the vertical SaaS market",
            research_questions=["Is the market growing?", "Who are the competitors?"],
            deliverable="decision brief",
            comparison_criteria=["growth", "competition"],
            entities=["Product A", "Product B"],
            is_ambiguous=False,
        ),
    ]
    happy_path_llm(structured_request=ambiguous_then_resolved)

    start = client.post("/research", json={"text": "Should we enter a market?"})
    run_id = start.json()["run_id"]

    status = client.get(f"/workflow/{run_id}")
    body = status.json()
    assert body["workflow_status"] == "awaiting_clarification"
    assert body["pending_clarification"]["question"] == "Which market should this focus on?"

    answer = client.post(
        "/clarification", json={"run_id": run_id, "answer": "Focus on vertical SaaS, Product A vs Product B."}
    )
    assert answer.status_code == 202

    resumed_status = client.get(f"/workflow/{run_id}")
    assert resumed_status.json()["workflow_status"] == "awaiting_approval"


def test_reject_endpoint_loops_back_to_writer_then_can_be_approved(happy_path_llm):
    happy_path_llm()

    start = client.post("/research", json={"text": "Should we enter the market?"})
    run_id = start.json()["run_id"]

    reject = client.post("/reject", json={"run_id": run_id, "feedback": "Needs a stronger recommendation."})
    assert reject.status_code == 202

    status_after_reject = client.get(f"/workflow/{run_id}")
    assert status_after_reject.json()["workflow_status"] == "awaiting_approval"

    approve = client.post("/approve", json={"run_id": run_id, "feedback": None})
    assert approve.status_code == 202

    final_status = client.get(f"/workflow/{run_id}")
    assert final_status.json()["workflow_status"] == "completed"

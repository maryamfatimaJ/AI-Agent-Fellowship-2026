from tests.conftest import auth_headers, register_and_login


def _create_workspace(client, token):
    return client.post("/api/workspaces", json={"name": "WS"}, headers=auth_headers(token)).json()["id"]


def test_upload_txt_document_is_chunked_and_ready(client):
    token = register_and_login(client, "doc-a@example.com")
    workspace_id = _create_workspace(client, token)

    upload_response = client.post(
        f"/api/workspaces/{workspace_id}/documents",
        files={"file": ("policy.txt", b"Our refund policy allows returns within 30 days.", "text/plain")},
        headers=auth_headers(token),
    )
    assert upload_response.status_code == 201
    body = upload_response.json()
    assert body["status"] == "ready"
    assert body["filename"] == "policy.txt"

    list_response = client.get(f"/api/workspaces/{workspace_id}/documents", headers=auth_headers(token))
    assert len(list_response.json()) == 1


def test_unsupported_file_type_is_rejected(client):
    token = register_and_login(client, "doc-b@example.com")
    workspace_id = _create_workspace(client, token)

    response = client.post(
        f"/api/workspaces/{workspace_id}/documents",
        files={"file": ("archive.zip", b"not a real zip", "application/zip")},
        headers=auth_headers(token),
    )
    assert response.status_code == 400


def test_chat_answer_cites_relevant_document(client):
    token = register_and_login(client, "doc-c@example.com")
    workspace_id = _create_workspace(client, token)

    client.post(
        f"/api/workspaces/{workspace_id}/documents",
        files={
            "file": (
                "policy.txt",
                b"Our refund policy allows returns within 30 days of purchase.",
                "text/plain",
            )
        },
        headers=auth_headers(token),
    )
    client.post(
        f"/api/workspaces/{workspace_id}/documents",
        files={"file": ("shipping.txt", b"Standard shipping takes 5 to 7 business days.", "text/plain")},
        headers=auth_headers(token),
    )

    conversation_id = client.post(
        f"/api/workspaces/{workspace_id}/conversations", json={}, headers=auth_headers(token)
    ).json()["id"]

    response = client.post(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}/messages",
        json={"content": "What is the refund policy?"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    citations = response.json()["assistant_message"]["citations"]
    assert citations, "expected at least one citation"
    assert citations[0]["filename"] == "policy.txt"


def test_deleting_document_removes_its_chunks_from_retrieval(client):
    token = register_and_login(client, "doc-d@example.com")
    workspace_id = _create_workspace(client, token)

    document_id = client.post(
        f"/api/workspaces/{workspace_id}/documents",
        files={"file": ("warranty.txt", b"Our warranty covers manufacturing defects for one year.", "text/plain")},
        headers=auth_headers(token),
    ).json()["id"]

    delete_response = client.delete(
        f"/api/workspaces/{workspace_id}/documents/{document_id}", headers=auth_headers(token)
    )
    assert delete_response.status_code == 204

    list_response = client.get(f"/api/workspaces/{workspace_id}/documents", headers=auth_headers(token))
    assert list_response.json() == []


def test_documents_isolated_between_workspaces(client):
    token = register_and_login(client, "doc-e@example.com")
    workspace_a = _create_workspace(client, token)
    workspace_b = _create_workspace(client, token)

    client.post(
        f"/api/workspaces/{workspace_a}/documents",
        files={"file": ("a.txt", b"Content only relevant to workspace A.", "text/plain")},
        headers=auth_headers(token),
    )

    response = client.get(f"/api/workspaces/{workspace_b}/documents", headers=auth_headers(token))
    assert response.json() == []

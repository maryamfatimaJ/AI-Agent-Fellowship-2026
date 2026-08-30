from tests.conftest import auth_headers, register_and_login

from app.models.assistant import Assistant
from app.models.conversation import Conversation, Message
from app.models.document import Chunk, Document
from app.models.memory import Memory
from app.models.prompt_template import PromptTemplate
from app.models.settings import WorkspaceSettings
from app.models.skill import Skill
from app.models.workspace import Workspace


def test_rename_workspace_persists_and_does_not_affect_others(client):
    token = register_and_login(client, "rename-a@example.com")
    ws1 = client.post("/api/workspaces", json={"name": "Original Name"}, headers=auth_headers(token)).json()
    ws2 = client.post("/api/workspaces", json={"name": "Untouched Workspace"}, headers=auth_headers(token)).json()

    response = client.patch(
        f"/api/workspaces/{ws1['id']}", json={"name": "Renamed Workspace"}, headers=auth_headers(token)
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Workspace"

    # Persists on a fresh GET, not just in the PATCH response
    refetched = client.get(f"/api/workspaces/{ws1['id']}", headers=auth_headers(token))
    assert refetched.json()["name"] == "Renamed Workspace"

    # The other workspace is untouched
    other = client.get(f"/api/workspaces/{ws2['id']}", headers=auth_headers(token))
    assert other.json()["name"] == "Untouched Workspace"


def test_rename_rejects_empty_name(client):
    token = register_and_login(client, "rename-b@example.com")
    ws = client.post("/api/workspaces", json={"name": "Keep Me"}, headers=auth_headers(token)).json()

    response = client.patch(f"/api/workspaces/{ws['id']}", json={"name": ""}, headers=auth_headers(token))
    assert response.status_code == 422

    unchanged = client.get(f"/api/workspaces/{ws['id']}", headers=auth_headers(token))
    assert unchanged.json()["name"] == "Keep Me"


def test_cannot_rename_or_delete_another_users_workspace(client):
    token_a = register_and_login(client, "rename-c@example.com")
    token_b = register_and_login(client, "rename-d@example.com")
    ws = client.post("/api/workspaces", json={"name": "A's Workspace"}, headers=auth_headers(token_a)).json()

    rename_attempt = client.patch(
        f"/api/workspaces/{ws['id']}", json={"name": "Hijacked"}, headers=auth_headers(token_b)
    )
    assert rename_attempt.status_code == 404

    delete_attempt = client.delete(f"/api/workspaces/{ws['id']}", headers=auth_headers(token_b))
    assert delete_attempt.status_code == 404

    # Untouched from the owner's perspective
    still_there = client.get(f"/api/workspaces/{ws['id']}", headers=auth_headers(token_a))
    assert still_there.status_code == 200
    assert still_there.json()["name"] == "A's Workspace"


def test_delete_workspace_persists_and_is_gone_after(client):
    token = register_and_login(client, "delete-a@example.com")
    ws = client.post("/api/workspaces", json={"name": "Doomed"}, headers=auth_headers(token)).json()

    delete_response = client.delete(f"/api/workspaces/{ws['id']}", headers=auth_headers(token))
    assert delete_response.status_code == 204

    get_response = client.get(f"/api/workspaces/{ws['id']}", headers=auth_headers(token))
    assert get_response.status_code == 404

    listing = client.get("/api/workspaces", headers=auth_headers(token)).json()
    assert ws["id"] not in [w["id"] for w in listing]


def test_delete_workspace_cascades_and_leaves_no_orphans(client, db_session):
    token = register_and_login(client, "delete-b@example.com")
    ws = client.post("/api/workspaces", json={"name": "Full of data"}, headers=auth_headers(token)).json()
    ws_id = ws["id"]

    # Conversation + message
    conversation = client.post(
        f"/api/workspaces/{ws_id}/conversations", json={}, headers=auth_headers(token)
    ).json()
    client.post(
        f"/api/workspaces/{ws_id}/conversations/{conversation['id']}/messages",
        json={"content": "Hello"},
        headers=auth_headers(token),
    )

    # Document + chunk (real ingestion via the mocked embedder)
    client.post(
        f"/api/workspaces/{ws_id}/documents",
        files={"file": ("notes.txt", b"Some notes about a refund policy.", "text/plain")},
        headers=auth_headers(token),
    )

    # Manual memory entry
    client.post(
        f"/api/workspaces/{ws_id}/memory",
        json={"key": "note", "value": "Remember this."},
        headers=auth_headers(token),
    )

    # Sanity check: everything actually exists before deletion
    assert db_session.query(Assistant).filter_by(workspace_id=ws_id).count() == 1
    assert db_session.query(Conversation).filter_by(workspace_id=ws_id).count() == 1
    assert db_session.query(Message).join(Conversation).filter(Conversation.workspace_id == ws_id).count() == 2
    assert db_session.query(Document).filter_by(workspace_id=ws_id).count() == 1
    assert db_session.query(Chunk).join(Document).filter(Document.workspace_id == ws_id).count() > 0
    assert db_session.query(PromptTemplate).filter_by(workspace_id=ws_id).count() == 4
    assert db_session.query(Skill).filter_by(workspace_id=ws_id).count() == 6
    assert db_session.query(Memory).filter_by(workspace_id=ws_id).count() == 1
    assert db_session.query(WorkspaceSettings).filter_by(workspace_id=ws_id).count() == 1

    delete_response = client.delete(f"/api/workspaces/{ws_id}", headers=auth_headers(token))
    assert delete_response.status_code == 204

    # Nothing left behind anywhere
    assert db_session.query(Workspace).filter_by(id=ws_id).count() == 0
    assert db_session.query(Assistant).filter_by(workspace_id=ws_id).count() == 0
    assert db_session.query(Conversation).filter_by(workspace_id=ws_id).count() == 0
    assert db_session.query(Message).join(
        Conversation, isouter=True
    ).filter(Conversation.workspace_id == ws_id).count() == 0
    assert db_session.query(Document).filter_by(workspace_id=ws_id).count() == 0
    assert db_session.query(Chunk).join(Document, isouter=True).filter(Document.workspace_id == ws_id).count() == 0
    assert db_session.query(PromptTemplate).filter_by(workspace_id=ws_id).count() == 0
    assert db_session.query(Skill).filter_by(workspace_id=ws_id).count() == 0
    assert db_session.query(Memory).filter_by(workspace_id=ws_id).count() == 0
    assert db_session.query(WorkspaceSettings).filter_by(workspace_id=ws_id).count() == 0


def test_deleting_one_workspace_does_not_affect_a_sibling_workspace(client):
    token = register_and_login(client, "delete-c@example.com")
    ws1 = client.post("/api/workspaces", json={"name": "To delete"}, headers=auth_headers(token)).json()
    ws2 = client.post("/api/workspaces", json={"name": "To keep"}, headers=auth_headers(token)).json()
    client.post(f"/api/workspaces/{ws2['id']}/conversations", json={}, headers=auth_headers(token))

    client.delete(f"/api/workspaces/{ws1['id']}", headers=auth_headers(token))

    kept = client.get(f"/api/workspaces/{ws2['id']}", headers=auth_headers(token))
    assert kept.status_code == 200
    conversations = client.get(f"/api/workspaces/{ws2['id']}/conversations", headers=auth_headers(token)).json()
    assert len(conversations) == 1

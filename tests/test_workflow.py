import pytest

from tests.conftest import auth_headers


async def _create_equipment(client, admin):
    response = await client.post(
        "/api/v1/equipment",
        json={
            "name": "Excavator 01",
            "equipment_type": "Heavy Machinery",
            "registration_number": "EXC-001",
            "serial_number": "SN-001",
            "assigned_site": "Site A",
        },
        headers=auth_headers(admin),
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_full_repair_lifecycle(client, admin, mechanic, supervisor, md):
    equipment = await _create_equipment(client, admin)

    # Mechanic creates and immediately submits the fault report.
    create_resp = await client.post(
        "/api/v1/repair-requests",
        json={
            "equipment_id": equipment["id"],
            "fault_datetime": "2026-10-10T08:00:00Z",
            "fault_type": "corrective_maintenance",
            "priority": "high",
            "fault_description": "Hydraulic leak on the boom arm.",
            "submit_immediately": True,
        },
        headers=auth_headers(mechanic),
    )
    assert create_resp.status_code == 201, create_resp.text
    repair_request = create_resp.json()
    assert repair_request["status"] == "pending_supervisor_approval"
    request_id = repair_request["id"]

    # The reporting mechanic cannot approve their own request.
    self_approve = await client.post(
        f"/api/v1/repair-requests/{request_id}/supervisor-decision",
        json={"decision": "approve", "comment": "nice try"},
        headers=auth_headers(mechanic),
    )
    assert self_approve.status_code == 403

    # Supervisor approves -> moves to pending MD approval.
    sup_decision = await client.post(
        f"/api/v1/repair-requests/{request_id}/supervisor-decision",
        json={"decision": "approve", "comment": "Looks valid."},
        headers=auth_headers(supervisor),
    )
    assert sup_decision.status_code == 200, sup_decision.text
    assert sup_decision.json()["status"] == "pending_md_approval"

    # MD gives final approval.
    md_decision = await client.post(
        f"/api/v1/repair-requests/{request_id}/md-decision",
        json={"decision": "approve", "comment": "Approved."},
        headers=auth_headers(md),
    )
    assert md_decision.status_code == 200, md_decision.text
    assert md_decision.json()["status"] == "approved"

    # Supervisor assigns the mechanic.
    assign_resp = await client.post(
        f"/api/v1/repair-requests/{request_id}/assign-mechanic",
        json={"mechanic_id": str(mechanic.id)},
        headers=auth_headers(supervisor),
    )
    assert assign_resp.status_code == 200, assign_resp.text
    assert assign_resp.json()["status"] == "approved"

    # Mechanic starts the repair.
    start_resp = await client.post(
        f"/api/v1/repair-requests/{request_id}/start",
        headers=auth_headers(mechanic),
    )
    assert start_resp.status_code == 200, start_resp.text
    assert start_resp.json()["status"] == "repair_in_progress"

    # Mechanic logs a repair action/cost.
    action_resp = await client.post(
        f"/api/v1/repair-requests/{request_id}/actions",
        json={
            "action_date": "2026-10-11",
            "action_taken": "Replaced hydraulic seal.",
            "quantity": 2,
            "unit_cost": 50.0,
            "labour_cost": 30.0,
        },
        headers=auth_headers(mechanic),
    )
    assert action_resp.status_code == 201, action_resp.text
    assert action_resp.json()["total_cost"] == 130.0

    # Mechanic marks repair complete.
    complete_resp = await client.post(
        f"/api/v1/repair-requests/{request_id}/complete",
        json={"final_notes": "Tested and working."},
        headers=auth_headers(mechanic),
    )
    assert complete_resp.status_code == 200, complete_resp.text
    assert complete_resp.json()["status"] == "repair_completed"

    # Supervisor closes the request.
    close_resp = await client.post(
        f"/api/v1/repair-requests/{request_id}/close",
        headers=auth_headers(supervisor),
    )
    assert close_resp.status_code == 200, close_resp.text
    assert close_resp.json()["status"] == "closed"

    # A closed request cannot be restarted.
    restart_resp = await client.post(
        f"/api/v1/repair-requests/{request_id}/start",
        headers=auth_headers(mechanic),
    )
    assert restart_resp.status_code in (403, 409)


@pytest.mark.asyncio
async def test_supervisor_can_reject_request(client, admin, mechanic, supervisor):
    equipment = await _create_equipment(client, admin)

    create_resp = await client.post(
        "/api/v1/repair-requests",
        json={
            "equipment_id": equipment["id"],
            "fault_datetime": "2026-10-10T08:00:00Z",
            "fault_type": "emergency_repair",
            "priority": "medium",
            "fault_description": "Dashboard warning light stuck on.",
            "submit_immediately": True,
        },
        headers=auth_headers(mechanic),
    )
    assert create_resp.status_code == 201
    request_id = create_resp.json()["id"]

    reject_resp = await client.post(
        f"/api/v1/repair-requests/{request_id}/supervisor-decision",
        json={"decision": "reject_return", "comment": "Need more details on the fault."},
        headers=auth_headers(supervisor),
    )
    assert reject_resp.status_code == 200, reject_resp.text
    assert reject_resp.json()["status"] == "rejected_returned"

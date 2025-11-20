import pytest

from geoapi.models import TaskStatus
from geoapi.services.file_location_status import FileLocationStatusService


def test_start_check_creates_new_check(db_session, projects_fixture):
    """Test start_check creates a new check when none exists"""
    check = FileLocationStatusService.start_check(
        db_session, projects_fixture.id, celery_task_uuid="uuid"
    )

    assert check is not None
    assert check.project_id == projects_fixture.id
    assert check.task_id is not None
    assert check.task.status == TaskStatus.QUEUED
    assert check.started_at is not None
    assert check.completed_at is None


def test_start_complete_restart(db_session, projects_fixture):
    """Test that start and complete and re-start work"""
    # Create initial check with task_id
    first_check = FileLocationStatusService.start_check(
        db_session, projects_fixture.id, celery_task_uuid="uuid"
    )
    first_started_at = first_check.started_at
    assert (
        FileLocationStatusService.has_running_check(db_session, projects_fixture.id)
        is True
    )

    # Complete it
    FileLocationStatusService.complete_check(db_session, projects_fixture.id)
    db_session.refresh(first_check)
    assert first_check.completed_at is not None
    assert (
        FileLocationStatusService.has_running_check(db_session, projects_fixture.id)
        is False
    )

    # Start again with different task_id
    second_check = FileLocationStatusService.start_check(
        db_session, projects_fixture.id, celery_task_uuid="uuid"
    )

    assert second_check.id == first_check.id  # same entry
    assert second_check.task_id == first_check.task_id  # different tasks
    assert second_check.completed_at is None
    assert second_check.started_at != first_started_at
    assert (
        FileLocationStatusService.has_running_check(db_session, projects_fixture.id)
        is True
    )


def test_complete_check_when_no_check_exists(db_session, projects_fixture):
    """Test complete_check raises ValueError when no check exists"""
    with pytest.raises(ValueError, match="No check found for project"):
        FileLocationStatusService.complete_check(db_session, projects_fixture.id)


def test_has_running_check_returns_false_when_no_check(db_session, projects_fixture):
    """Test has_running_check returns False when no check exists"""
    result = FileLocationStatusService.has_running_check(
        db_session, projects_fixture.id
    )
    assert result is False


def test_has_running_check_returns_true_for_running_check(db_session, projects_fixture):
    """Test has_running_check returns True for a running check"""
    FileLocationStatusService.start_check(
        db_session, projects_fixture.id, celery_task_uuid="uuid"
    )

    result = FileLocationStatusService.has_running_check(
        db_session, projects_fixture.id
    )
    assert result is True


def test_has_running_check_returns_false_for_completed_check(
    db_session, projects_fixture
):
    """Test has_running_check returns False when check is completed"""
    FileLocationStatusService.start_check(
        db_session, projects_fixture.id, celery_task_uuid="uuid"
    )
    FileLocationStatusService.complete_check(db_session, projects_fixture.id)

    result = FileLocationStatusService.has_running_check(
        db_session, projects_fixture.id
    )
    assert result is False


def test_get_returns_check(db_session, projects_fixture):
    """Test get returns the check for a project"""
    original_check = FileLocationStatusService.start_check(
        db_session, projects_fixture.id, celery_task_uuid="uuid"
    )

    retrieved_check = FileLocationStatusService.get(db_session, projects_fixture.id)
    assert retrieved_check.id == original_check.id
    assert retrieved_check.project_id == projects_fixture.id


def test_get_returns_none_when_no_check(db_session, projects_fixture):
    """Test get returns None when no check exists"""
    result = FileLocationStatusService.get(db_session, projects_fixture.id)
    assert result is None

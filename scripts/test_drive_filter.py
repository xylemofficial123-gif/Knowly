import sys
import os
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.drive_ingestion import list_drive_files, list_drive_folders

@patch("app.services.drive_ingestion._get_drive_service")
def test_list_folders(mock_get_service):
    mock_service = MagicMock()
    mock_get_service.return_value = mock_service
    
    # Mock files().list().execute()
    mock_service.files().list().execute.return_value = {
        "files": [
            {"id": "folder1", "name": "Work Documents"},
            {"id": "folder2", "name": "Secret Stuff"}
        ]
    }
    
    folders = list_drive_folders()
    print(f"Discovered folders: {folders}")
    assert len(folders) == 2
    assert folders[0]["name"] == "Work Documents"
    print("✓ list_drive_folders works")

@patch("app.services.drive_ingestion._get_drive_service")
def test_filter_by_folders(mock_get_service):
    mock_service = MagicMock()
    mock_get_service.return_value = mock_service
    
    # Mock files().list().execute()
    mock_service.files().list().execute.return_value = {
        "files": [{"id": "file1", "name": "Report.pdf"}]
    }
    
    # Test single folder ID
    files = list_drive_files(folder_id="folder1")
    call_args = mock_service.files().list.call_args
    query = call_args.kwargs.get("q")
    assert "'folder1' in parents" in query
    print("✓ single folder_id filter works")
    
    # Test multiple folder IDs
    mock_service.files().list.reset_mock()
    files = list_drive_files(folder_ids=["f1", "f2"])
    # Should call twice
    assert mock_service.files().list.call_count == 2
    print("✓ multiple folder_ids loop works")

if __name__ == "__main__":
    try:
        test_list_folders()
        test_filter_by_folders()
        print("\nAll tests passed! Verification successful.")
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

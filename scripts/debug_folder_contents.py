import sys
import os
import logging

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.drive_ingestion import _get_drive_service, SUPPORTED_TYPES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_folder(folder_id):
    service = _get_drive_service()
    
    # Query EVERYTHING in this folder (no MIME filter)
    query = f"'{folder_id}' in parents and trashed=false"
    
    logger.info(f"Checking folder: {folder_id}")
    results = []
    page_token = None
    
    resp = service.files().list(
        q=query,
        fields="nextPageToken, files(id, name, mimeType)",
        pageSize=100,
        pageToken=page_token
    ).execute()
    
    files = resp.get("files", [])
    print(f"\nFound {len(files)} items in folder:")
    for f in files:
        is_supported = f['mimeType'] in SUPPORTED_TYPES
        status = "✓ Supported" if is_supported else "✗ Unsupported"
        print(f"  - Name: {f['name']}")
        print(f"    ID:   {f['id']}")
        print(f"    Type: {f['mimeType']} ({status})")
    
    if not files:
        print("  (Folder is empty or ID is incorrect)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/debug_folder_contents.py <folder_id>")
        sys.exit(1)
    
    debug_folder(sys.argv[1])
